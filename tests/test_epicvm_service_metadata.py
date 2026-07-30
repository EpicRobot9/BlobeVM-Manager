"""Contract tests for EpicVM service descriptions and legacy service identity."""

from pathlib import Path
import re


REPO_ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_dashboard_service_has_epicvm_description_without_runtime_identity_changes():
    service = _text("server/blobedash.service")

    assert "Description=EpicVM Dashboard (direct mode)" in service
    assert "Description=BlobeVM Dashboard (direct mode)" not in service
    assert "ExecStart=/usr/bin/env bash /opt/blobe-vm/server/blobedash-ensure.sh" in service
    assert "ExecReload=/usr/bin/env bash /opt/blobe-vm/server/blobedash-ensure.sh" in service
    assert "ExecStop=/usr/bin/env docker rm -f blobedash" in service
    assert (REPO_ROOT / "server/blobedash.service").name == "blobedash.service"


def test_optimizer_compatibility_metadata_uses_epicvm_description():
    service = _text("blobe-optimizer.service")
    ensure_script = _text("optimizer/optimizer-ensure.sh")

    assert "EpicVM Optimizer" in service
    assert "legacy compatibility" in service.lower()
    assert "BlobeVM Optimizer" not in ensure_script
    assert "EpicVM Optimizer" in ensure_script
    assert "/opt/blobe-vm" in ensure_script


def test_installer_dashboard_auth_status_uses_epicvm_brand_only():
    installer = _text("server/install.sh")

    assert installer.count("EpicVM Dashboard Auth") == 2
    assert "BlobeVM Dashboard Auth" not in installer
    assert re.search(r'echo "  EpicVM Dashboard Auth: enabled', installer)
    assert re.search(r'echo "  EpicVM Dashboard Auth: disabled', installer)
