#!/usr/bin/env bash

set -Eeuo pipefail

printf '%s\n' "install-blobevm.sh is deprecated; use install-epicvm.sh (compatibility wrapper)." >&2
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/install-epicvm.sh" "$@"
