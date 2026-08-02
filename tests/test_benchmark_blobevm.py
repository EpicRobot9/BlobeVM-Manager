import json
import http.client
import socket
import subprocess
import sys
from urllib.error import URLError
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import benchmark_blobevm as bench  # noqa: E402


@pytest.fixture
def safe_api_dns(monkeypatch):
    def resolve(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    monkeypatch.setattr(bench.socket, "getaddrinfo", resolve)


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


def test_summary_excludes_non_finite_numeric_samples():
    summary = bench.summarize_samples([
        {"cpu_percent": 1.0, "memory_percent": 10.0},
        {"cpu_percent": float("nan"), "memory_percent": float("inf")},
        {"cpu_percent": 3.0, "memory_percent": 20.0},
    ])

    assert summary["cpu_percent"] == {"median": 2.0, "p95": 2.9, "count": 2}
    assert summary["memory_percent"] == {"median": 15.0, "p95": 19.5, "count": 2}


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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_write_report_rejects_non_finite_values(tmp_path, value):
    report = {"samples": [{"elapsed_ms": value}], "summary": {}}

    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
        bench.write_report(report, tmp_path / "report.json")

    assert not (tmp_path / "report.json").exists()


def test_cli_rejects_non_positive_duration_and_interval():
    parser = bench.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--duration", "0"])
    with pytest.raises(SystemExit):
        parser.parse_args(["--interval", "-1"])


def test_parse_docker_stats_ignores_non_object_json_values():
    payload = "\n".join(["null", "[]", "42", json.dumps({"CPUPerc": "1%", "MemPerc": "2%"})])

    assert bench.parse_docker_stats(payload) == [{
        "container": "",
        "cpu_percent": 1.0,
        "memory_percent": 2.0,
        "memory_usage": "",
    }]


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_positive_float_rejects_non_finite_values(value):
    with pytest.raises(Exception):
        bench.positive_float(value)


@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_number_returns_none_for_non_finite_values(value):
    assert bench._number(value) is None


def test_comparison_skips_metrics_missing_median_or_p95(tmp_path):
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"summary": {"api": {"elapsed_ms": {"median": 10.0}}}}))
    report = {"summary": {"api": {"elapsed_ms": {"p95": 20.0}}}, "errors": []}

    bench._comparison(report, prior)

    assert report["comparison"]["summary"]["api"] == {}


def test_comparison_skips_non_finite_prior_metrics(tmp_path):
    prior = tmp_path / "prior.json"
    prior.write_text('{"summary": {"api": {"elapsed_ms": {"median": NaN, "p95": Infinity}}}}')
    report = {
        "summary": {"api": {"elapsed_ms": {"median": 12.0, "p95": 20.0}}},
        "errors": [],
    }

    bench._comparison(report, prior)

    assert report["comparison"]["summary"]["api"] == {}


def test_collect_api_timing_sanitizes_url_from_error(monkeypatch, safe_api_dns):
    url = "https://api.example.test/health?token=secret-value"

    def fail(*args, **kwargs):
        raise URLError(f"request failed for {url}")

    class FailingOpener:
        def open(self, *args, **kwargs):
            return fail(*args, **kwargs)

    monkeypatch.setattr(bench, "build_opener", lambda *handlers: FailingOpener())
    result = bench.collect_api_timing(url)

    assert "secret-value" not in result["error"]
    assert "token=" not in result["error"]
    assert url not in result["error"]


def test_collect_api_timing_returns_sanitized_error_for_malformed_secret_url():
    url = "https://[bad?token=secret-value"

    result = bench.collect_api_timing(url)

    assert result["error"]
    assert "secret-value" not in json.dumps(result)
    assert url not in json.dumps(result)


def test_collect_api_timing_rejects_non_https_and_missing_hostname(monkeypatch, safe_api_dns):
    calls = []
    monkeypatch.setattr(bench, "build_opener", lambda *handlers: None)

    assert "error" in bench.collect_api_timing("http://api.example.test/health")
    assert "error" in bench.collect_api_timing("https:///health")
    assert calls == []


