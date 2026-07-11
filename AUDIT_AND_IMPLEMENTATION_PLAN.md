# BlobeVM Manager Audit and Implementation Plan

Date: 2026-07-11

## Executive summary

BlobeVM Manager is a Linux-first Docker host manager for browser-accessible desktop containers. It includes a Bash CLI and installer, a Flask dashboard/API, a React/Vite Dashboard v2, a per-user VM portal, and an optimizer.

The core idea is solid, but the current `main` branch is not safe to expose until the authentication and portal defects below are fixed. The highest-risk issue is a split admin-auth design: the new installer stores `BLOBEDASH_USER`/`BLOBEDASH_PASS`, while Dashboard v2 checks a separate legacy settings password. When that legacy value is absent, `v2_auth_required` allows requests through, including user administration and arbitrary command execution inside VM containers. The latest credential-prompt function is also never invoked.

Windows should be supported as a development workstation through Git, Node, Docker Desktop/WSL2, and LF-normalized shell files. Native Windows production hosting is out of scope for this hardening pass; the production runtime should remain Linux containers.

## Audit findings

### P0 - fix before exposing the dashboard

1. **Dashboard v2 authentication can be bypassed.** `dashboard/app.py` gates v2 routes on `new_dashboard_admin_password`, not the installer-managed `BLOBEDASH_USER`/`BLOBEDASH_PASS`. If the legacy value is missing, `v2_auth_required` permits the request. This affects sensitive routes such as user administration and `/Dashboard/api/vm/exec/<name>`. The HMAC secret also falls back to the public constant `blobevm-secret`, so tokens are forgeable on default installs.
2. **The latest dashboard-credential feature is dead code.** `server/install.sh` defines `prompt_dashboard_auth`, but the function is never called from `main`. The installer therefore does not perform the prompt advertised by commit `c4ba8ed`.
3. **The user portal cannot complete login or logout.** `_portal_cookie_domain()` is called but never defined; Ruff reports both uses as `F821`. After defining it, `secure=True` would still prevent the cookie from working in the project's default direct HTTP mode.
4. **Linux dependencies are committed into Git.** `dashboard_v2/node_modules` contains 2,492 tracked files (59.8 MiB), including `@esbuild/linux-x64` and Unix-only `.bin` launchers. The checked-out repo therefore fails `npm run build` on Windows even though a clean temporary `npm ci && npm run build` succeeds.

### P1 - correctness, safety, and deployment

5. **Fresh Users & Access installs can return 500.** The list endpoint opens SQLite and queries `access_requests` before `_init_users_db()` has guaranteed the schema exists.
6. **Host cleanup is too broad.** The dashboard runs host-global Docker prune operations, including volumes and networks. It can delete unrelated Docker data on a shared server. Cleanup must be restricted to BlobeVM-labeled resources; aggressive global cleanup must not be the normal web action.
7. **Delete-all is wired incorrectly.** The web UI confirms `DELETE`, but the API invokes `blobe-vm-manager delete-all-instances` without `--yes`, causing the CLI to request another interactive confirmation from a non-interactive server process.
8. **Portal behavior is inconsistent.** The portal list includes only assigned VM names even though public VMs are accessible; the denied screen hardcodes `https://techexplore.us`; repeated access requests are allowed; and the `next` URL is not constrained to a same-origin relative path.
9. **Build/deploy ownership is confused.** The server installer copies Dashboard v2 but says Docker Compose builds it without actually invoking that build path. The deployment therefore relies on committed `dist`, while stale hashed bundles accumulate. There is no CI workflow to prove source, generated assets, and installers agree.
10. **Long-running operations are fire-and-forget.** Rebuild, reset, update, prune, and optimizer actions return `started` while swallowing worker errors. Users cannot see reliable progress, failure reason, or final state.

### P2 - Dashboard v2 UX and accessibility

11. **The React app changes hook order after authentication.** `useLocation()` is called only after the unauthenticated early return. A successful login can trigger React's "rendered more hooks" failure.
12. **No-auth startup is broken.** The backend returns `authRequired: false` with an empty token, but the frontend treats login as successful only when a non-empty token exists. It also trusts local storage instead of checking `/auth/status` during startup.
13. **Several controls are visibly or semantically broken.** The modal uses an invalid CSS ternary inside `calc()`, Advanced Tools links to `/dashboard/vm/` without the selected VM, the Home metric grid is not responsive, and the "Disable animations" setting is never consumed.
14. **Keyboard and screen-reader support is incomplete.** The login input has only a placeholder, modal lacks dialog semantics/focus trapping/Escape handling, icon-only topbar and sidebar controls lack accessible names, Logout is a clickable `div`, there is no global `:focus-visible` treatment, and motion does not honor `prefers-reduced-motion`.
15. **VM Manager polls with an N+1 request pattern.** Every refresh requests global list/stats/optimizer/settings and then one settings request per VM. At the default three-second interval this will overload the dashboard as VM count grows.

## Implementation plan

### Phase 1 - establish a reproducible Windows/Linux baseline

