# EpicVM

EpicVM is a VM platform for creating, running, routing, and maintaining isolated desktop VMs through Docker and a focused web dashboard. It is derived from the DesktopOnCodespaces project and remains focused on VM operations.

> **License and attribution:** EpicVM is distributed under the GNU General Public License, version 3 (GPLv3). Keep the upstream DesktopOnCodespaces attribution and the repository `LICENSE` when copying or redistributing this modified work.

The current repository is still hosted at https://github.com/EpicRobot9/BlobeVM-Manager. A future GitHub rename may follow; links below intentionally use the current URL.

## Quick start

### Codespaces

Open a blank codespace at <https://github.com/codespaces/> and run:

```bash
curl -fsSLO https://raw.githubusercontent.com/EpicRobot9/BlobeVM-Manager/main/install.sh
chmod +x install.sh
./install.sh
```

### Linux host / VPS

The canonical public bootstrap entrypoint is `install-epicvm.sh`:

```bash
curl -fsSL https://raw.githubusercontent.com/EpicRobot9/BlobeVM-Manager/main/install-epicvm.sh | sudo bash
```

The installer deploys the EpicVM VM stack, optional Traefik routing, and the EpicVM Dashboard. Verify the installation with:

```bash
epicvm doctor
epicvm list
```

For a local checkout, use the server installer documented by the repository and then use the `epicvm` CLI. Set `BLOBEVM_NO_TRAEFIK=1` for direct high-port mode, or set `BLOBEVM_INITIAL_VM_NAME=alpha` to choose the starter VM name.

## Manage VMs

```bash
epicvm create alpha
epicvm start alpha
epicvm status alpha
epicvm url alpha
epicvm stop alpha
epicvm delete alpha
epicvm apps
epicvm update-vm alpha
```

See [docs/CLI.md](docs/CLI.md) for the complete command reference and [docs/DASHBOARD_V2.md](docs/DASHBOARD_V2.md) for the EpicVM Dashboard documentation.

## EpicVM Dashboard

The dashboard is a VM management UI served at `/dashboard` (and, for the modern UI, `/Dashboard`). It lists VM state, opens VM URLs, supports lifecycle actions, shows resource information, and exposes EpicVM optimizer controls. It does not replace the VM CLI: use `epicvm doctor` for diagnostics and `epicvm` for automation.

## Compatibility ABI

EpicVM is a public rebrand, not a destructive migration. Existing deployments retain their legacy ABI so they can be upgraded in place:

- `blobe-vm-manager` remains a compatibility alias for the canonical `epicvm` CLI.
- `install-blobevm.sh` remains a compatibility installer alias; new documentation uses `install-epicvm.sh`.
- `/opt/blobe-vm` remains the legacy installation/state root.
- Existing `blobevm_<name>` Docker container names remain valid.
- Existing `BLOBEVM_*` environment variables remain valid, including `BLOBEVM_NO_TRAEFIK`, `BLOBEVM_INITIAL_VM_NAME`, and `BLOBEVM_DIRECT_PORT_START`.
- Existing service IDs `blobedash` and `blobe-optimizer` remain valid.
- Existing routes such as `/dashboard`, `/Dashboard`, `/vm/<name>/`, and their established dashboard API paths remain legacy ABI retained for existing deployments.

Use the EpicVM names for new scripts and documentation, but do not rename these compatibility identifiers on a live installation unless a separate migration explicitly requires it.

## Scope

EpicVM documents VM lifecycle, routing, container resources, dashboard presentation, and VM application maintenance.
