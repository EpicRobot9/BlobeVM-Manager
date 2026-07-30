"""Executable contract checks for the EpicVM public-brand migration.

The public-brand assertion is intentionally RED until the later rebrand tasks
replace the visible legacy product name.  Compatibility identifiers are
checked separately and are expected to remain documented throughout.
"""

from __future__ import annotations

from pathlib import Path
import subprocess


REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_PATH = REPO_ROOT / "tests" / "brand_legacy_allowlist.txt"
LEGACY_ABI_TOKENS = (
    "/opt/blobe-vm",
    "blobevm_",
    "com.blobevm.managed",
    "BLOBEVM_",
    "BLOBEDASH_",
)

# These are the public-facing files in scope for the initial rebrand contract.
# EpicVM.txt is the intended destination; the legacy filename remains in scope
# until the later task performs the rename.
PUBLIC_FILES = (
    "README.md",
    "PROJECT_CONTEXT.md",
    "dashboard/app.py",
    "dashboard_v2/index.html",
    "dashboard_v2/src/components/Login.jsx",
    "dashboard_v2/src/components/Sidebar.jsx",
    "dashboard_v2/src/components/Topbar.jsx",
    "root/config/Desktop/EpicVM.txt",
    "root/config/Desktop/BlobeVM.txt",
)


def _tracked_files() -> list[Path]:
    """Return tracked paths, making the test independent of cwd/package install."""
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [REPO_ROOT / item for item in result.stdout.decode().split("\0") if item]


def _human_facing_source_files() -> list[Path]:
    """Select tracked text sources while excluding generated/history artifacts."""
    excluded_parts = {".git", ".hermes", "dist", "screenshots"}
    excluded_names = {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
    }
    historical_markers = ("ROLLBACK", "HISTORY", "historical")
    files = []
    for path in _tracked_files():
        relative = path.relative_to(REPO_ROOT)
        if any(part in excluded_parts for part in relative.parts):
            continue
        if path.name in excluded_names or any(
            marker in path.name for marker in historical_markers
        ):
            continue
        try:
            path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        files.append(path)
    return files


def _allowlist_entries() -> dict[str, str]:
    entries = {}
    for raw_line in ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        token, separator, reason = line.partition("|")
        assert separator, f"Malformed allowlist line: {raw_line!r}"
        entries[token.strip()] = reason.strip()
    return entries


def test_legacy_abi_tokens_are_documented_with_reasons() -> None:
    entries = _allowlist_entries()
    assert set(LEGACY_ABI_TOKENS) <= entries.keys()
    for token in LEGACY_ABI_TOKENS:
        assert entries[token], f"Missing compatibility reason for {token!r}"


def test_current_public_files_contain_no_legacy_public_brand() -> None:
    """RED until later rebrand work removes visible ``BlobeVM`` copy."""
    tracked = {path.relative_to(REPO_ROOT).as_posix(): path for path in _human_facing_source_files()}
    violations = []
    for relative in PUBLIC_FILES:
        path = tracked.get(relative)
        if path is None:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if "BlobeVM" in line:
                violations.append(f"{relative}:{line_number}: {line.strip()}")
    assert not violations, "Visible legacy public-brand uses:\n" + "\n".join(violations)
