# BlobeVM-Manager context refresh — 2026-03-13

## What was done

### Live fixes completed
1. **Restored VM type/profile control in Dashboard v2**
   - Re-added VM type selector to VM cards.
   - Uses existing optimizer profile API.

2. **Fixed Dashboard v2 optimizer logs viewer**
   - UI was reading optimizer logs as JSON instead of plain text.
   - Now reads plain text properly.

3. **Fixed optimizer memory/swap stats collection**
   - Optimizer was calling `free -b` and failing because `free` was missing in the runtime.
   - Added fallback to `/proc/meminfo`.
   - Updated swap guard to use shared stats instead of calling `free` directly.

4. **Fixed bogus optimizer health behavior**
   - VM subdomains like `alpha.techexplore.us` and `epic.techexplore.us` do not currently resolve.
   - Health checks were incorrectly treating DNS failure / curl failure as VM failure.
   - Added multi-probe health fallback logic so the optimizer can validate VMs through the proxy path route.
   - Final working fallback from inside the dashboard container: `https://172.18.0.1/vm/<name>/`.

5. **Changed live VM URLs to path-based fallbacks when subdomain DNS is missing**
   - `blobe-vm-manager` now prefers `https://techexplore.us/vm/<name>/` when `<name>.techexplore.us` does not resolve.
   - Dashboard API list now also reflects those working URLs after service restart.

6. **Cleared stale optimizer logs**
   - Truncated `/var/blobe/logs/optimizer/optimizer.log`.

7. **Fixed empty optimizer logs response**
   - `/dashboard/api/optimizer/logs` now returns `200 text/plain` with empty content instead of `404 {"error":"no logs"}`.

### Installer / onboarding improvements completed
8. **Improved one-shot onboarding**
   - `server/quick-install.sh` now defaults to one-shot mode:
     - `BLOBEVM_ASSUME_DEFAULTS=1`
     - `BLOBEVM_ENABLE_DASHBOARD=1`
     - `BLOBEVM_AUTO_CREATE_VM=1`
     - `BLOBEVM_INITIAL_VM_NAME=testvm`

9. **Improved final install summary**
   - `server/install.sh` now prints:
     - Dashboard v2 link
     - Old dashboard link
     - Test VM link

10. **Fixed installer repo references**
    - Entry points were still cloning or referencing the old `EpicRobot9/BlobeVM` repo in some places.
    - Updated installer/bootstrap references to `EpicRobot9/BlobeVM-Manager` where appropriate.

## Important diagnosis/results
- **Wildcard/subdomain DNS is missing** for `*.techexplore.us`.
- Root domain resolves, VM subdomains do not.
- Path-based routing via Traefik works:
  - `/vm/alpha/` returns 200
  - `/vm/epic/` returns 200
- Host-based VM URLs should not be trusted until wildcard/per-VM DNS is added.

## Services/runtime notes
- Optimizer is **embedded in the Flask dashboard process**, not a separate optimizer service.
- Relevant runtime service:
  - `blobedash.service`
- Live dashboard code is bind-mounted from:
  - `/opt/blobe-vm/dashboard`
  - `/opt/blobe-vm/dashboard_v2`
- The repo working copy is:
  - `/root/.openclaw/workspace/BlobeVM-Manager`
- Restarting only the service is not enough if repo changes are not synced into `/opt/blobe-vm/...`.

## Files most relevant for future work

### Runtime/live paths
- `/opt/blobe-vm/dashboard/app.py`
- `/opt/blobe-vm/dashboard/optimizer.py`
- `/opt/blobe-vm/dashboard_v2/src/pages/Logs.jsx`
- `/opt/blobe-vm/dashboard_v2/src/pages/VMManager.jsx`
- `/opt/blobe-vm/server/blobe-vm-manager`
- `/var/blobe/logs/optimizer/optimizer.log`
- `/opt/blobe-vm/.env`

### Repo/source paths
- `dashboard/app.py`
- `dashboard/optimizer.py`
- `dashboard_v2/src/pages/Logs.jsx`
- `dashboard_v2/src/pages/VMManager.jsx`
- `server/blobe-vm-manager`
- `server/install.sh`
- `server/quick-install.sh`
- `install-blobevm.sh`
- `README.md`

## Key commits from this work
- `aa5dd19` — Fix optimizer logs viewer and restore VM type control
- `0c9bc77` — Make optimizer health checks tolerate DNS/path routing
- `332f2ba` — Use proxy gateway fallback for optimizer health checks
- `78932ad` — Try both HTTP and HTTPS for health fallback probes
- `c87d50d` — Prefer path URLs when VM subdomains do not resolve
- `0bd7cd3` — Return empty optimizer logs as plain text instead of 404
- `39460de` — Improve one-shot onboarding and dashboard/test VM links

## Still worth doing later
1. Add wildcard DNS in Cloudflare:
   - `A *.techexplore.us -> server IPv4`
   - optional `AAAA *.techexplore.us -> server IPv6`
2. Optionally verify the live UI in a real browser after DNS is fixed.
3. Consider log rotation for optimizer logs if they grow quickly again.
4. Consider whether old `install.sh` should be further modernized or deprecated in favor of the server installer path.

## Short resend summary
Use this if you want to rehydrate context later:

> We fixed BlobeVM-Manager dashboard/optimizer issues on 2026-03-13. Main fixes: restored VM type selector in Dashboard v2, fixed optimizer logs viewer, fixed optimizer `free` dependency by using `/proc/meminfo`, fixed bogus health restarts caused by missing VM subdomain DNS, made URL output prefer path-based links like `/vm/<name>/` when wildcard DNS is missing, and improved one-shot installer onboarding so quick-install creates `testvm` and prints links for Dashboard v2, old dashboard, and the test VM. Main files: `dashboard/app.py`, `dashboard/optimizer.py`, `dashboard_v2/src/pages/Logs.jsx`, `dashboard_v2/src/pages/VMManager.jsx`, `server/blobe-vm-manager`, `server/install.sh`, `server/quick-install.sh`, `install-blobevm.sh`, `README.md`. Live runtime paths are under `/opt/blobe-vm/...` and optimizer logs are at `/var/blobe/logs/optimizer/optimizer.log`.
