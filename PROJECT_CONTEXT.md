# EpicVM Project Context

- **Product:** EpicVM VM platform
- **Status:** active
- **Current repository:** https://github.com/EpicRobot9/BlobeVM-Manager
- **Future rename:** the GitHub repository may be renamed later; it has not been renamed yet.

## Purpose

EpicVM is a Docker-based VM platform with a web dashboard and CLI for creating, routing, monitoring, and maintaining isolated desktop VMs. It is derived from DesktopOnCodespaces and remains under the GNU General Public License version 3 (GPLv3); see `LICENSE` for the complete license text and preserve upstream attribution.

## Stack

- Docker-based VM lifecycle management
- EpicVM Dashboard (legacy and modern UI routes)
- VM routing through Traefik or direct high-port mode
- VM-focused optimizer components
- Shell and Python installation tooling

## Compatibility contract

Existing deployments continue to use the legacy ABI: `blobe-vm-manager`, `install-blobevm.sh`, `/opt/blobe-vm`, `blobevm_<name>` container names, `BLOBEVM_*` variables, service IDs `blobedash` and `blobe-optimizer`, and established routes such as `/dashboard`, `/Dashboard`, and `/vm/<name>/`. These identifiers are retained for compatibility; new public-facing documentation uses EpicVM and `epicvm`.
