# PRD & Backlog — HermesHotel

## Status (2026-05-14)
✅ **Three Hermes instances operational**:
- `operator` — admin/operator profile; can operate against Flowwink MCP
- `customer` — customer-support profile
- `supplier` — supplier-coordination profile

All containers healthy; official `nousresearch/hermes-agent:latest` image in use.
Chat verified via `hermes -z`; dashboards HTTP 200; Caddy reverse proxy working.

---

## Achieved
- Official Docker image, venv-activated CLI
- Private LLM (`autoversio` at `https://code4.autoversio.ai/v1`) configured in all profiles
- Caddy headers fixed (`X-Hermes-Session-Token`, OPTIONS preflight)
- Config mounts writable; dashboard persistence OK
- Flowwink API key updated in `.env` and operator profile
- TUI v0.16.0 with config cockpit, fleet controls, MCP orchestration plan
- Light web panel deployed (`hermeshotel.froste.eu`) with Docker-socket status
- Docs: `official-ui-setup.md`, `containerized-hermes-lessons.md`, `container-boot-settings.md`, `light-web-panel.md`, `mcp-orchestration-plan.md`, `easypanel-tui.md`

---

## Backlog — Future Work
- Model & server load display in light web UI
- Hermes gateway with Chrome for browser automation
- Dynamic "Add Hermes" flow in TUI (template-based profile creation)
- Per-profile `.env` isolation option
- Monitoring/alerting for 502 Cloudflare incidents