def test_collect_api_timing_sends_credentials_only_for_explicit_allowed_host(monkeypatch, safe_api_dns):
    requests = []

    class Response:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return b"x"

    def capture(request, **kwargs):
        requests.append(request)
        return Response()

    class CapturingOpener:
        def open(self, request, **kwargs):
            return capture(request, **kwargs)

    monkeypatch.setattr(bench, "build_opener", lambda *handlers: CapturingOpener())
    monkeypatch.setenv("BLOBEVM_API_TOKEN", "secret-token")
    monkeypatch.setenv("BLOBEVM_API_COOKIE", "secret-cookie")

    bench.collect_api_timing("https://api.example.test/health")
    bench.collect_api_timing("https://api.example.test/health", auth_host="api.example.test")
    bench.collect_api_timing("https://other.example.test/health", auth_host="api.example.test")

    assert "Authorization" not in requests[0].headers
    assert requests[1].headers["Authorization"] == "Bearer secret-token"
    assert requests[1].headers["Cookie"] == "secret-cookie"
    assert "Authorization" not in requests[2].headers


def test_collect_api_timing_does_not_follow_redirects(monkeypatch, safe_api_dns):
    requests = []
    handlers = []

    class Response:
        status = 301
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return b"x"

    def capture(request, **kwargs):
        requests.append(request)
        return Response()

    class CapturingOpener:
        def open(self, request, **kwargs):
            return capture(request, **kwargs)

    def make_opener(*new_handlers):
        handlers.extend(new_handlers)
        return CapturingOpener()

    monkeypatch.setattr(bench, "build_opener", make_opener)
    result = bench.collect_api_timing("https://api.example.test/health", auth_host="api.example.test")

    assert result["status"] == 301
    assert len(requests) == 1
    assert any(isinstance(handler, bench._NoRedirectHandler) for handler in handlers)


@pytest.mark.parametrize("url", [
    "https://localhost/health",
    "https://service.localhost/health",
    "https://127.0.0.1/health",
    "https://10.0.0.5/health",
    "https://169.254.169.254/latest/meta-data",
])
def test_collect_api_timing_rejects_private_or_metadata_destinations(monkeypatch, url):
    monkeypatch.setattr(bench, "build_opener", lambda *handlers: pytest.fail("unsafe URL was opened"))

    result = bench.collect_api_timing(url)

    assert result["error"] == "API URL target is not a safe public address"


@pytest.mark.parametrize("url", [
    "https://api.example.test:invalid/health",
    "https://user%zz@api.example.test/health",
])
def test_collect_api_timing_returns_sanitized_error_for_invalid_url_parts(monkeypatch, url):
    monkeypatch.setattr(bench, "build_opener", lambda *handlers: pytest.fail("invalid URL was opened"))

    result = bench.collect_api_timing(url)

    assert result == {"url": "<invalid-url>", "error": "invalid API URL"}


def test_collect_api_timing_allows_safe_fake_public_host_without_network(monkeypatch):
    requests = []

    def resolve(host, *args, **kwargs):
        assert host == "safe.example.test"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]

    class Response:
        status = 204
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return b""

    class CapturingOpener:
        def open(self, request, **kwargs):
            requests.append(request)
            return Response()

    monkeypatch.setattr(bench.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(bench, "build_opener", lambda *handlers: CapturingOpener())

    result = bench.collect_api_timing("https://safe.example.test/health")

    assert result["status"] == 204
    assert requests[0].full_url == "https://safe.example.test/health"


def test_collect_api_timing_sanitizes_dns_resolution_failure(monkeypatch):
    def fail(*args, **kwargs):
        raise socket.gaierror("secret.internal.example")

    monkeypatch.setattr(bench.socket, "getaddrinfo", fail)

    result = bench.collect_api_timing("https://unresolvable.example.test/health?token=secret")

    assert result["error"] == "API hostname could not be resolved"
    assert "secret" not in json.dumps(result)


def test_collect_api_timing_sanitizes_http_client_invalid_url(monkeypatch, safe_api_dns):
    class FailingOpener:
        def open(self, *args, **kwargs):
            raise http.client.InvalidURL("https://user:secret@safe.example.test")

    monkeypatch.setattr(bench, "build_opener", lambda *handlers: FailingOpener())

    result = bench.collect_api_timing("https://safe.example.test/health")

    assert result["error"] == "invalid API URL"
    assert "secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "prior_report",
    [[], {"summary": {"api": []}}, {"summary": {"docker": {"cpu_percent": []}}}],
)
def test_comparison_reports_invalid_prior_structure_instead_of_raising(tmp_path, prior_report):
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps(prior_report))
    report = {"summary": {"docker": {"cpu_percent": {"median": 2.0, "p95": 3.0}}}, "errors": []}

    bench._comparison(report, prior)

    assert report["errors"]
    assert report["errors"][-1]["source"] == "compare"
