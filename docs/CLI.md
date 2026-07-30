# epicvm CLI

This is the canonical server-side CLI installed to `/usr/local/bin/epicvm` by `server/install.sh`.
The legacy `/usr/local/bin/blobe-vm-manager` command remains available as a compatibility launcher.

## Quick help

```bash
epicvm --help
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

`doctor` checks the local install and runtime health, including:
- state dir / env file presence
- docker CLI + daemon reachability
- image presence
- Traefik/direct-mode basics
- dashboard container + dashboard URL health
- each VM container and URL reachability

## URL/routing helpers

```bash
epicvm url <name>
epicvm open <name>
epicvm dashboard-url
epicvm open-dashboard

epicvm set-host <name> <fqdn>
epicvm clear-host <name>
epicvm set-host-interactive <name>

epicvm set-path <name> </prefix>
epicvm clear-path <name>

epicvm set-base-path </base>
epicvm clear-base-path
```

## Direct mode helpers (`NO_TRAEFIK=1`)

```bash
epicvm list-ports
epicvm port <name>
epicvm set-port <name> <port>
```

## Rebuild/update commands

```bash
epicvm pull-repo
epicvm rebuild-image
epicvm recreate-all
epicvm recreate <name> [name2 ...]
epicvm rebuild-all
epicvm rebuild-vms <name> [name2 ...]
epicvm update-and-rebuild
epicvm update-and-rebuild <name> [name2 ...]
```

## VM maintenance and apps

```bash
epicvm update-vm <name>

epicvm apps
epicvm app-install <name> <app>
epicvm app-status <name> <app>
epicvm app-uninstall <name> <app>
epicvm app-reinstall <name> <app>
```

`apps` lists installer scripts found at:
- `${REPO_DIR}/root/installable-apps/*.sh`
- default fallback: `/opt/blobe-vm/root/installable-apps/*.sh`

## Resource controls

```bash
epicvm set-limits <name> <cpu> <mem>
epicvm clear-limits <name>
epicvm set-title <name> <title>
```

## Destructive commands and non-interactive mode

Both commands are interactive by default and require typed confirmation:

```bash
epicvm delete-all-instances
epicvm nuke
```

For automation/CI, pass `--yes` to skip prompts:

```bash
epicvm delete-all-instances --yes
epicvm nuke --yes
```

Use `nuke` carefully: it removes BlobeVM containers, data in `/opt/blobe-vm`, related images/volumes, and the installed CLI.
