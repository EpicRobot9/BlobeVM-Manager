# BlobeVM-Manager Handoff — Portal/Auth/Access pass (2026-03-13)

## Summary
This pass added account-based access control, a user-facing portal, VM assignment/access policy support, admin review tooling for requests, and in-VM wrapper controls. It also fixed several restricted-VM routing/auth/proxy regressions and portal/Dashboard V2 bugs discovered during rollout.

## Completed
- Added user accounts with hashed passwords.
- Added per-user VM assignments.
- Added public vs restricted VM access modes.
- Added portal login with persistent sessions.
- Added user portal so assigned users can view VMs and open/start/stop them.
- Added access request flow.
- Added admin approve/deny/dismiss actions in Dashboard V2 `Users & Access`.
- Added in-VM wrapper controls UI:
  - stop VM
  - open portal
  - log out
- Fixed restricted VM routing/auth/proxy issues.
- Fixed portal bugs including syntax/filtering/status/start-stop auth issues.
- Fixed Dashboard V2 `Users & Access` unauthorized popup behavior.

## Main source files touched
- `dashboard/app.py`
- `server/blobe-vm-manager`
- `server/blobedash-ensure.sh`
- `dashboard_v2/src/pages/Users.jsx`
- `dashboard_v2/src/pages/VMManager.jsx`
- `dashboard_v2/src/lib/fetchWrapper.js`
- `dashboard_v2/src/App.jsx`
- `dashboard_v2/src/components/Sidebar.jsx`
- `dashboard/static/js/main_vm_wrapper.jsx`
- `dashboard/static/js/components/VMFallback.jsx`
- `dashboard/static/js/api/vms.js`

## Live deployment paths
- `/opt/blobe-vm/dashboard/app.py`
- `/opt/blobe-vm/server/blobe-vm-manager`
- `/opt/blobe-vm/server/blobedash-ensure.sh`
- `/opt/blobe-vm/dashboard_v2/src/pages/Users.jsx`
- `/opt/blobe-vm/dashboard_v2/src/pages/VMManager.jsx`
- `/opt/blobe-vm/dashboard_v2/src/lib/fetchWrapper.js`
- `/opt/blobe-vm/dashboard/static/js/main_vm_wrapper.jsx`
- `/opt/blobe-vm/dashboard/static/js/components/VMFallback.jsx`
- `/opt/blobe-vm/dashboard/static/js/api/vms.js`
- `/opt/blobe-vm/dashboard_v2/dist/`

## Known unresolved older issue
- VM tab favicon refresh is still unreliable even though upload/serving works.

## Good next checks
- Verify portal session persistence across restart/redeploy.
- Verify public vs restricted behavior on both direct-open and portal-open flows.
- Verify access request state transitions and UI refresh behavior after admin actions.
- Trace favicon invalidation/update path from upload -> served asset -> browser tab refresh behavior.
