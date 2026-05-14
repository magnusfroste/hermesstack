# HermesHotel Light Web Panel

HermesHotel now includes a lightweight web status panel in addition to the official Hermes dashboards and the host-side TUI.

Purpose:

- Show what Hermes containers are running.
- Show lightweight CPU/memory stats.
- Link to the official Hermes dashboards.
- Keep the TUI as the deeper control panel for editing configs, pulling images, and future MCP orchestration.

## Service

Compose service:

```yaml
hermeshotel-web:
  image: python:3.12-alpine
  container_name: hermeshotel-web
  restart: unless-stopped
  working_dir: /app
  environment:
    - HERMESHOTEL_WEB_PORT=3099
    - HERMESHOTEL_REFRESH_SECONDS=5
  volumes:
    - /opt/hermeshotel/hermes-web.py:/app/hermeshotel-web.py:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
  ports:
    - "127.0.0.1:3099:3099"
  command: ["python", "/app/hermeshotel-web.py"]
```

Source file:

- `hermes-web.py`

It has no third-party Python dependencies. It talks to Docker through the mounted read-only Docker socket and checks the internal Hermes dashboard URLs over the compose network.

## Routes

Local routes:

```text
http://127.0.0.1:3099/
http://127.0.0.1:3099/api/status
```

Planned public route:

```text
https://hermeshotel.froste.eu/
```

Caddy config has been added, but DNS must point `hermeshotel.froste.eu` to the VPS before the public route works.

## What It Shows

- Running Hermes containers.
- Internal dashboard health.
- CPU percent.
- Memory usage and memory percent.
- Hermes official image ID/created timestamp.
- Redis status.
- Quick links to:
  - `https://operator.froste.eu/`
  - `https://customer.froste.eu/`
  - `https://supplier.froste.eu/`

## Security Notes

The web panel mounts Docker socket read-only:

```yaml
- /var/run/docker.sock:/var/run/docker.sock:ro
```

This is sufficient for status reads, but Docker socket exposure is still sensitive. Keep the panel behind HTTPS and do not add mutation controls to the lightweight web UI unless an authentication/authorization layer is added.

Control actions should stay in the local TUI or in a future restricted MCP server.

## Verify

Start or update the panel:

```bash
docker compose -f docker-compose.yml --env-file .env up -d hermeshotel-web
```

Check local API:

```bash
curl -fsS http://127.0.0.1:3099/api/status | python3 -m json.tool
```

Expected summary:

```json
{
  "total": 3,
  "running": 3,
  "http_ok": 3
}
```

Check local UI:

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3099/
```

Expected: `200`.
