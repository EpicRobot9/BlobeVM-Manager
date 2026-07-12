# Deployment

BlobeVM's production host uses Linux, Docker, KVM, and systemd. Windows is a
supported deployment workstation through Docker Desktop and WSL2; the VM host
backend does not run as a native Windows service.

## Linux production host

Requirements: Ubuntu 22.04 or newer, root access, Node.js 20+, Docker Engine,
Docker Compose v2, and KVM when hardware acceleration is desired.

```bash
# Verify without changing the host
sudo ./scripts/Deploy-Linux.sh --check-only

# Build and deploy
sudo ./scripts/Deploy-Linux.sh

# Verify the installed host
sudo blobe-vm-manager doctor
```

Installer options can be forwarded after `--`.

## Windows deployment workstation

Requirements: Windows 11, Node.js 20+, WSL2 with Ubuntu, Docker Desktop using
the WSL2 backend, Docker Desktop integration enabled for that distribution,
and systemd enabled inside WSL.

```powershell
# Build only the deployable Dashboard v2 bundle
.\scripts\Deploy-Windows.ps1 -DashboardOnly

# Verify the complete path without changing the host
.\scripts\Deploy-Windows.ps1 -CheckOnly

# Deploy through the default WSL distribution
.\scripts\Deploy-Windows.ps1

# Or select a distribution
.\scripts\Deploy-Windows.ps1 -WslDistribution Ubuntu-24.04
```

On a fresh checkout, the Windows script runs `npm ci`; in an active development
checkout it reuses the installed dependency tree so Windows file locks cannot
break deployment while native build binaries are mapped. It always performs a
production dashboard build before handing the full deployment to the supported
Linux installer in WSL2. This catches Windows-only frontend problems without
pretending KVM is a native Windows backend.

## Release contents

- `dashboard_v2/dist/`: checked-in production frontend bundle.
- `scripts/Deploy-Linux.sh`: Linux build, preflight, and installer wrapper.
- `scripts/Deploy-Windows.ps1`: Windows build and WSL2 deployment wrapper.
- `design-qa.md`: visual verification against the selected GPT Image 2 design.

Do not deploy using the development-only `?preview=1` query flag. It is gated
behind Vite development mode and is absent from production builds.
