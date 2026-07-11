# Development and verification

Production remains a Linux Docker deployment. On Windows, use Git plus Node.js
for the Dashboard v2 frontend, and Docker Desktop with its WSL2 backend for any
container/runtime work. A native Windows dashboard backend is not supported.

From PowerShell, install the pinned Python checks in an isolated environment and
run the focused local checks:

```powershell
py -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest dashboard/tests
.\.venv\Scripts\ruff check dashboard
Push-Location dashboard_v2; npm ci; npm run test; npm run build; Pop-Location
& 'C:\Program Files\Git\bin\bash.exe' -n server/install.sh server/blobe-vm-manager server/blobedash-ensure.sh install.sh install-blobevm.sh
git diff --check
```

`dashboard_v2/dist` remains checked in for this hardening release because the
installer serves it directly. `npm run build` empties and regenerates it; stage
both removed and added hashes when intentionally updating that release asset.
