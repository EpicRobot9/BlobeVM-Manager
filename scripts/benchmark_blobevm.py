#!/usr/bin/env python3
"""Repeatable, read-only-by-default BlobeVM performance benchmark."""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import math
import os
import platform
import statistics
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import BaseHandler, Request, build_opener


def positive_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=positive_float, default=10.0, help="sampling duration in seconds")
    parser.add_argument("--interval", type=positive_float, default=1.0, help="seconds between samples")
    parser.add_argument("--output", type=Path, default=Path("blobevm-benchmark.json"), help="JSON report path")
    parser.add_argument("--compare", type=Path, help="include deltas versus a prior JSON report")
    parser.add_argument("--api-url", action="append", help="public API URL to time (repeatable; no API calls by default)")
    parser.add_argument("--api-auth-host", help="explicit hostname allowed to receive configured API credentials")
    parser.add_argument("--timeout", type=positive_float, default=10.0, help="subprocess/request timeout")
    parser.add_argument("--measure-start", metavar="NAME", help="explicitly run docker start NAME before sampling")
    return parser


def _number(value: str) -> float | None:
    try:
        number = float(value.strip().rstrip("%"))
        return number if math.isfinite(number) else None
    except (AttributeError, TypeError, ValueError):
        return None


def parse_docker_stats(stdout: str) -> list[dict[str, Any]]:
    samples = []
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        cpu = _number(item.get("CPUPerc"))
        memory = _number(item.get("MemPerc"))
        if cpu is None or memory is None:
            continue
        samples.append({
            "container": item.get("Name", ""),
            "cpu_percent": cpu,
            "memory_percent": memory,
            "memory_usage": item.get("MemUsage", ""),
        })
    return samples


def collect_docker_stats(timeout: float = 10.0) -> dict[str, Any]:
    command = ["docker", "stats", "--no-stream", "--format", "{{json .}}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"samples": [], "error": {"source": "docker", "error": str(exc)}}
    if result.returncode != 0:
        return {"samples": [], "error": {"source": "docker", "error": (result.stderr or "command failed").strip()}}
    return {"samples": parse_docker_stats(result.stdout)}


def measure_start(name: str, timeout: float = 10.0) -> dict[str, Any]:
    result = subprocess.run(["docker", "start", name], capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "docker start failed").strip())
    return {"name": name, "started": True}


def _percentile(values: list[float], percentile: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * percentile
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _is_finite_metric(value: Any) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for key in ("cpu_percent", "memory_percent", "elapsed_ms"):
        values = sorted(float(item[key]) for item in samples if _is_finite_metric(item.get(key)))
        if values:
            summary[key] = {"median": statistics.median(values), "p95": _percentile(values, 0.95), "count": len(values)}
    return summary


def _safe_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc.split("@")[-1], parts.path, "", ""))
    except (AttributeError, TypeError, ValueError):
        return "<invalid-url>"


