# EpicVM Dashboard (Modern UI)

The EpicVM Dashboard is the modern React + Vite interface for the EpicVM VM platform. It runs alongside the legacy dashboard route so existing deployments can upgrade without losing established links.

## URLs and title

- Modern UI: `/Dashboard`
- Legacy-compatible UI/API base: `/dashboard`
- Browser title: **EpicVM Dashboard**

The old `/dashboard` and `/Dashboard` routes, including established dashboard API paths, are legacy ABI retained for existing deployments.

## Pages and features

- Home overview with live host metrics and charts
- VM Manager for create/start/stop/restart/delete and VM links
- Resource Usage and per-VM CPU/RAM information
- Logs Viewer and short, non-interactive VM commands
- EpicVM Optimizer profiles and capacity controls
- Settings, API/System Info, Advanced Tools, and Login

VM operations act on EpicVM containers while preserving existing `blobevm_<name>` container names. The dashboard is focused on VM lifecycle, routing, and presentation.

## API highlights

- `POST /Dashboard/api/auth/login` and `GET /Dashboard/api/auth/status`
- `GET /Dashboard/api/stats`
- `GET /Dashboard/api/vm/logs/<name>`
- `GET /Dashboard/api/vm/stats`
- `POST /Dashboard/api/vm/exec/<name>` (short, non-interactive command)
- `POST /dashboard/api/create` and `POST /dashboard/api/delete/<name>`
- `GET /dashboard/api/v2/info`
- `GET /dashboard/api/optimizer/v2/summary`

The legacy service ID `blobedash` and optimizer service ID `blobe-optimizer` remain valid compatibility identifiers. Existing `BLOBEVM_*` variables and `/opt/blobe-vm` state paths are likewise retained.

## Local development

```bash
cd dashboard_v2
npm ci
npm run dev
npm run build
```

A production build is written to `dashboard_v2/dist`. The installer records build diagnostics in `dashboard_v2/last_error.txt`; check `/dashboard/api/v2/info` when the modern UI does not load. Set `DASH_V2_SECRET` in production for signed dashboard tokens. The Docker CLI must be available to the dashboard process.

## Attribution and license

EpicVM is a modified VM platform derived from DesktopOnCodespaces. It is distributed under the GNU General Public License version 3 (GPLv3); preserve the upstream attribution and repository `LICENSE` when redistributing it.
