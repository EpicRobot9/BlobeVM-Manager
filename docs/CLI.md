# blobe-vm-manager CLI

This is the server-side CLI installed to `/usr/local/bin/blobe-vm-manager` by `server/install.sh`.

## Quick help

```bash
blobe-vm-manager --help
```

## VM naming rules

VM names must be 1-63 chars and match:
- lowercase letters / numbers
- `.` `_` `-`
- must start with a letter or number

Examples:
- valid: `alpha`, `vm-01`, `dev.desktop_2`
- invalid: `MyVM`, `_test`, `vm!`

## Core lifecycle

```bash
blobe-vm-manager list
blobe-vm-manager create <name>
blobe-vm-manager start <name>
blobe-vm-manager stop <name>
blobe-vm-manager restart <name>
blobe-vm-manager status <name>
blobe-vm-manager check <name>
blobe-vm-manager check --no-fix <name>
blobe-vm-manager doctor
blobe-vm-manager delete <name>
blobe-vm-manager rename <old> <new>
```

`doctor` checks the local install and runtime health, including:
- state dir / env file presence
- docker CLI + daemon reachability
- image presence
- Traefik/direct-mode basics
- dashboard container + dashboard URL health
- each VM container and URL reachability

## URL/routing helpers

```bash
blobe-vm-manager url <name>
blobe-vm-manager open <name>
blobe-vm-manager dashboard-url
blobe-vm-manager open-dashboard

blobe-vm-manager set-host <name> <fqdn>
blobe-vm-manager clear-host <name>
blobe-vm-manager set-host-interactive <name>

blobe-vm-manager set-path <name> </prefix>
blobe-vm-manager clear-path <name>

blobe-vm-manager set-base-path </base>
blobe-vm-manager clear-base-path
```

## Direct mode helpers (`NO_TRAEFIK=1`)

```bash
blobe-vm-manager list-ports
blobe-vm-manager port <name>
blobe-vm-manager set-port <name> <port>
```

## Rebuild/update commands

```bash
blobe-vm-manager pull-repo
blobe-vm-manager rebuild-image
blobe-vm-manager recreate-all
blobe-vm-manager recreate <name> [name2 ...]
blobe-vm-manager rebuild-all
blobe-vm-manager rebuild-vms <name> [name2 ...]
blobe-vm-manager update-and-rebuild
blobe-vm-manager update-and-rebuild <name> [name2 ...]
```

## VM maintenance and apps

```bash
blobe-vm-manager update-vm <name>

blobe-vm-manager apps
blobe-vm-manager app-install <name> <app>
blobe-vm-manager app-status <name> <app>
blobe-vm-manager app-uninstall <name> <app>
blobe-vm-manager app-reinstall <name> <app>
```

`apps` lists installer scripts found at:
- `${REPO_DIR}/root/installable-apps/*.sh`
- default fallback: `/opt/blobe-vm/root/installable-apps/*.sh`

## Resource controls

```bash
blobe-vm-manager set-limits <name> <cpu> <mem>
blobe-vm-manager clear-limits <name>
blobe-vm-manager set-title <name> <title>
```

## Destructive commands and non-interactive mode

Both commands are interactive by default and require typed confirmation:

```bash
blobe-vm-manager delete-all-instances
blobe-vm-manager nuke
```

For automation/CI, pass `--yes` to skip prompts:

```bash
blobe-vm-manager delete-all-instances --yes
blobe-vm-manager nuke --yes
```

Use `nuke` carefully: it removes BlobeVM containers, data in `/opt/blobe-vm`, related images/volumes, and the installed CLI.
