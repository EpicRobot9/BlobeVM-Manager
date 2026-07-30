import json
from pathlib import Path


REPO_ROOT = Path(__file__).parents[1]


def test_desktop_welcome_copy_uses_epicvm_and_preserves_feature_claims():
    welcome = REPO_ROOT / "root/config/Desktop/EpicVM.txt"
    legacy = REPO_ROOT / "root/config/Desktop/BlobeVM.txt"

    assert welcome.is_file()
    assert not legacy.exists()
    content = welcome.read_text()
    assert content.startswith("Welcome to EpicVM!")
    for claim in (
        "Runs entirely in a web browser",
        "Is unblocked",
        "Has Windows app support",
        "Has audio support",
        "Can run games with almost no lag",
        "Can Bypass School Network",
        "Is very fast",
    ):
        assert claim in content


def test_dashboard_package_metadata_uses_epicvm_name_consistently():
    package = json.loads((REPO_ROOT / "dashboard_v2/package.json").read_text())
    lockfile = json.loads((REPO_ROOT / "dashboard_v2/package-lock.json").read_text())

    assert package["name"] == "epicvm-dashboard-v2"
    assert lockfile["name"] == "epicvm-dashboard-v2"
    assert lockfile["packages"][""]["name"] == "epicvm-dashboard-v2"