class _NoRedirectHandler(BaseHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        return fp

    http_error_302 = http_error_301
    http_error_303 = http_error_301
    http_error_307 = http_error_301
    http_error_308 = http_error_301


def _sanitize_error(error: str, url: str) -> str:
    return error.replace(url, _safe_url(url))


def _is_safe_public_api_url(url: str) -> tuple[bool, str]:
    """Validate an API URL without allowing requests to private destinations."""
    try:
        parts = urlsplit(url)
        hostname = parts.hostname
        # Force validation of otherwise lazily-parsed URL components.
        parts.port
        if parts.username is not None or parts.password is not None:
            return False, "invalid API URL"
    except (AttributeError, TypeError, ValueError):
        return False, "invalid API URL"

    if parts.scheme.lower() != "https" or not hostname:
        return False, "API URL must use https and include a hostname"
    hostname = hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost"):
        return False, "API URL target is not a safe public address"

    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        try:
            resolved = socket.getaddrinfo(hostname, parts.port or 443, type=socket.SOCK_STREAM)
        except (OSError, ValueError):
            return False, "API hostname could not be resolved"
        if not resolved:
            return False, "API hostname could not be resolved"
        try:
            addresses = [ipaddress.ip_address(item[4][0]) for item in resolved]
        except (IndexError, KeyError, TypeError, ValueError):
            return False, "API hostname could not be resolved"
        if any(not item.is_global for item in addresses):
            return False, "API URL target is not a safe public address"
    else:
        if not address.is_global:
            return False, "API URL target is not a safe public address"
    return True, ""


def collect_api_timing(url: str, timeout: float = 10.0, auth_host: str | None = None) -> dict[str, Any]:
    safe_url = _safe_url(url)
    try:
        parts = urlsplit(url)
        parts.port
        hostname = parts.hostname
    except (AttributeError, TypeError, ValueError):
        return {"url": "<invalid-url>", "error": "invalid API URL"}
    safe, error = _is_safe_public_api_url(url)
    if not safe:
        return {"url": safe_url if error != "invalid API URL" else "<invalid-url>", "error": error}
    headers = {"User-Agent": "blobe-vm-benchmark/1"}
    token = os.environ.get("BLOBEVM_API_TOKEN") or os.environ.get("BLOBEVM_TOKEN")
    # Values are used only in request headers and are never included in the report.
    cookie = os.environ.get("BLOBEVM_API_COOKIE") or os.environ.get("BLOBEVM_COOKIE")
    if auth_host and hostname and hostname.lower() == auth_host.lower():
        if token:
            headers["Authorization"] = "Bearer " + token
        if cookie:
            headers["Cookie"] = cookie
    started = time.perf_counter()
    try:
        with build_opener(_NoRedirectHandler()).open(Request(url, headers=headers), timeout=timeout) as response:
            response.read(1)
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (http.client.InvalidURL, ValueError):
        return {"url": "<invalid-url>", "error": "invalid API URL"}
    except http.client.HTTPException as exc:
        return {"url": safe_url, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "error": _sanitize_error(str(exc), url)}
    except (OSError, URLError) as exc:
        return {"url": safe_url, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "error": _sanitize_error(str(exc), url)}
    return {"url": safe_url, "status": status, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}


def build_report(samples: list[dict[str, Any]], api_samples: list[dict[str, Any]], errors: list[dict[str, str]], environment: dict[str, Any]) -> dict[str, Any]:
    return {
        "samples": {"docker": samples, "api": api_samples},
        "summary": {"docker": summarize_samples(samples), "api": summarize_samples(api_samples)},
        "environment": environment,
        "errors": errors,
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, allow_nan=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _comparison(report: dict[str, Any], prior_path: Path | None) -> None:
    if not prior_path:
        return
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        if not isinstance(prior, dict):
            raise TypeError("prior report must be an object")
        prior_summary = prior.get("summary", {})
        if not isinstance(prior_summary, dict):
            raise TypeError("prior summary must be an object")
        current_summary = report.get("summary", {})
        if not isinstance(current_summary, dict):
            raise TypeError("current summary must be an object")
        report["comparison"] = {"baseline": str(prior_path), "summary": {}}
        for group in ("docker", "api"):
            current = current_summary.get(group, {})
            old = prior_summary.get(group, {})
            if not isinstance(current, dict) or not isinstance(old, dict):
                raise TypeError(f"comparison summary for {group} must be an object")
            for key in current.keys() & old.keys():
                if not isinstance(current[key], dict) or not isinstance(old[key], dict):
                    raise TypeError(f"comparison metric {key} must be an object")
            report["comparison"]["summary"][group] = {
                key: {
                    metric: current[key][metric] - old[key][metric]
                    for metric in ("median", "p95")
                    if metric in current[key]
                    and metric in old[key]
                    and _is_finite_metric(current[key][metric])
                    and _is_finite_metric(old[key][metric])
                }
                for key in current.keys() & old.keys()
                if isinstance(current[key], dict)
                and isinstance(old[key], dict)
                and any(
                    metric in current[key]
                    and metric in old[key]
                    and _is_finite_metric(current[key][metric])
                    and _is_finite_metric(old[key][metric])
                    for metric in ("median", "p95")
                )
            }
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        report["errors"].append({"source": "compare", "error": str(exc)})


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors: list[dict[str, str]] = []
    if args.measure_start:
        try:
            measure_start(args.measure_start, args.timeout)
        except (OSError, subprocess.TimeoutExpired, RuntimeError) as exc:
            errors.append({"source": "docker-start", "error": str(exc)})
    samples: list[dict[str, Any]] = []
    api_samples: list[dict[str, Any]] = []
    deadline = time.monotonic() + args.duration
    while True:
        docker = collect_docker_stats(args.timeout)
        samples.extend(docker["samples"])
        if docker.get("error"):
            errors.append(docker["error"])
        for url in args.api_url or []:
            timed = collect_api_timing(url, args.timeout, args.api_auth_host)
            api_samples.append(timed)
            if timed.get("error"):
                errors.append({"source": "api", "error": timed["error"]})
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(args.interval, remaining))
    report = build_report(samples, api_samples, errors, {"platform": platform.platform(), "python": sys.version.split()[0]})
    _comparison(report, args.compare)
    write_report(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
