#!/usr/bin/env python3
"""Repeatable, read-only-by-default BlobeVM performance benchmark."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


def positive_float(value: str) -> float:
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=positive_float, default=10.0, help="sampling duration in seconds")
    parser.add_argument("--interval", type=positive_float, default=1.0, help="seconds between samples")
    parser.add_argument("--output", type=Path, default=Path("blobevm-benchmark.json"), help="JSON report path")
    parser.add_argument("--compare", type=Path, help="include deltas versus a prior JSON report")
    parser.add_argument("--api-url", action="append", help="public API URL to time (repeatable; no API calls by default)")
    parser.add_argument("--timeout", type=positive_float, default=10.0, help="subprocess/request timeout")
    parser.add_argument("--measure-start", metavar="NAME", help="explicitly run docker start NAME before sampling")
    return parser


def _number(value: str) -> float | None:
    try:
        return float(value.strip().rstrip("%"))
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


def summarize_samples(samples: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {}
    for key in ("cpu_percent", "memory_percent", "elapsed_ms"):
        values = sorted(float(item[key]) for item in samples if isinstance(item.get(key), (int, float)))
        if values:
            summary[key] = {"median": statistics.median(values), "p95": _percentile(values, 0.95), "count": len(values)}
    return summary


def _safe_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc.split("@")[-1], parts.path, "", ""))


def collect_api_timing(url: str, timeout: float = 10.0) -> dict[str, Any]:
    headers = {"User-Agent": "blobe-vm-benchmark/1"}
    token = os.environ.get("BLOBEVM_API_TOKEN") or os.environ.get("BLOBEVM_TOKEN")
    # Values are used only in request headers and are never included in the report.
    cookie = os.environ.get("BLOBEVM_API_COOKIE") or os.environ.get("BLOBEVM_COOKIE")
    if token:
        headers["Authorization"] = "Bearer " + token
    if cookie:
        headers["Cookie"] = cookie
    safe_url = _safe_url(url)
    started = time.perf_counter()
    try:
        with urlopen(Request(url, headers=headers), timeout=timeout) as response:
            response.read(1)
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except (OSError, URLError, ValueError) as exc:
        return {"url": safe_url, "elapsed_ms": round((time.perf_counter() - started) * 1000, 3), "error": str(exc)}
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
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _comparison(report: dict[str, Any], prior_path: Path | None) -> None:
    if not prior_path:
        return
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        report["comparison"] = {"baseline": str(prior_path), "summary": {}}
        for group in ("docker", "api"):
            current = report["summary"].get(group, {})
            old = prior.get("summary", {}).get(group, {})
            report["comparison"]["summary"][group] = {
                key: {metric: current[key][metric] - old[key][metric] for metric in ("median", "p95")}
                for key in current.keys() & old.keys() if isinstance(current[key], dict) and isinstance(old[key], dict)
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
            timed = collect_api_timing(url, args.timeout)
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
