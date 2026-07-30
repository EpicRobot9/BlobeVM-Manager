import os
import subprocess
from pathlib import Path


REPO = Path(__file__).parents[1]
CANONICAL = REPO / "server" / "epicvm"
LEGACY = REPO / "server" / "blobe-vm-manager"


def run_cli(cli, *args):
    env = os.environ.copy()
    env["STATE_DIR"] = str(REPO / ".pytest-epicvm-state")
    return subprocess.run(
        [str(cli), *args],
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_epicvm_is_the_canonical_executable_and_names_help_epicvm():
    result = run_cli(CANONICAL, "--help")

    assert result.returncode == 0
    assert "Usage: epicvm <command> [args]" in result.stderr


def test_legacy_launcher_preserves_legacy_help_name():
    result = run_cli(LEGACY, "--help")

    assert result.returncode == 0
    assert "Usage: blobe-vm-manager <command> [args]" in result.stderr


def test_legacy_launcher_execs_canonical_sibling_without_copying_implementation():
    launcher = LEGACY.read_text()

    assert 'exec "$SCRIPT_DIR/epicvm" "$@"' in launcher
    assert len(launcher.splitlines()) <= 12
