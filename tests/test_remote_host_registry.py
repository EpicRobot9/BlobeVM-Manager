import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

from dashboard.remote_hosts import ConfiguredVmHostRegistry, RemoteHostConfigError, load_remote_host_configs
from dashboard.remote_agent_client import RemoteAgentClient, RemoteAgentError, RemoteAgentHost
from dashboard.vm_hosts import LocalDockerHost, VmHostUnavailable


def test_load_configs_redacts_tokens_and_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "remote-hosts.json"
    path.write_text(json.dumps({
        "version": 1,
        "hosts": [{
            "id": "epic-pc",
            "display_name": "Epic PC",
            "platform": "windows",
            "provider": "hyperv",
            "agent_url": "http://100.72.220.117:8765",
            "token": "secret-token",
            "enabled": True,
        }],
    }))

    configs = load_remote_host_configs(path)
    assert configs[0]["id"] == "epic-pc"
    assert "token" in configs[0]

    registry = ConfiguredVmHostRegistry(LocalDockerHost(manager="manager"), path)
    public = registry.public_records()
    remote = next(item for item in public if item["id"] == "epic-pc")
    assert "token" not in remote
    assert remote["provider"] == "hyperv"

    path.write_text(json.dumps({
        "version": 1,
        "hosts": [
            {"id": "same", "display_name": "A", "agent_url": "http://100.64.0.2:1", "token": "a"},
            {"id": "same", "display_name": "B", "agent_url": "http://100.64.0.3:1", "token": "b"},
        ],
    }))
    with pytest.raises(RemoteHostConfigError, match="duplicate"):
        load_remote_host_configs(path)


def test_registry_marks_unreachable_host_offline_without_hiding_local(tmp_path):
    path = tmp_path / "remote-hosts.json"
    path.write_text(json.dumps({
        "version": 1,
        "hosts": [{
            "id": "offline-pc",
            "display_name": "Offline PC",
            "agent_url": "http://100.64.0.2:8765",
            "token": "secret-token",
            "enabled": True,
        }],
    }))
    registry = ConfiguredVmHostRegistry(LocalDockerHost(manager="manager"), path)
    registry._providers["offline-pc"].client = SimpleNamespace(
        health=lambda: (_ for _ in ()).throw(RemoteAgentError("offline")),
        capabilities=lambda: {},
    )

    records = registry.public_records()
    assert any(item["id"] == "local" for item in records)
    offline = next(item for item in records if item["id"] == "offline-pc")
    assert offline["online"] is False
    assert offline["capabilities"]["create_vm"] is False


def test_remote_agent_client_sends_token_and_parses_vm_list(monkeypatch):
    calls = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"vms": [{"name": "alpha", "state": "Running"}]}).encode()

    def fake_open(req, timeout):
        calls.append((req, timeout))
        return FakeResponse()

    client = RemoteAgentClient("http://100.64.0.2:8765", "token", opener=fake_open)
    result = client.list_vms()
    assert result == [{"name": "alpha", "state": "Running"}]
    assert calls[0][0].get_header("Authorization") == "Bearer token"
    assert calls[0][1] <= 3


def test_remote_host_lifecycle_errors_are_normalized(monkeypatch):
    host = RemoteAgentHost({
        "id": "epic-pc",
        "display_name": "Epic PC",
        "agent_url": "http://100.64.0.2:8765",
        "token": "token",
    })
    host.client = SimpleNamespace(
        lifecycle=lambda *args, **kwargs: (_ for _ in ()).throw(RemoteAgentError("offline")),
    )
    with pytest.raises(VmHostUnavailable):
        host.run_manager("start", "alpha")


def test_hosts_api_redacts_credentials_and_exposes_inventory(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOBEVM_ALLOW_INSECURE_DASHBOARD", "1")
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    import importlib

    module = importlib.import_module("dashboard.app")

    class FakeRegistry:
        config_error = ""

        def refresh(self):
            return None

        def public_records(self):
            return [{
                "id": "epic-pc",
                "display_name": "Epic PC",
                "kind": "remote",
                "provider": "hyperv",
                "agent_url": "http://100.64.0.2:8765",
                "token": "must-not-leak",
                "online": True,
                "capabilities": {"create_vm": True},
            }]

    monkeypatch.setattr(module, "VM_HOST_REGISTRY", FakeRegistry())
    response = module.app.test_client().get("/dashboard/api/hosts")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["hosts"][0]["id"] == "epic-pc"
    assert "token" not in payload["hosts"][0]


def test_remote_lifecycle_route_uses_selected_host(monkeypatch, tmp_path):
    monkeypatch.setenv("BLOBEVM_ALLOW_INSECURE_DASHBOARD", "1")
    monkeypatch.setenv("BLOBEDASH_STATE", str(tmp_path))
    import importlib

    module = importlib.import_module("dashboard.app")
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    class FakeHost:
        kind = "remote"
        host_id = "epic-pc"
        host_name = "Epic PC"

        def run_manager(self, action, name, **kwargs):
            calls.append((action, name, kwargs))
            return Result()

        def check_call(self, action, name, **kwargs):
            calls.append((action, name, kwargs))

    class FakeRegistry:
        def refresh(self):
            return None

        def get(self, host_id="local"):
            assert host_id == "epic-pc"
            return FakeHost()

    monkeypatch.setattr(module, "VM_HOST_REGISTRY", FakeRegistry())
    response = module.app.test_client().post("/dashboard/api/start/alpha?host_id=epic-pc")
    assert response.status_code == 200
    assert calls and calls[0][0:2] == ("start", "alpha")