- Remove `dashboard_v2/node_modules` from Git and add `/dashboard_v2/node_modules/`, Python caches, logs, local state, and temporary audit/build output to `.gitignore`.
- Add `.gitattributes` with LF enforcement for `*.sh`, `Dockerfile`, and `server/blobe-vm-manager`. Keep production runtime Linux; document Windows development as Node plus Docker Desktop/WSL2.
- Keep `dashboard_v2/dist` tracked for the first hardening release because the current installer serves it directly. Change the build workflow to empty `dist`, regenerate one bundle, and stage both deletions and additions so stale hashes cannot accumulate. Reconsider untracking `dist` only after the installer owns a verified containerized build.
- Add pinned Python runtime/dev requirements and a single documented local check command. Do not depend on globally installed Flask or Ruff.

### Phase 2 - unify and secure admin authentication

- Make `BLOBEDASH_USER` and `BLOBEDASH_PASS` the single admin credential source. Read `new_dashboard_admin_password` only as a one-time compatibility fallback when the env credentials are absent; stop writing new legacy values.
- Replace `auth_required` and `v2_auth_required` with one `admin_auth_required` policy used by every admin API, including stats, users, logs, optimizer controls, destructive actions, and VM exec.
- Change Dashboard v2 login to accept username and password. At startup, call `/Dashboard/api/auth/status`; render a loading state until the result is known; enter the app directly only when auth is explicitly disabled or the cookie is valid.
- Generate random `DASH_V2_SECRET` and `BLOBEVM_USER_SECRET` values during install, persist them in `/opt/blobe-vm/.env`, and pass them into the dashboard container. Remove the public secret fallback in production; fail closed if a protected dashboard has no secret.
- Use an HttpOnly host-only session cookie rather than local-storage bearer tokens. Set `SameSite=Strict`, set `Secure` only when the effective external scheme is HTTPS, validate `Origin` on state-changing requests, and add a small per-IP login backoff.
- Default new installs to protected admin access. In non-interactive mode, generate an admin password and print it once. Allow an open dashboard only with an explicit `BLOBEVM_ALLOW_INSECURE_DASHBOARD=1` opt-out and a prominent warning.
- Move `useLocation()` above all conditional returns so hook order is stable.

### Phase 3 - repair portal and destructive workflows

- Remove `_portal_cookie_domain()` usage and use a host-only portal cookie with scheme-aware `Secure`. Return no portal token in response JSON.
- Call `_init_users_db()` before every direct users/access DB query. Raise the user password minimum to 12 characters and reject assignments or access requests for nonexistent VM names.
- Build the portal VM list from all public VMs plus the signed-in user's assigned restricted VMs, deduplicated by name. Replace the hardcoded production domain with relative same-origin URLs. Accept `next` only when it starts with one `/` and has no scheme/host.
- Add a unique pending-request rule or upsert so one user/VM pair cannot create duplicate pending requests.
- Require `{ "confirm": "DELETE" }` at the delete-all API boundary, then invoke the CLI with `--yes`. Apply the same server-side confirmation contract to reset-all and any other irreversible action.
- Replace global Docker cleanup with label-scoped BlobeVM cleanup. Never prune unrelated volumes or networks from the default dashboard action.
- Introduce a persisted job record for long operations with `id`, type, targets, status, timestamps, progress text, and final error/output. Mutation endpoints return HTTP 202 plus `jobId`; add `GET /dashboard/api/jobs` and `GET /dashboard/api/jobs/<id>`.

### Phase 4 - finish Dashboard v2 UX and scalability

- Fix modal width with valid `maxWidth`, add `role="dialog"`, `aria-modal`, labelled title, focus trap, initial focus, Escape close, and focus restoration.
- Correct the Advanced Tools VM link and replace prompt/alert flows with the existing modal/toast system. Give destructive actions visually distinct confirmation dialogs that name the exact VM/data affected.
- Add labels, error `role="alert"`, visible focus rings, accessible names for icon buttons, keyboard-safe menus, and reduced-motion CSS. Consume the animations setting at the app root.
- Make Home and Settings layouts responsive using reusable CSS classes rather than fixed inline column templates. In collapsed navigation, hide labels and expose tooltips; on mobile, add a backdrop and close the drawer after navigation.
- Replace VM Manager's per-VM settings calls with one bulk endpoint or include title, host override, access mode, favicon state, profile, and stats in the list payload. Keep one non-overlapping polling loop and pause polling while the page is hidden.
- Add an operation/job drawer so users can watch rebuilds, updates, and cleanup finish instead of receiving only "started".

### Phase 5 - tests and CI

