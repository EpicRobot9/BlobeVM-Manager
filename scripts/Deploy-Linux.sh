#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage: sudo ./scripts/Deploy-Linux.sh [--check-only] [-- installer options]

Builds the checked-in dashboard release and runs the supported BlobeVM Linux
installer. Arguments after -- are forwarded to server/install.sh.
EOF
}

CHECK_ONLY=0
INSTALL_ARGS=()
while (($#)); do
  case "$1" in
    --check-only) CHECK_ONLY=1; shift ;;
    --help|-h) usage; exit 0 ;;
    --) shift; INSTALL_ARGS=("$@"); break ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for command_name in bash node npm docker; do
  command -v "$command_name" >/dev/null 2>&1 || { echo "Missing required command: $command_name" >&2; exit 1; }
done
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required (docker compose)." >&2; exit 1; }

echo "Building Dashboard v2 release..."
(cd "$ROOT_DIR/dashboard_v2" && npm ci --no-audit --no-fund && npm run build)

if ((CHECK_ONLY)); then
  echo "Linux deployment preflight passed. No host changes were made."
  exit 0
fi
if ((EUID != 0)); then
  echo "Deployment requires root. Re-run with sudo." >&2
  exit 1
fi

echo "Running supported Linux installer..."
exec bash "$ROOT_DIR/server/install.sh" "${INSTALL_ARGS[@]}"
