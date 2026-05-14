# HermesHotel EasyPanel TUI

The HermesHotel TUI is evolving into a local EasyPanel for the Hermes fleet.

Official Hermes dashboards remain the primary UI for each agent:

- `https://operator.froste.eu`
- `https://customer.froste.eu`
- `https://supplier.froste.eu`

The TUI is for host-side fleet operations, config editing, image updates, and future MCP orchestration.

Run it from the VPS:

```bash
cd /opt/hermeshotel
python3 hermes-tui.py
```

## Main Areas

### `1. Status Dashboard`

Shows:

- customer/operator/supplier status
- domains
- local ports
- current model
- CPU/memory from Docker
- uptime
- host memory/load

### `8. Config Files`

Config cockpit for the files that make the official containerized Hermes stack boot correctly:

- `.env`
- `docker-compose.yml`
- `config/Caddyfile`
- `profiles/operator/config.yaml`
- `profiles/customer/config.yaml`
- `profiles/supplier/config.yaml`
- `instances.json`
- `docs/container-boot-settings.md`
- `docs/official-ui-setup.md`

Features:

- masked secret viewing
- scrollable file viewer
- edit with `$EDITOR`, default `nano`
- timestamped backups before edits
- JSON/YAML/env/Caddy validation
- apply/restart/reload for affected services

Apply behavior:

- Caddyfile → copy to `/etc/caddy/Caddyfile` and reload Caddy
- profile config → recreate the matching Hermes service
- `.env` → recreate Hermes customer/operator/supplier
- compose → recreate stack
- docs/instances → no service restart by default

### `9. Fleet / Images`

Fleet controls:

- pull latest `nousresearch/hermes-agent:latest`
- recreate Hermes services
- show image ID/created timestamp
- show Hermes version from the operator container
- run a model smoke test
- show compose status and Docker stats
- prune dangling images

Use this when upgrading the official image or checking what version is actually running.

### `m. MCP Orchestration`

Shows the planned MCP tool surface for allowing a trusted Hermes to spawn/manage more Hermes instances.

Planned tools:

- list instances
- spawn instance
- remove/deactivate instance
- pull image
- recreate instance
- read masked config
- patch config safely
- reload proxy

Detailed plan: `docs/mcp-orchestration-plan.md`.

### `c. Chat with Agent`

Secondary CLI chat path through `docker exec hermes-operator`. Use the official Hermes web UI first; this is mostly a fallback/smoke-test path.

## What Else Would Be Useful Later

Good next additions for multi-Hermes operations:

- per-agent backup/restore of profile directories
- per-agent session browser for latest chat transcripts
- one-click domain/DNS readiness checks
- certificate status from Caddy
- per-agent disk usage and volume usage
- template-based profile creation
- safe compose service generator for new Hermes instances
- direct MCP server management once `hermeshotel-mcp` exists
- read-only audit log of TUI actions

## Safety Notes

The TUI is intentionally local-only. It can run mutating operations such as service recreation and Caddy reloads. Do not expose it as a public web shell.

For public visibility, use the read-only light panel:

```text
https://hermeshotel.froste.eu
```
