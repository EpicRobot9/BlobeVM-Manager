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

## Additional work completed later the same day

### Repo/docs/CLI improvements
11. **Improved `blobe-vm-manager` CLI and docs**
   - Added working help entrypoints: `help`, `-h`, `--help`.
   - Wired previously missing `update-vm` command into dispatcher.
   - Added `apps` command to list installable app scripts.
   - Added `--yes` automation flags for `delete-all-instances` and `nuke`.
   - Added VM name validation for create/rename.
   - Added new CLI reference doc: `docs/CLI.md`.
   - Cleaned up `README.md` formatting and synced it with the CLI behavior.

12. **Pushed repo updates to GitHub**
   - Pushed through commit `7021975` at that stage.

### Optimizer density planning work
13. **Added optimizer density profiles + custom capacity controls**
   - Added built-in density profiles:
     - `single-user`
     - `small-group`
     - `multi-user`
   - Added custom capacity tuning fields:
     - host CPU soft/hard limits
     - minimum available RAM reserve
     - max swap percent
     - per-gaming-VM CPU/RAM budget
     - per-interactive-VM CPU/RAM budget
   - Added API to apply density profiles and exposed profile metadata in optimizer summary.
   - Added Dashboard v2 Optimizer UI controls for preset dropdown + custom mode.

14. **Deployed updated dashboard/optimizer live to server**
   - Synced repo code into `/opt/blobe-vm/...`
   - Rebuilt `dashboard_v2`
   - Restarted `blobedash.service`

### Dashboard v2 VM Manager expansion
15. **Expanded Dashboard v2 VM Manager**
   - Added create-VM form.
   - Added delete-VM support.
   - Added per-VM Manage modal.
   - Added per-VM settings support for:
     - custom host/domain override
     - browser tab title
     - per-VM favicon upload

16. **Fixed VM settings race condition**
   - Saving title + host override caused overlapping recreates and Docker container name conflicts.
   - Changed flow so VM metadata is updated first, then a single recreate is triggered.

### Favicon debugging/results
17. **Tried multiple favicon delivery fixes**
   - Disabled favicon caching headers.
   - Added multiple wrapper favicon link tags (`icon`, `shortcut icon`, `apple-touch-icon`).
   - Re-applied favicon links from wrapper JavaScript on load.
   - Switched wrapper to use extensionless VM favicon URLs instead of fake `.ico` URLs.
   - Fixed server MIME detection so uploaded PNG favicons are served as `image/png` instead of being mislabeled as ICO.

18. **Current favicon status**
   - Upload state is saved correctly.
   - Dashboard UI detects the uploaded VM favicon correctly.
   - Wrapper HTML points at the correct per-VM favicon URL.
   - Live server now serves the actual uploaded file with no-cache headers and correct MIME type.
   - **However, the VM tab favicon still does not visibly update in the browser** even after hard refresh/incognito.
   - This remains unresolved and likely needs either:
     - true server-side conversion to a real `.ico`, or
     - deeper browser-specific favicon behavior testing.

## Important newer commits from this later work
- `15c439c` — Improve blobe-vm-manager CLI UX and document new commands
- `7021975` — Tidy README formatting and sync CLI docs references
- `8e9c917` — Add optimizer density profiles and custom capacity controls
- `e1572cb` — Expand Dashboard v2 VM manager controls
- `a666ffa` — Fix VM settings update race in Dashboard v2
- `7992db0` — Disable favicon caching for VM wrapper tabs
- `78eaf2d` — Force VM wrapper tabs to refresh favicon links
- `3a4a184` — Serve uploaded VM favicons with correct MIME types
- `336e783` — Use extensionless VM favicon URLs in wrapper tabs

## Additional relevant files for later favicon/VM settings work
### Repo/source
- `docs/CLI.md`
- `dashboard_v2/src/pages/Optimizer.jsx`
- `dashboard_v2/dist/index.html`
- `dashboard_v2/dist/assets/`

### Runtime/live
- `/opt/blobe-vm/dashboard/vm-fav/`
- `/opt/blobe-vm/dashboard_v2/dist/`
- `/etc/systemd/system/blobedash.service`
- `/opt/blobe-vm/server/blobedash-ensure.sh`

## Still worth doing later
1. Add wildcard DNS in Cloudflare:
   - `A *.techexplore.us -> server IPv4`
   - optional `AAAA *.techexplore.us -> server IPv6`
2. Optionally verify the live UI in a real browser after DNS is fixed.
3. Consider log rotation for optimizer logs if they grow quickly again.
4. Consider whether old `install.sh` should be further modernized or deprecated in favor of the server installer path.
5. Finish favicon support by converting uploads into a true `.ico` artifact server-side if browser behavior still refuses to cooperate.

## Short resend summary
Use this if you want to rehydrate context later:

> We did a larger BlobeVM-Manager pass on 2026-03-13. Earlier fixes covered Dashboard v2 VM type selector restore, optimizer logs viewer, optimizer `/proc/meminfo` fallback, health-check fallback via path routing, path-based VM URL fallback when wildcard DNS is missing, and one-shot installer onboarding improvements. Later we improved the `blobe-vm-manager` CLI + docs, added optimizer density profiles plus custom capacity controls in Dashboard v2, expanded the V2 VM Manager so it can create/delete VMs and edit per-VM domain override, tab title, and favicon, then deployed those changes live under `/opt/blobe-vm/...`. We also fixed a VM settings recreate race. Remaining unresolved issue: uploaded VM favicons are saved and served correctly, but the actual browser tab favicon still refuses to update reliably. Main files: `dashboard/app.py`, `dashboard/optimizer.py`, `dashboard_v2/src/pages/Logs.jsx`, `dashboard_v2/src/pages/Optimizer.jsx`, `dashboard_v2/src/pages/VMManager.jsx`, `server/blobe-vm-manager`, `docs/CLI.md`, `README.md`. Live runtime paths: `/opt/blobe-vm/dashboard/app.py`, `/opt/blobe-vm/dashboard/optimizer.py`, `/opt/blobe-vm/dashboard_v2/src/pages/Optimizer.jsx`, `/opt/blobe-vm/dashboard_v2/src/pages/VMManager.jsx`, `/opt/blobe-vm/dashboard/vm-fav/`, `/opt/blobe-vm/dashboard_v2/dist/`, `/var/blobe/logs/optimizer/optimizer.log`.
