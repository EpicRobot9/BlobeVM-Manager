import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "dashboard"))

import optimizer


def test_cpu_priority_shares_are_deterministic_for_running_vm_states():
    states = [
        {"name": "idle-vm", "activityClass": "idle", "running": True},
        {"name": "active-vm", "activityClass": "active", "running": True},
        {"name": "warm-vm", "activityClass": "warm", "running": True},
        {"name": "stopped-vm", "activityClass": "active", "running": False},
        {"name": "dashboard", "activityClass": "active", "running": True},
        {"name": "bad/name", "activityClass": "idle", "running": True},
        {"name": "unknown-vm", "activityClass": "unknown", "running": True},
    ]

    assert optimizer._desired_cpu_shares(states, {
        "activeCpuShares": 2048,
        "warmCpuShares": 1024,
        "idleCpuShares": 512,
    }) == {
        "active-vm": 2048,
        "idle-vm": 512,
        "warm-vm": 1024,
    }


def test_cpu_priority_uses_safe_positive_bounded_config_values():
    assert optimizer._desired_cpu_shares(
        [{"name": "vm1", "activityClass": "active", "running": True}],
        {"activeCpuShares": -10, "warmCpuShares": "not-a-number", "idleCpuShares": 999999999},
    ) == {"vm1": 2}


def test_cpu_priority_is_opt_in_and_only_updates_changed_vm_containers(monkeypatch, tmp_path):
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(tmp_path / "cpu.json"))
    states = [
        {"name": "vm1", "activityClass": "active", "running": True},
        {"name": "vm2", "activityClass": "idle", "running": True},
        {"name": "stopped", "activityClass": "warm", "running": False},
    ]
    calls = []
    monkeypatch.setattr(optimizer.subprocess, "check_call", lambda argv: calls.append(argv))

    assert optimizer._apply_cpu_priority({}, states) == {}
    assert calls == []
    assert not (tmp_path / "cpu.json").exists()

    cfg = {"activityCpuPriorityEnabled": True, "activeCpuShares": 2048,
           "warmCpuShares": 1024, "idleCpuShares": 512}
    assert optimizer._apply_cpu_priority(cfg, states) == {"vm1": 2048, "vm2": 512}
    assert calls == [
        ["docker", "update", "--cpu-shares=2048", "blobevm_vm1"],
        ["docker", "update", "--cpu-shares=512", "blobevm_vm2"],
    ]

    assert optimizer._apply_cpu_priority(cfg, states) == {"vm1": 2048, "vm2": 512}
    assert len(calls) == 2
    assert json.loads((tmp_path / "cpu.json").read_text()) == {"vm1": 2048, "vm2": 512}


def test_cpu_priority_failure_does_not_crash_or_mark_share_applied(monkeypatch, tmp_path):
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(tmp_path / "cpu.json"))

    def fail(_argv):
        raise RuntimeError("docker unavailable")

    monkeypatch.setattr(optimizer.subprocess, "check_call", fail)
    result = optimizer._apply_cpu_priority(
        {"activityCpuPriorityEnabled": True, "activeCpuShares": 2048},
        [{"name": "vm1", "activityClass": "active", "running": True}],
    )

    assert result == {}
    assert not (tmp_path / "cpu.json").exists()
