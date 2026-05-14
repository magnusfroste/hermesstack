# HermesHotel — Containerized Hermes Multi‑Agent Stack

Official Hermes image + private LLM + Flowwink MCP. Three agents (operator, customer, supplier) running as separate containers managed by a lightweight TUI and status web.

## Quickstart (5 min)

```bash
git clone <your‑repo> && cd hermeshotel
./scripts/init.sh                # → prompts for OpenAI key, starts containers
python3 hermes-tui.py            # terminal control panel
python3 hermes-web.py            # fleet status → http://localhost:3099
```

All three agents come up automatically. Open `https://operator.<your‑domain>` (configured in `config/Caddyfile`) for the official Hermes dashboard.

## Repository layout (optimized)

```
hermeshotel/
├── docker-compose.yml          # main compose: 3 × hermes‑* + hermeshotel‑web + redis
├── .env                        # secrets & model (OPENAI_API_KEY, HERMES_MODEL=llama-3-8b, FLOWWINK_API_KEY)
├── hermes-tui.py               # TUI control panel (directly executable)
├── hermes-web.py               # lightweight fleet status web panel
├── scripts/
│   ├── init.sh                 # one‑command bootstrap for fresh VPS/local install
│   └── add-hermes.sh           # add a new Hermes agent from operator template
├── profiles/
│   ├── operator/               # operator profile (Flowwink MCP, full tools)
│   ├── customer/               # customer‑support profile
│   └── supplier/               # supplier‑coordination profile
├── config/
│   ├── Caddyfile               # reverse proxy (edit domains)
│   └── Caddyfile.template      # template used by init.sh
├── instances.json              # dynamic agent list consumed by TUI & hermes‑web
└── docs/                       # detailed guides
```

Key paths changed from `deploy/vps/` → repo root for first‑run simplicity.

## Services (compose)

| Service            | Container          | Host port | Domain (Caddy)           |
|--------------------|-------------------|-----------|--------------------------|
| Hermes Operator    | `hermes-operator`  | 3002      | `operator.<domain>`      |
| Hermes Customer    | `hermes-customer`  | 3001      | `customer.<domain>`      |
| Hermes Supplier    | `hermes-supplier`  | 3003      | `supplier.<domain>`      |
| Redis              | `hermes-redis`     | –         | internal only            |
| Light status web   | `hermeshotel-web`  | 3099      | `http://localhost:3099`  |

Edit domain mappings in `config/Caddyfile`, then `sudo caddy reload`.

## Add a new Hermes agent

```bash
./scripts/add-hermes.sh <profile-name>   # e.g. ./scripts/add-hermes.sh sales
```

What it does:
1. Copies `profiles/operator/` → `profiles/<profile-name>/`
2. Generates a unique session token and appends `HERMES_<PROFILE>_TOKEN` to `.env`
3. Inserts a new service block for `hermes-<profile-name>` into `docker-compose.yml` between dynamic markers
4. Starts the container

`instances.json` is updated automatically; the TUI and web panel reflect the new agent immediately.

## Common commands

```bash
# General compose usage
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml logs -f
docker compose -f docker-compose.yml ps
docker compose -f docker-compose.yml restart hermes-operator

# TUI
python3 hermes-tui.py

# Light web status
python3 hermes-web.py   # browse to http://localhost:3099

# Caddy
sudo caddy reload       # after editing config/Caddyfile
sudo systemctl status caddy
```

## Configuration

### .env (root)
```env
OPENAI_API_KEY=sk-…
HERMES_MODEL=llama-3-8b
FLOWWINK_API_KEY=fwk_…   # operator only
HERMES_LOG_LEVEL=info
PYTHONUNBUFFERED=1
```

### profiles/*/config.yaml
Each agent has its own YAML config: personality, mcp_servers, toolsets, model overrides. The operator profile includes the Flowwink MCP server URL and bearer token.

### config/Caddyfile
Reverse proxy mapping:

```
https://operator.<your-domain> {
  reverse_proxy http://127.0.0.1:3002
}
# … customer, supplier
```

Update `<your-domain>` to your real domain and point DNS A‑records to the server IP.

## Health checks

