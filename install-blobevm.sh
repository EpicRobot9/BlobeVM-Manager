#!/usr/bin/env bash

set -Eeuo pipefail

SCRIPT_NAME="${0##*/}"
BRANCH="${BLOBEVM_BRANCH:-main}"
REPO_URL="${BLOBEVM_REPO_URL:-https://github.com/EpicRobot9/BlobeVM.git}"
INSTALL_ROOT="${BLOBEVM_ROOT:-/opt/blobe-vm}"
REPO_DIR="${INSTALL_ROOT}/repo"
INSTALLER_REL="server/install.sh"
LOGFILE="${BLOBEVM_BOOTSTRAP_LOG:-/var/log/blobe-vm-bootstrap.log}"
ASSUME_YES=0
SKIP_PULL=0
DRY_RUN=0
INSTALLER_ARGS=()

handle_error() {
  local exit_code=$?
  local line=$1
  local cmd=$2
  printf '\n[ERROR] %s failed at line %s: %s\n' "$SCRIPT_NAME" "$line" "$cmd" >&2
  printf 'See %s for full logs.\n' "$LOGFILE" >&2
  exit "$exit_code"
}
trap 'handle_error ${LINENO} "${BASH_COMMAND}"' ERR

supports_color() {
  [[ -t 1 && -z "${NO_COLOR:-}" && $(tput colors 2>/dev/null || echo 0) -ge 8 ]]
}
if supports_color; then
  C_RESET='\033[0m'
  C_BOLD='\033[1m'
  C_INFO='\033[1;34m'
  C_WARN='\033[1;33m'
  C_GOOD='\033[1;32m'
else
  C_RESET=''
  C_BOLD=''
  C_INFO=''
  C_WARN=''
  C_GOOD=''
fi

say() { printf '%b%s%b\n' "$C_INFO" "$1" "$C_RESET"; }
success() { printf '%b%s%b\n' "$C_GOOD" "$1" "$C_RESET"; }
warn() { printf '%b%s%b\n' "$C_WARN" "$1" "$C_RESET"; }
die() { printf '%s\n' "$1" >&2; exit 1; }

usage() {
  cat <<USAGE
${SCRIPT_NAME} [options] [-- installer-args]

Clone or update the BlobeVM repository and invoke server/install.sh.

Options:
  -b, --branch <name>     Git branch (default: ${BRANCH})
  -r, --repo <url>        Repository URL (default: ${REPO_URL})
  -d, --dest <path>       Installation root (default: ${INSTALL_ROOT})
  -y, --yes               Assume yes for prompts
      --skip-pull         Skip git fetch/reset if repo exists
      --dry-run           Show plan then exit
  -h, --help              Show this help

Any arguments after -- are passed to server/install.sh.
USAGE
}

