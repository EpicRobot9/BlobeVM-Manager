"""Persistent remote-host registry for EpicVM.

Remote hosts are configuration records, not arbitrary URLs supplied by browser
clients.  The registry validates the record before creating an agent client,
refreshes when the file changes, and exposes only redacted inventory records.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

try:
    from .remote_agent_client import RemoteAgentHost
    from .vm_hosts import LocalDockerHost, VmHostRegistry
except ImportError:  # pragma: no cover - direct module loading
    from remote_agent_client import RemoteAgentHost
    from vm_hosts import LocalDockerHost, VmHostRegistry


HOST_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")
DEFAULT_REMOTE_HOSTS_FILE = "/var/lib/epicvm/remote-hosts.json"


class RemoteHostConfigError(ValueError):
    """The remote-host configuration is malformed or unsafe."""


def remote_hosts_path(path: str | os.PathLike[str] | None = None) -> Path:
    return Path(path or os.environ.get("EPICVM_REMOTE_HOSTS_FILE") or DEFAULT_REMOTE_HOSTS_FILE)


def _is_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _validate_agent_url(value: Any) -> str:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RemoteHostConfigError("agent_url must be an http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RemoteHostConfigError("agent_url cannot contain credentials, query, or fragment")
    hostname = parsed.hostname.rstrip(".").lower()
    allowed = _is_truthy(os.environ.get("EPICVM_ALLOW_NON_TAILSCALE_HOSTS"))
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if not allowed:
        is_tailscale_ip = bool(address and ipaddress.ip_network("100.64.0.0/10").version == address.version and address in ipaddress.ip_network("100.64.0.0/10"))
        is_tailnet_name = hostname.endswith(".ts.net")
        if not (is_tailscale_ip or is_tailnet_name):
            raise RemoteHostConfigError("agent_url must target a Tailscale address")
    return url


def _normalize_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    host_id = str(raw.get("id") or "").strip().lower()
    if not HOST_ID_RE.fullmatch(host_id):
        raise RemoteHostConfigError("host id must match [a-z0-9][a-z0-9_-]{0,62}")
    token = str(raw.get("token") or "").strip()
    if not token:
        raise RemoteHostConfigError(f"remote host {host_id} is missing an agent token")
    record = {
        "id": host_id,
        "display_name": str(raw.get("display_name") or raw.get("name") or host_id).strip()[:120],
        "platform": str(raw.get("platform") or "windows").strip().lower(),
        "provider": str(raw.get("provider") or "hyperv").strip().lower(),
        "agent_url": _validate_agent_url(raw.get("agent_url")),
        "token": token,
        "enabled": raw.get("enabled", True) is not False,
        "timeout": max(0.5, min(float(raw.get("timeout", 2.0)), 20.0)),
    }
    if not record["display_name"]:
        raise RemoteHostConfigError(f"remote host {host_id} has an empty display name")
    return record


def load_remote_host_configs(path: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    config_path = remote_hosts_path(path)
    if not config_path.exists():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RemoteHostConfigError(f"cannot read remote host registry: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RemoteHostConfigError(f"invalid remote host registry JSON: {exc}") from exc
    if isinstance(data, list):
        raw_hosts = data
    elif isinstance(data, dict):
        raw_hosts = data.get("hosts", [])
    else:
        raise RemoteHostConfigError("remote host registry must be an object or list")
    if not isinstance(raw_hosts, list):
        raise RemoteHostConfigError("remote host registry hosts must be a list")
    result = []
    seen: set[str] = set()
    for raw in raw_hosts:
        if not isinstance(raw, Mapping):
            raise RemoteHostConfigError("each remote host must be an object")
        record = _normalize_record(raw)
        if record["id"] == "local" or record["id"] in seen:
            raise RemoteHostConfigError(f"duplicate or reserved remote host id: {record['id']}")
        seen.add(record["id"])
        if record["enabled"]:
            result.append(record)
    return result


class ConfiguredVmHostRegistry(VmHostRegistry):
    """Local provider plus validated remote providers from a JSON registry."""

    def __init__(self, local_provider: LocalDockerHost | None = None, path: str | os.PathLike[str] | None = None):
        self.local_provider = local_provider or LocalDockerHost()
        self.path = remote_hosts_path(path)
        self._loaded_signature: tuple[int, int] | None = None
        self.config_error = ""
        super().__init__([self.local_provider])
        self.refresh(force=True)

    def _signature(self) -> tuple[int, int] | None:
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return None
        return (int(stat.st_mtime_ns), int(stat.st_size))

    def refresh(self, *, force: bool = False) -> None:
        signature = self._signature()
        if not force and signature == self._loaded_signature:
            return
        providers: dict[str, Any] = {"local": self.local_provider}
        try:
            records = load_remote_host_configs(self.path)
            self.config_error = ""
        except RemoteHostConfigError as exc:
            # A malformed optional registry must not take down the dashboard;
            # keep local VMs available and surface the redacted error in the
            # host-inventory response.
            records = []
            self.config_error = str(exc)[:500]
        for record in records:
            providers[record["id"]] = RemoteAgentHost(record)
        self._providers = providers
        self._loaded_signature = signature

    def get(self, host_id: str = "local"):
        self.refresh()
        return super().get(host_id)

    @property
    def providers(self):
        self.refresh()
        return super().providers

    def public_records(self) -> list[dict[str, Any]]:
        self.refresh()
        local = {
            "id": "local",
            "display_name": getattr(self.local_provider, "host_name", "EpicVM Server"),
            "kind": "local",
            "platform": "linux",
            "provider": getattr(self.local_provider, "provider", "local-docker"),
            "transport": "local",
            "online": True,
            "capabilities": {
                "create_vm": True,
                "start": True,
                "stop": True,
                "restart": True,
                "delete": True,
                "console": True,
            },
            "resources": {},
            "last_error": "",
        }
        records = [local]
        for host_id, provider in self._providers.items():
            if host_id == "local":
                continue
            try:
                records.append(provider.public_record())
            except Exception as exc:  # inventory must remain useful if a host is broken
                records.append({
                    "id": host_id,
                    "display_name": getattr(provider, "host_name", host_id),
                    "kind": "remote",
                    "platform": getattr(provider, "platform", "unknown"),
                    "provider": getattr(provider, "provider", "unknown"),
                    "transport": "tailscale",
                    "online": False,
                    "capabilities": {"create_vm": False, "start": False, "stop": False, "restart": False, "delete": False, "console": False},
                    "resources": {},
                    "last_error": str(exc)[:500],
                })
        return records


def redact_host_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return a browser-safe copy; tokens and unknown secret fields never escape."""
    allowed = {
        "id", "display_name", "kind", "platform", "provider", "agent_url",
        "transport", "online", "capabilities", "resources", "last_error",
    }
    return {key: value for key, value in record.items() if key in allowed}


__all__ = [
    "ConfiguredVmHostRegistry",
    "DEFAULT_REMOTE_HOSTS_FILE",
    "RemoteHostConfigError",
    "load_remote_host_configs",
    "redact_host_record",
    "remote_hosts_path",
]