```bash
curl -fsS -o /dev/null -w 'operator %{http_code}\n' https://operator.<domain>/
curl -fsS -o /dev/null -w 'customer %{http_code}\n' https://customer.<domain>/
curl -fsS -o /dev/null -w 'supplier %{http_code}\n' https://supplier.<domain>/
```

All should return `200`.

Inside operator container:
```bash
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes -z "Svara med endast orden: llama-3-8b aktiv"'
```
Expected output: `llama-3-8b aktiv`

## Notes

- All profile configs must be mounted read‑write so the official Hermes UI can persist changes.
- `TERMINAL_DOCKER_FORWARD_ENV` is set to pass API keys into the terminal sandbox (see `.env`).
- The light web panel (`hermes-web.py`) reads `/var/run/docker.sock` for container stats and the internal Hermes dashboard endpoints; no third‑party dependencies.

## Documentation

See `docs/` for detailed setup, lessons learned, EasyPanel integration, and MCP orchestration plans:

- `official-ui-setup.md`
- `containerized-hermes-lessons.md`
- `container-boot-settings.md`
- `light-web-panel.md`
- `mcp-orchestration-plan.md`
- `easypanel-tui.md`

Expected:

```text
llama-3-8b aktiv
```

## Private LLM Configuration

The profiles use Hermes' custom OpenAI-compatible provider format:

```yaml
model:
  provider: custom
  default: llama-3-8b
  base_url: https://api.localhost.ai/v1
  api_mode: chat_completions

custom_providers:
  - name: localhost
    base_url: https://api.localhost.ai/v1
    key_env: OPENAI_API_KEY
    api_mode: chat_completions
    model: llama-3-8b
    models:
      llama-3-8b:
        context_length: 128000
```

Relevant files:

- `profiles/operator/config.yaml`
- `profiles/customer/config.yaml`
- `profiles/supplier/config.yaml`
- `.env`

`.env` should include:

```bash
HERMES_MODEL=llama-3-8b
OPENAI_API_KEY=...
FLOWWINK_API_KEY=...
```

Do not use stale `openai/gpt-4o-mini` values with the private endpoint; it only exposes `llama-3-8b`.

## Flowwink MCP

The operator agent is the important one. Its Flowwink MCP config lives in:

- `profiles/operator/config.yaml`

Flowwink is configured under `mcp_servers.flowwink` and uses bearer auth. Keep real keys out of public commits and rotate any key that has appeared in chat/log output.

The operator chat verified that Flowwink MCP can return briefing/site-health information and FlowPilot identity when configured correctly.

## Critical Containerization Lessons From Operator Chat

The operator chat surfaced several important facts for running Hermes in containers.

### Config Must Be Writable

The official Hermes UI writes to `config.yaml`. Therefore profile config bind mounts must not use `:ro`.

Correct:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml
```

Incorrect:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml:ro
```

Symptoms when mounted read-only:

```text
Read-only file system
Device or resource busy
Failed to write config.yaml
```

Verify inside the container:

```bash
docker exec hermes-operator /bin/sh -lc 'ls -l /data/hermes-profiles/operator/config.yaml; mount | grep /data/hermes-profiles/operator/config.yaml || true'
```

Expected: mount mode includes `rw`.

### Terminal Sandbox Env Vars

When Hermes terminal tools spawn a Docker sandbox, API keys are only available if forwarded. The operator chat identified `TERMINAL_DOCKER_FORWARD_ENV=[]` as a common reason tools appear broken: the sandbox receives no credentials.

If using Docker-backed terminal tools, forward required keys from the host/container environment:

```bash
TERMINAL_DOCKER_FORWARD_ENV="FAL_KEY OPENAI_API_KEY ANTHROPIC_API_KEY HERMES_MODEL FLOWWINK_API_KEY"
```

In Hermes config this corresponds to terminal Docker env forwarding. If terminal backend is `local`, this is less important; if terminal backend is `docker`, it is critical.

### Toolsets Configuration

Older top-level `toolsets:` may be ignored or less complete in newer Hermes versions. Prefer platform-specific toolsets when configuring broad UI/CLI access.

Example target direction:

```yaml
platform_toolsets:
  cli:
    - hermes-cli
```

This is a follow-up hardening item, not a blocker for official UI availability.

