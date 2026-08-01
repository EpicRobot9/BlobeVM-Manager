# EpicVM RemoteVM Windows agent

This directory contains the Windows host side of EpicVM's RemoteVM feature.
It uses PowerShell 7 and the Hyper-V module. The dashboard never receives a
Hyper-V credential: it calls this agent over a Tailscale address with a bearer
token.

## Install

Run an elevated PowerShell 7 prompt on the Windows host:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1 -TailscaleAddress 100.72.220.117
```

The installer writes the enrollment credential to the protected `agent.token`
file and never prints it. Transfer that file through an approved secure channel
to the EpicVM server, keep it mode `0600`, and enroll it with
`epicvm-remote-host add ... --token-file <path>`.
It stores the real token under `C:\ProgramData\EpicVM\agent\agent.token`,
creates the `EpicVMRemoteAgent` service, and opens TCP/8765 only for
`100.64.0.0/10` (Tailscale's CGNAT range). The listener binds only to the
supplied Tailscale address; wildcard binding is refused. Set `SwitchName` in the generated
`config.json` before creating VMs if Hyper-V should attach a specific virtual
switch.

A quick local check is:

```powershell
Invoke-RestMethod -Headers @{ Authorization = "Bearer $(Get-Content C:\ProgramData\EpicVM\agent\agent.token)" } http://127.0.0.1:8765/v1/capabilities
```

The service exposes:

- `GET /v1/health`
- `GET /v1/capabilities`
- `GET /v1/vms`
- `POST /v1/vms`
- `GET /v1/vms/{name}`
- `GET /v1/vms/{name}/logs` (empty but explicit until guest log transport is added)
- `POST /v1/vms/{name}/start|stop|restart`
- `DELETE /v1/vms/{name}`
- `POST /v1/vms/{name}/actions/start|stop|restart|delete` (legacy alias)

All endpoints require the configured authorization header and return JSON. Mutation
requests accept an `Idempotency-Key`, are serialized while the provider acts,
and return an `X-Request-Id` header. The provider writes an
`EpicVM-Managed: true` marker into Hyper-V VM notes and refuses lifecycle or
delete operations on VMs without that marker or outside the configured VM root.
Deleting a VM unregisters it but preserves its VHDX for recovery.

## Uninstall

```powershell
.\uninstall.ps1
# Add -PurgeData only when the token, config, logs, and VM data should be removed.
```

The Linux dashboard should register the host with its Tailscale URL, for
example `http://win-gaming.ts.net:8765`, and the token. Public URLs are rejected
by the server-side registry unless the explicit development override is set.
