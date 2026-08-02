# EpicVM CLI

`epicvm` is the canonical server-side CLI installed by the EpicVM installer. It manages VM instances, routing, resources, applications, and the EpicVM Dashboard. It is not a generic host-administration CLI.

```bash
epicvm --help
epicvm doctor
```

The legacy `blobe-vm-manager` command remains available as a compatibility alias for existing deployments. New automation should use `epicvm`.

## VM naming

Names must be 1–63 characters, start with a lowercase letter or number, and contain only lowercase letters, numbers, `.`, `_`, or `-`.

## Lifecycle and health

```bash
epicvm list
epicvm create <name>
epicvm start <name>
epicvm stop <name>
epicvm restart <name>
epicvm status <name>
epicvm check <name>
epicvm check --no-fix <name>
epicvm doctor
epicvm delete <name>
epicvm rename <old> <new>
```

`doctor` checks the EpicVM installation, Docker reachability, image, routing mode, dashboard, and VM URL health.

## URLs and routing

```bash
epicvm url <name>
epicvm open <name>
epicvm dashboard-url
epicvm open-dashboard
epicvm set-host <name> <fqdn>
epicvm clear-host <name>
epicvm set-host-interactive <name>
epicvm set-path <name> /prefix
epicvm clear-path <name>
epicvm set-base-path /desktops
epicvm clear-base-path
```

## Direct mode

When `BLOBEVM_NO_TRAEFIK=1` is set, use high-port helpers:

```bash
epicvm list-ports
epicvm port <name>
epicvm set-port <name> <port>
```

## Rebuild, update, and apps

```bash
epicvm pull-repo
epicvm rebuild-image
epicvm recreate-all
epicvm recreate <name> [name2 ...]
epicvm rebuild-all
epicvm rebuild-vms <name> [name2 ...]
epicvm update-and-rebuild [name ...]
epicvm update-vm <name>
epicvm apps
epicvm app-install <name> <app>
epicvm app-status <name> <app>
epicvm app-uninstall <name> <app>
epicvm app-reinstall <name> <app>
```

Application scripts live in `root/installable-apps/*.sh` in the checkout. Existing deployments may use `/opt/blobe-vm/root/installable-apps/*.sh`.

## RemoteVM host enrollment

The optional `epicvm-remote-host` helper manages the server-side Windows/Hyper-V host registry. It writes an atomic `0600` JSON file and never includes the bearer token in command output. Generate a protected token file when needed, then pass it to `add`:

```bash
epicvm-remote-host token-generate --output /run/epicvm/agent.token
epicvm-remote-host setup
# Or use add --token-file for scripted/non-interactive enrollment
epicvm-remote-host add win-gaming "Windows Gaming PC" http://100.64.12.34:8765 --token-file /run/epicvm/agent.token
epicvm-remote-host probe win-gaming
epicvm-remote-host disable win-gaming
epicvm-remote-host enable win-gaming
epicvm-remote-host show win-gaming
epicvm-remote-host remove win-gaming
```

Set `EPICVM_REMOTE_HOSTS_FILE` (or the compatibility alias `BLOBEVM_REMOTE_HOSTS_FILE`) or pass `--registry` when the default `/opt/blobe-vm/remote-hosts.json` is not suitable. The registry accepts Tailscale `100.64.0.0/10` addresses and `*.ts.net` names by default; `EPICVM_ALLOW_NON_TAILSCALE_HOSTS=1` is a development-only escape hatch.

## Resources and destructive operations

```bash
epicvm set-limits <name> <cpu> <memory>
epicvm clear-limits <name>
epicvm set-title <name> <title>
epicvm delete-all-instances --yes
epicvm nuke --yes
```

Destructive commands prompt for confirmation unless `--yes` is supplied. `nuke` removes EpicVM containers, legacy state under `/opt/blobe-vm`, related images/volumes, and the installed CLI.

## Compatibility ABI

The following names are intentionally retained for existing deployments: `blobe-vm-manager`, `install-blobevm.sh`, `/opt/blobe-vm`, `blobevm_<name>` container names, `BLOBEVM_*` variables, service IDs `blobedash` and `blobe-optimizer`, and old routes `/dashboard`, `/Dashboard`, and `/vm/<name>/`. They are legacy ABI, not the preferred product-facing names. The canonical installer is `install-epicvm.sh`.