parse_args() {
  local positional=()
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -b|--branch) [[ $# -lt 2 ]] && die "Missing value for $1"; BRANCH="$2"; shift 2 ;;
      -r|--repo) [[ $# -lt 2 ]] && die "Missing value for $1"; REPO_URL="$2"; shift 2 ;;
      -d|--dest) [[ $# -lt 2 ]] && die "Missing value for $1"; INSTALL_ROOT="$2"; REPO_DIR="${INSTALL_ROOT}/repo"; shift 2 ;;
      -y|--yes) ASSUME_YES=1; shift ;;
      --skip-pull) SKIP_PULL=1; shift ;;
      --dry-run) DRY_RUN=1; shift ;;
      -h|--help) usage; exit 0 ;;
      --) shift; INSTALLER_ARGS=("$@"); return ;;
      *) positional+=("$1"); shift ;;
    esac
  done
  if [[ ${#positional[@]} -gt 0 ]]; then
    INSTALLER_ARGS=("${positional[@]}")
  fi
}

ensure_logfile() {
  mkdir -p "$(dirname "$LOGFILE")"
  touch "$LOGFILE"
  chmod 600 "$LOGFILE" 2>/dev/null || true
  exec > >(tee -a "$LOGFILE") 2>&1
  say "Logging to $LOGFILE"
}

reexec_as_root() {
  if [[ $EUID -eq 0 ]]; then
    return
  fi
  if ! command -v sudo >/dev/null 2>&1; then
    die "This installer must run as root or with sudo access."
  fi
  say "Re-running with sudo..."
  exec sudo -E bash "$0" "$@"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_git_if_missing() {
  if need_cmd git; then
    return
  fi
  if need_cmd apt-get; then
    say "Installing git via apt-get..."
    apt-get update -y
    apt-get install -y git ca-certificates
  else
    die "git is required. Install git manually and rerun."
  fi
}

describe_plan() {
  cat <<PLAN
Configuration:
  Repo URL   : ${REPO_URL}
  Branch     : ${BRANCH}
  Install dir: ${INSTALL_ROOT}
  Log file   : ${LOGFILE}
PLAN
}

confirm_or_exit() {
  if [[ $ASSUME_YES -eq 1 ]]; then
    return
  fi
  read -rp "Proceed with these settings? [Y/n] " reply || true
  if [[ ${reply,,} =~ ^n|no$ ]]; then
    die "Aborted by user."
  fi
}

clone_or_update_repo() {
  mkdir -p "$INSTALL_ROOT"
  if [[ -d "$REPO_DIR/.git" ]]; then
    if [[ $SKIP_PULL -eq 1 ]]; then
      say "Using existing repository at $REPO_DIR (skip-pull enabled)."
      return
    fi
    say "Updating repository at $REPO_DIR..."
    (cd "$REPO_DIR" && git fetch --force origin "$BRANCH" && git reset --hard "origin/$BRANCH")
  else
    say "Cloning repository into $REPO_DIR..."
    rm -rf "$REPO_DIR"
    git clone --branch "$BRANCH" --depth 1 "$REPO_URL" "$REPO_DIR"
  fi
}

ensure_installer_present() {
  INSTALLER_PATH="${REPO_DIR}/${INSTALLER_REL}"
  if [[ -f "$INSTALLER_PATH" ]]; then
    return
  fi
  warn "Installer script missing locally; attempting recovery."
  if git -C "$REPO_DIR" cat-file -e "origin/${BRANCH}:${INSTALLER_REL}" 2>/dev/null; then
    git -C "$REPO_DIR" show "origin/${BRANCH}:${INSTALLER_REL}" > "$INSTALLER_PATH"
  elif git -C "$REPO_DIR" cat-file -e "HEAD:${INSTALLER_REL}" 2>/dev/null; then
    git -C "$REPO_DIR" show "HEAD:${INSTALLER_REL}" > "$INSTALLER_PATH"
  else
    die "Unable to locate ${INSTALLER_REL} in repository."
  fi
  chmod +x "$INSTALLER_PATH"
}

run_main_installer() {
  say "Delegating to ${INSTALLER_REL}..."
  chmod +x "$INSTALLER_PATH" 2>/dev/null || true
  exec bash "$INSTALLER_PATH" "${INSTALLER_ARGS[@]}"
}


parse_args "$@"
reexec_as_root "$@"
ensure_logfile
describe_plan
confirm_or_exit

# Default: disable Traefik unless explicitly set
export BLOBEVM_NO_TRAEFIK="${BLOBEVM_NO_TRAEFIK:-1}"

install_git_if_missing
need_cmd curl || warn "curl not detected; downstream installer may install it."
need_cmd wget || warn "wget not detected; downstream installer may install it."
clone_or_update_repo
ensure_installer_present

# Install kasm tuning components on the host so a single curl|bash deploy includes them.
install_kasm_tune_components() {
  say "Installing Kasm tuning components (host + container-aware)..."

  # Helper to write files safely
  write_file() {
    local dest="$1"; shift
    mkdir -p "$(dirname "$dest")"
    cat > "$dest" <<'EOF'
$*
EOF
  }

  # Create host tuner
  mkdir -p /usr/local/bin
  cat >/usr/local/bin/kasm_tune.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# kasm_tune.sh
# Finds GUI/Kasm browser processes owned by `kasmuser` and:
# - applies cpulimit (60%) to browser PIDs (if cpulimit installed)
# - renices to lower CPU priority (+10)
# - sets low I/O priority (ionice -c2 -n7)
# Logs to /var/log/kasm_tune.log and to syslog (tag=kasm_tune)

LOG=/var/log/kasm_tune.log
KASM_USER=kasmuser
CPU_LIMIT=60

touch "$LOG" 2>/dev/null || true
exec 3>>"$LOG"

log() {
  local msg="$*"
  echo "$(date -Is) $msg" >&3 || true
  logger -t kasm_tune -- "$msg" || true
}

CPULIMIT_BIN="$(command -v cpulimit || true)"

# Patterns to match executable name or cmdline for browsers and common KDE GUI components
BROWSER_PATTERN='firefox|firefox-esr|chrome|chromium|google-chrome|chromium-browser'
GUI_PATTERN='plasmashell|kwin|kwin_x11|kwin_wayland|plasmashell|startplasma'

log "kasm_tune: starting scan for user $KASM_USER"

# Get PIDs owned by KASM_USER; pgrep returns non-zero if none found, so use || true
for pid in $(pgrep -u "$KASM_USER" 2>/dev/null || true); do
  # ensure /proc exists for PID (skip zombies/kernel threads)
  if [ ! -d "/proc/$pid" ]; then
    continue
  fi

  # Obtain command name and full cmdline (lowercased for matching)
  cmd="$(ps -p "$pid" -o comm= 2>/dev/null || true)"
  cmdline="$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null || true)"
  match_source="$cmd $cmdline"
  match_source_lc="$(echo "$match_source" | tr '[:upper:]' '[:lower:]')"

  if echo "$match_source_lc" | grep -Eiq "$BROWSER_PATTERN|$GUI_PATTERN"; then
    # Apply renice (+10) to lower CPU scheduling priority
    if renice +10 -p "$pid" >/dev/null 2>&1; then
      log "reniced pid=$pid cmd='$cmd'"
    else
      log "warning: renice failed for pid=$pid cmd='$cmd'"
    fi

    # Apply low I/O priority if ionice exists
    if command -v ionice >/dev/null 2>&1; then
      if ionice -c2 -n7 -p "$pid" >/dev/null 2>&1; then
        log "ioniced pid=$pid cmd='$cmd'"
      else
        log "warning: ionice failed for pid=$pid cmd='$cmd'"
      fi
    fi

    # Apply cpulimit only for browser-like commands
    if echo "$match_source_lc" | grep -Eiq "$BROWSER_PATTERN"; then
      if [ -n "$CPULIMIT_BIN" ]; then
        # Avoid duplicating cpulimit instances for the same PID
        if ! pgrep -af "cpulimit" 2>/dev/null | grep -E "-p[[:space:]]*$pid|-p$pid" >/dev/null 2>&1; then
          # Use cpulimit's background mode (-b) so it detaches and persists until the process exits
          if "$CPULIMIT_BIN" -p "$pid" -l "$CPU_LIMIT" -b >/dev/null 2>&1; then
            log "started cpulimit pid=$pid limit=${CPU_LIMIT}% cmd='$cmd'"
          else
            log "warning: failed to start cpulimit for pid=$pid cmd='$cmd'"
          fi
        else
          log "cpulimit already present for pid=$pid cmd='$cmd'"
        fi
      else
        log "cpulimit not installed; skipping cpulimit for pid=$pid cmd='$cmd'"
      fi
    fi
  fi
done

log "kasm_tune: scan complete"

exit 0
EOF
  chmod 0755 /usr/local/bin/kasm_tune.sh || true

  # Container tuner
  cat >/usr/local/bin/kasm_tune_containers.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# kasm_tune_containers.sh
# Find running Docker containers that look like Kasm instances and:
# - apply docker resource limits (cpus + memory)
# - exec into the container to renice/ionice browser and KDE processes
# - attempt to run cpulimit inside container if available
# Logs to /var/log/kasm_tune_containers.log and syslog (tag=kasm_tune_cont)

LOG=/var/log/kasm_tune_containers.log
CPU_LIMIT_PER_BROWSER=60
CONTAINER_CPU=1.5
CONTAINER_MEM=6g
CONTAINER_PATTERNS='kasm|kasmvnc|kasmvnc|blobevm'

touch "$LOG" 2>/dev/null || true
exec 3>>"$LOG"

log() {
  local msg="$*"
  echo "$(date -Is) $msg" >&3 || true
  logger -t kasm_tune_cont -- "$msg" || true
}

if ! command -v docker >/dev/null 2>&1; then
  log "docker CLI not found; skipping container tuning"
  exit 0
fi

log "kasm_tune_containers: scanning containers for patterns: $CONTAINER_PATTERNS"

docker ps --format '{{.ID}} {{.Names}} {{.Image}}' | while read -r id name image; do
  sn="$name $image"
  if echo "$sn" | tr '[:upper:]' '[:lower:]' | grep -Eiq "$CONTAINER_PATTERNS"; then
    log "found candidate container id=$id name=$name image=$image"

    # Apply docker update limits (idempotent)
    if docker update --cpus "$CONTAINER_CPU" --memory "$CONTAINER_MEM" "$id" >/dev/null 2>&1; then
      log "docker update applied to $name ($id): cpus=$CONTAINER_CPU memory=$CONTAINER_MEM"
    else
      log "warning: docker update failed for $name ($id)"
    fi

    # Build a small in-container tuning command
    tune_cmd=''
    tune_cmd+="# find browser and GUI PIDs (try user kasmuser, fallback to any matches)\n"
    tune_cmd+="pids=\$(pgrep -u kasmuser -f 'firefox|chrome|chromium|chromium-browser' 2>/dev/null || true)\n"
    tune_cmd+="if [ -z \"\$pids\" ]; then pids=\$(pgrep -f 'firefox|chrome|chromium|chromium-browser|plasmashell|kwin' 2>/dev/null || true); fi\n"
    tune_cmd+="for pid in \$pids; do\n"
    tune_cmd+="  [ -z \"\$pid\" ] && continue\n"
    tune_cmd+="  renice +10 -p \$pid >/dev/null 2>&1 || true\n"
    tune_cmd+="  if command -v ionice >/dev/null 2>&1; then ionice -c2 -n7 -p \$pid >/dev/null 2>&1 || true; fi\n"
    tune_cmd+="  if command -v cpulimit >/dev/null 2>&1; then cpulimit -p \$pid -l $CPU_LIMIT_PER_BROWSER -b >/dev/null 2>&1 || true; fi\n"
    tune_cmd+="done\n"

    # Execute tuning inside the container as root
    if docker exec "$id" /bin/sh -lc "$tune_cmd" >/dev/null 2>&1; then
      log "in-container tuning executed for $name ($id)"
    else
      log "warning: in-container tuning failed for $name ($id)"
    fi
  fi
done

log "kasm_tune_containers: scan complete"

exit 0
EOF
  chmod 0755 /usr/local/bin/kasm_tune_containers.sh || true

  # Wrapper
  cat >/usr/local/bin/kasm_tune_wrapper.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run both host and container tuners for Kasm GUI
LOG=/var/log/kasm_tune.log
exec 3>>"$LOG" || true
echo "$(date -Is) kasm_tune_wrapper: running host and container tuners" >&3 || true

if [ -x /usr/local/bin/kasm_tune.sh ]; then
  /usr/local/bin/kasm_tune.sh || true
fi

if [ -x /usr/local/bin/kasm_tune_containers.sh ]; then
  /usr/local/bin/kasm_tune_containers.sh || true
fi

echo "$(date -Is) kasm_tune_wrapper: done" >&3 || true
exit 0
EOF
  chmod 0755 /usr/local/bin/kasm_tune_wrapper.sh || true

  # Systemd unit, timer, slice, override
  mkdir -p /etc/systemd/system/kasm-workspaces.service.d
  cat >/etc/systemd/system/kasm-tune.service <<'EOF'
[Unit]
Description=Kasm GUI tuning service (host + container-aware)
Wants=kasm.slice
After=network.target docker.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/kasm_tune_wrapper.sh
User=root
Group=root

[Install]
WantedBy=multi-user.target
EOF

  cat >/etc/systemd/system/kasm-tune.timer <<'EOF'
[Unit]
Description=Run kasm-tune every minute

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
Persistent=true

[Install]
WantedBy=timers.target
EOF

  cat >/etc/systemd/system/kasm.slice <<'EOF'
[Unit]
Description=Slice for Kasm GUI processes to constrain resources

[Slice]
# Limit memory used by all units in this slice to 6GB
MemoryMax=6G
# Allow up to 150% CPU across CPUs for the entire slice
CPUQuota=150%
EOF

  cat >/etc/systemd/system/kasm-workspaces.service.d/override.conf <<'EOF'
[Service]
# Ensure the kasm-workspaces service (the main Kasm systemd service) runs in kasm.slice
# This applies the MemoryMax and CPUQuota limits to the entire Kasm stack managed by that service.
Slice=kasm.slice
EOF

  # Make sure cpulimit is installed on the host (idempotent)
  if need_cmd apt-get; then
    if ! need_cmd cpulimit; then
      say "Installing cpulimit on host for browser limiting..."
      apt-get update -y && apt-get install -y cpulimit || warn "Failed to apt-install cpulimit; host cpulimit will be skipped"
    fi
  else
    warn "apt-get not available; cannot auto-install cpulimit on host"
  fi

  # Reload systemd and enable timer
  systemctl daemon-reload || true
  systemctl enable --now kasm-tune.timer || warn "Failed to enable kasm-tune.timer"

  # Apply docker updates to running containers matching common patterns
  if need_cmd docker; then
    CONTAINER_PATTERNS='kasm|kasmvnc|blobevm'
    CONTAINER_CPU=1.5
    CONTAINER_MEM=6g
    docker ps --format '{{.ID}} {{.Names}} {{.Image}}' | while read -r id name image; do
      sn="$name $image"
      if echo "$sn" | tr '[:upper:]' '[:lower:]' | grep -Eiq "$CONTAINER_PATTERNS"; then
        say "Applying docker update to $name ($id): cpus=$CONTAINER_CPU memory=$CONTAINER_MEM"
        docker update --cpus "$CONTAINER_CPU" --memory "$CONTAINER_MEM" "$id" || warn "docker update failed for $name ($id)"
      fi
    done
  fi

  say "Kasm tuning components installed. See /var/log/kasm_tune.log and /var/log/kasm_tune_containers.log"
}

install_kasm_tune_components

# Detect code changes: compare repo HEAD to installed files
CHANGED=0
if [[ -d "$INSTALL_ROOT" && -d "$REPO_DIR/.git" ]]; then
  REPO_HASH=$(cd "$REPO_DIR" && git rev-parse HEAD)
  INST_HASH_FILE="$INSTALL_ROOT/.last_install_hash"
  LAST_HASH=""
  [[ -f "$INST_HASH_FILE" ]] && LAST_HASH=$(cat "$INST_HASH_FILE")
  if [[ "$REPO_HASH" != "$LAST_HASH" ]]; then
    CHANGED=1
    echo "$REPO_HASH" > "$INST_HASH_FILE"
  fi
fi

if [[ $DRY_RUN -eq 1 && $CHANGED -eq 0 ]]; then
  warn "Dry run: no changes were made."
  exit 0
fi

run_main_installer
