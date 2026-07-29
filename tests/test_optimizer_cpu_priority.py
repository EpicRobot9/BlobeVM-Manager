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
    monkeypatch.setattr(optimizer.subprocess, "check_output", lambda argv, text=True: "container-id\n")
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
    assert json.loads((tmp_path / "cpu.json").read_text()) == {
        "enabled": True,
        "vms": {
            "vm1": {"share": 2048, "containerId": "container-id"},
            "vm2": {"share": 512, "containerId": "container-id"},
        },
    }


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


def test_cpu_priority_requires_boolean_true_opt_in(monkeypatch, tmp_path):
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(tmp_path / "cpu.json"))
    calls = []
    monkeypatch.setattr(optimizer.subprocess, "check_call", lambda argv: calls.append(argv))

    for value in ("false", "true", 1, 0, None):
        assert optimizer._apply_cpu_priority(
            {"activityCpuPriorityEnabled": value},
            [{"name": "vm1", "activityClass": "active", "running": True}],
        ) == {}
    assert calls == []


def test_cpu_priority_persists_exactly_current_successful_desired_map(monkeypatch, tmp_path):
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(tmp_path / "cpu.json"))
    identities = {"blobevm_vm1": "id-1", "blobevm_vm2": "id-2"}
    calls = []

    def inspect(argv, text=True):
        return identities[argv[-1]] + "\n"

    monkeypatch.setattr(optimizer.subprocess, "check_output", inspect)
    monkeypatch.setattr(optimizer.subprocess, "check_call", lambda argv: calls.append(argv))
    cfg = {"activityCpuPriorityEnabled": True, "activeCpuShares": 2048, "idleCpuShares": 512}
    states = [
        {"name": "vm1", "activityClass": "active", "running": True},
        {"name": "vm2", "activityClass": "idle", "running": True},
    ]

    assert optimizer._apply_cpu_priority(cfg, states) == {"vm1": 2048, "vm2": 512}
    assert optimizer._apply_cpu_priority(cfg, [states[0]]) == {"vm1": 2048}
    assert json.loads((tmp_path / "cpu.json").read_text()) == {
        "enabled": True,
        "vms": {"vm1": {"share": 2048, "containerId": "id-1"}},
    }


def test_cpu_priority_reapplies_when_container_identity_changes(monkeypatch, tmp_path):
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(tmp_path / "cpu.json"))
    identity = ["id-1"]
    calls = []
    monkeypatch.setattr(
        optimizer.subprocess,
        "check_output",
        lambda argv, text=True: identity[0] + "\n",
    )
    monkeypatch.setattr(optimizer.subprocess, "check_call", lambda argv: calls.append(argv))
    cfg = {"activityCpuPriorityEnabled": True, "activeCpuShares": 2048}
    state = [{"name": "vm1", "activityClass": "active", "running": True}]

    optimizer._apply_cpu_priority(cfg, state)
    identity[0] = "id-2"
    optimizer._apply_cpu_priority(cfg, state)
    assert calls == [
        ["docker", "update", "--cpu-shares=2048", "blobevm_vm1"],
        ["docker", "update", "--cpu-shares=2048", "blobevm_vm1"],
    ]


def test_disabling_cpu_priority_restores_only_previously_applied_valid_vms(monkeypatch, tmp_path):
    path = tmp_path / "cpu.json"
    path.write_text(json.dumps({
        "enabled": True,
        "vms": {
            "vm1": {"share": 2048, "containerId": "id-1"},
            "bad/name": {"share": 512, "containerId": "id-bad"},
            "unrelated": {"share": 1024, "containerId": "id-u"},
        },
    }))
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(path))
    calls = []
    identities = {
        "blobevm_vm1": "id-1",
        "blobevm_unrelated": "id-u",
    }
    monkeypatch.setattr(
        optimizer.subprocess,
        "check_output",
        lambda argv, text=True: identities[argv[-1]] + "\n",
    )
    monkeypatch.setattr(optimizer.subprocess, "check_call", lambda argv: calls.append(argv))

    assert optimizer._apply_cpu_priority(
        {"activityCpuPriorityEnabled": False},
        [{"name": "vm1", "activityClass": "active", "running": True}],
    ) == {}
    assert calls == [
        ["docker", "update", "--cpu-shares=1024", "id-1"],
        ["docker", "update", "--cpu-shares=1024", "id-u"],
    ]
    assert json.loads(path.read_text()) == {
        "enabled": False,
        "vms": {"bad/name": {"share": 512, "containerId": "id-bad"}},
    }


def test_disabling_cpu_priority_fails_closed_on_corrupt_or_mismatched_identity(monkeypatch, tmp_path):
    path = tmp_path / "cpu.json"
    metadata = {
        "enabled": True,
        "vms": {
            "vm1": {"share": 2048, "containerId": "id-1"},
            "vm2": {"share": 512, "containerId": "old-id"},
            "vm3": {"share": 512},
            "vm4": "corrupt",
            "bad/name": {"share": 512, "containerId": "id-bad"},
        },
    }
    path.write_text(json.dumps(metadata))
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(path))
    identities = {
        "blobevm_vm1": "id-1",
        "blobevm_vm2": "new-id",
        "blobevm_vm3": "id-3",
        "blobevm_vm4": "id-4",
    }
    calls = []
    monkeypatch.setattr(
        optimizer.subprocess,
        "check_output",
        lambda argv, text=True: identities[argv[-1]] + "\n",
    )
    monkeypatch.setattr(optimizer.subprocess, "check_call", lambda argv: calls.append(argv))

    assert optimizer._apply_cpu_priority({"activityCpuPriorityEnabled": False}, []) == {}
    assert calls == [["docker", "update", "--cpu-shares=1024", "id-1"]]
    assert json.loads(path.read_text()) == {
        "enabled": False,
        "vms": {
            "vm2": {"share": 512, "containerId": "old-id"},
            "vm3": {"share": 512},
            "vm4": "corrupt",
            "bad/name": {"share": 512, "containerId": "id-bad"},
        },
    }


def test_disabling_cpu_priority_retries_remaining_entries_after_failure(monkeypatch, tmp_path):
    path = tmp_path / "cpu.json"
    path.write_text(json.dumps({
        "enabled": True,
        "vms": {"vm1": {"share": 2048, "containerId": "id-1"}},
    }))
    monkeypatch.setattr(optimizer, "CPU_PRIORITY_META_PATH", str(path))
    identities = ["id-1"]
    failures = [True]
    calls = []

    monkeypatch.setattr(
        optimizer.subprocess,
        "check_output",
        lambda argv, text=True: identities[0] + "\n",
    )

    def update(argv):
        calls.append(argv)
        if failures[0]:
            failures[0] = False
            raise RuntimeError("docker unavailable")

    monkeypatch.setattr(optimizer.subprocess, "check_call", update)

    assert optimizer._apply_cpu_priority({"activityCpuPriorityEnabled": False}, []) == {}
    assert json.loads(path.read_text()) == {
        "enabled": False,
        "vms": {"vm1": {"share": 2048, "containerId": "id-1"}},
    }
    assert optimizer._apply_cpu_priority({"activityCpuPriorityEnabled": False}, []) == {}
    assert calls == [
        ["docker", "update", "--cpu-shares=1024", "id-1"],
        ["docker", "update", "--cpu-shares=1024", "id-1"],
    ]
    assert not path.exists()