### Missing Optional Keys Are Not UI Failures

Some operator-chat failures were optional tool setup issues, not official Hermes UI failures:

- `FAL_KEY` missing → image generation unavailable
- Missing packages such as `pyfiglet`, `cowsay`, `boxes`, `toilet` → optional CLI/art tools unavailable
- No sudo in runtime container → install tools in user-writable paths or bake them into an image

These should not be confused with the official dashboard/operator being down.

## Caddy And Dashboard Auth

Hermes injects an ephemeral dashboard token into the page as `window.__HERMES_SESSION_TOKEN__`. API calls use:

```text
X-Hermes-Session-Token
```

Caddy must allow that header and handle `OPTIONS` preflight. Use:

```bash
cp config/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
caddy reload --config /etc/caddy/Caddyfile
```

Verify dashboard API through Caddy:

```bash
token=$(curl -fsS https://operator.froste.eu/ | python3 -c 'import sys,re; data=sys.stdin.read(); print(re.search(r"__HERMES_SESSION_TOKEN__=\"([^\"]*)\"", data).group(1))')
curl -fsS -H "X-Hermes-Session-Token: $token" https://operator.froste.eu/api/config >/dev/null
```

## Useful Commands

Restart Hermes agents after config changes:

```bash
docker compose -f docker-compose.yml --env-file .env up -d --force-recreate hermes-customer hermes-operator hermes-supplier
```

Show operator logs:

```bash
docker logs --since=10m hermes-operator
```

Find stale model references:

```bash
grep -R "gpt-4o-mini\|openai/gpt-4o-mini" -n .
docker exec hermes-operator /bin/sh -lc 'grep -R "gpt-4o-mini\|openai/gpt-4o-mini" -n /data/hermes-profiles/operator 2>/dev/null || true'
```

Inspect loaded operator config:

```bash
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && python3 - <<"PY"
from hermes_cli.config import load_config
cfg = load_config()
print(cfg.get("model"))
print(cfg.get("custom_providers"))
print(cfg.get("mcp_servers", {}).keys())
PY'
```

## HermesHotel Light Web Panel

A lightweight web panel is available at:

```text
https://hermeshotel.froste.eu
```

It shows running Hermes containers, dashboard health, CPU/memory stats, Redis status, official image metadata, and quick links to the official Hermes dashboards. It is intentionally read-only; mutation/control remains in the local TUI or future MCP server.

Details: `docs/light-web-panel.md`.

## TUI EasyPanel / Config Cockpit

The custom TUI is secondary to the official Hermes UI, but it now works as a host-side EasyPanel for operations:

```bash
python3 hermes-tui.py
python3 hermes-tui.py
```

Useful TUI options:

- `8. Config Files` — view, validate, edit, and apply the files that make the container boot with the current settings
- `9. Fleet / Images` — pull latest official Hermes image, recreate services, inspect image/version, check stats, prune dangling images
- `m. MCP Orchestration` — shows the planned MCP control surface for spawning/managing more Hermes instances
- `c. Chat with Agent` — secondary CLI chat path; official web UI remains preferred

Config cockpit files:

- `.env`
- `docker-compose.yml`
- `config/Caddyfile`
- `profiles/operator/config.yaml`
- `profiles/customer/config.yaml`
- `profiles/supplier/config.yaml`
- `instances.json`
- `docs/container-boot-settings.md`
- `docs/official-ui-setup.md`

The TUI masks obvious secrets while viewing, creates timestamped backups before edits, validates JSON/YAML/env/Caddy files where possible, and can apply/recreate the affected service after saving.

## Further Docs

- `docs/official-ui-setup.md` — detailed setup and troubleshooting notes
- `docs/containerized-hermes-lessons.md` — operator-chat findings specific to containerized Hermes
- `docs/container-boot-settings.md` — map of the compose/env/Caddy/profile settings that make official Hermes boot correctly
- `docs/light-web-panel.md` — lightweight web status panel at `https://hermeshotel.froste.eu`
- `docs/mcp-orchestration-plan.md` — plan for HermesHotel MCP tools that let Hermes spawn/manage Hermes instances
- `README-VPS.md` — VPS/Caddy deployment reference