- Backend tests with `pytest` and Flask's test client: admin-auth matrix, default-secret rejection, HTTP/HTTPS cookie flags, first-run DB initialization, public/assigned portal listing, local-only `next`, duplicate access request handling, delete-all confirmation/`--yes`, and scoped cleanup. Mock Docker and the manager; never touch the real host daemon.
- Frontend tests with Vitest and React Testing Library: auth-status startup, auth-disabled startup, failed/successful login, stable hook order, expired session, accessible modal/menu, selected-VM link, and responsive/collapsed navigation behavior.
- One integration smoke: build Dashboard v2, run Flask with a temporary state directory and fake manager/Docker adapters, sign in, load an empty fleet, create a fake VM, and exercise start/stop/job status.
- GitHub Actions: Ubuntu job for Python checks, shell syntax/ShellCheck, frontend tests/build, and the integration smoke; Windows job for clean `npm ci`, frontend tests/build, Python syntax, and CRLF guard. Cache package downloads, not `node_modules` in Git.

## Acceptance criteria

- A fresh protected install cannot reach any admin endpoint without valid credentials; `/vm/exec` is verified explicitly.
- The advertised installer prompt runs, secrets are generated, and Dashboard v2 accepts those exact credentials.
- Portal login/logout works in direct HTTP and proxied HTTPS modes; restricted/public VM visibility matches policy.
- A clean clone builds on Windows after `npm ci`; no Linux binaries or `node_modules` are tracked.
- Default cleanup cannot remove non-BlobeVM Docker resources, and every irreversible web action requires server-validated confirmation.
- Dashboard v2 loads without hook errors, works at desktop and mobile widths, and core flows are keyboard operable.
- CI passes on Ubuntu and Windows from a clean checkout.

## New feature suggestions (separate from audit closure)

1. **Snapshot, clone, and restore:** point-in-time VM snapshots, clone-from-snapshot, retention rules, and one-click rollback before upgrades.
2. **Template catalog:** reusable VM templates for desktop, gaming, development, classroom, and disposable sessions with app presets and resource profiles.
3. **Guided setup and Doctor UI:** a first-run wizard that shows Docker/KVM/DNS/ports/TLS readiness, explains failures plainly, and exports a support bundle with secrets redacted.
4. **Backup and migration:** export VM metadata/config plus optional data archives, validate backups, and migrate a VM between BlobeVM hosts.
5. **Scheduled policies and alerts:** maintenance windows, automatic stop for idle VMs, quota warnings, job-failure alerts, and optional email/webhook delivery.
6. **Time-limited sharing and roles:** viewer/operator/admin roles, expiring VM access links, per-action audit history, and approval rules for high-cost VM profiles.
7. **Windows companion:** a small PowerShell/desktop launcher that checks Docker Desktop/WSL2, opens the dashboard, tails service status, and clearly distinguishes Windows development from Linux production hosting.

## Verification already performed

- Synced local `main` to `origin/main` at `c4ba8ed`.
- Clean temporary Windows install/build: `npm ci --no-audit --no-fund` and `npm run build` passed (57 modules).
- Repo-local build failed because tracked Linux `.bin` launchers are not Windows executables.
- Python syntax compilation passed for five project Python files.
- Targeted Ruff undefined-name scan found exactly the two `_portal_cookie_domain` failures.
- Git Bash syntax checks passed for the main installers, CLI, optimizer ensure script, and window-manager launch scripts.
- Screenshot-backed UX inspection reached the Dashboard v2 login screen. Full authenticated/runtime flow was blocked because this machine has no WSL distribution, Docker Desktop's daemon is not running, and the local Python environment does not include Flask.
- An npm advisory lookup was not completed because the external check hit the current Codex usage limit; dependency vulnerability status remains unverified.

## Completion checklist (2026-07-11)

Completed
- [x] P0 hygiene: ignored and removed tracked frontend dependency tree locally; added LF rules and Windows development guidance.
- [x] P0 authentication: unified protected API policy, cookie sessions, installer secret/credential generation, login backoff, and explicit insecure opt-out.
- [x] P1 portal safety: host-only scheme-aware cookie, safe portal redirects, first-use DB initialization, deduplicated requests, public-plus-assigned visibility, and VM validation.
- [x] P1 destructive safety: server-side DELETE confirmation, noninteractive delete-all, label-scoped cleanup, and persisted operation jobs.
- [x] P2 core UI fixes: auth-status startup, stable hook order, accessible modal/navigation controls, reduced motion, responsive layouts, and selected VM link.

Verification evidence
- [x] Python syntax compilation passed for dashboard Python entrypoints.
- [x] Git Bash syntax validation passed for installers, manager, and dashboard ensure script.
- [x] Windows clean `npm ci` passed; production Vite build passed after granting local esbuild filesystem access (56 modules).

Deferred / blockers
- [ ] Focused pytest/Vitest suites and Ubuntu/Windows CI definitions were not added in this constrained pass.
- [ ] Targeted Ruff currently reports 17 pre-existing style/unused-variable findings in `dashboard/app.py`; no new undefined portal-cookie failure remains.
- [ ] `git diff --check` is blocked by CRLF output from the generated Dashboard v2 `dist/index.html`; normalize generated artifact line endings before staging.
- [ ] Docker/WSL2 runtime integration was not run on this Windows host; use Docker Desktop/WSL2 with mocked manager/Docker adapters before deployment.
