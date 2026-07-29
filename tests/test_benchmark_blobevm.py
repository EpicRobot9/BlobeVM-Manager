import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import benchmark_blobevm as bench


def test_parse_docker_stats_json_lines_returns_numeric_samples():
    payload = '\n'.join([
        json.dumps({"Name": "blobe-one", "CPUPerc": "12.50%", "MemUsage": "100MiB / 1GiB", "MemPerc": "9.77%"}),
        json.dumps({"Name": "blobe-two", "CPUPerc": "0.25%", "MemUsage": "2.0GiB / 4GiB", "MemPerc": "50.00%"}),
    ])

    samples = bench.parse_docker_stats(payload)

    assert samples == [
        {"container": "blobe-one", "cpu_percent": 12.5, "memory_percent": 9.77, "memory_usage": "100MiB / 1GiB"},
        {"container": "blobe-two", "cpu_percent": 0.25, "memory_percent": 50.0, "memory_usage": "2.0GiB / 4GiB"},
    ]


def test_summary_reports_median_and_p95_for_numeric_metrics():
    summary = bench.summarize_samples([
        {"cpu_percent": 1.0, "memory_percent": 10.0},
        {"cpu_percent": 3.0, "memory_percent": 20.0},
        {"cpu_percent": 5.0, "memory_percent": 30.0},
    ])

    assert summary["cpu_percent"] == {"median": 3.0, "p95": 4.8, "count": 3}
    assert summary["memory_percent"] == {"median": 20.0, "p95": 29.0, "count": 3}


def test_collect_docker_stats_is_read_only_by_default(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, '{"Name":"vm","CPUPerc":"1%","MemUsage":"1MiB","MemPerc":"2%"}\n', "")

    monkeypatch.setattr(bench.subprocess, "run", fake_run)
    result = bench.collect_docker_stats()

    assert result["samples"][0]["container"] == "vm"
    assert calls == [["docker", "stats", "--no-stream", "--format", "{{json .}}"]]


def test_measure_start_is_the_only_start_operation(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(bench.subprocess, "run", fake_run)
    assert bench.measure_start("vm") == {"name": "vm", "started": True}
    assert calls == [["docker", "start", "vm"]]


def test_write_report_contains_environment_samples_summary_and_errors(tmp_path):
    output = tmp_path / "report.json"
    report = bench.build_report(
        samples=[{"cpu_percent": 2.0, "memory_percent": 4.0}],
        api_samples=[{"url": "https://example.test/health", "status": 200, "elapsed_ms": 12.0}],
        errors=[{"source": "docker", "error": "unavailable"}],
        environment={"platform": "test"},
    )

    bench.write_report(report, output)
    loaded = json.loads(output.read_text())

    assert loaded["samples"]["docker"] == [{"cpu_percent": 2.0, "memory_percent": 4.0}]
    assert loaded["samples"]["api"] == [{"url": "https://example.test/health", "status": 200, "elapsed_ms": 12.0}]
    assert loaded["summary"]["docker"]["cpu_percent"]["median"] == 2.0
    assert loaded["environment"]["platform"] == "test"
    assert loaded["errors"] == [{"source": "docker", "error": "unavailable"}]


def test_cli_rejects_non_positive_duration_and_interval():
    parser = bench.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--duration", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--interval", "-1"])
