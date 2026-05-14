# HermesHotel — Multi-Agent Hermes Platform

HermesHotel runs a multi-agent Hermes deployment using the official Docker image, Caddy reverse proxy, a private LLM endpoint, and optional MCP integrations (e.g. Flowwink).

## Quickstart (5 min)

```bash
git clone <repo> && cd hermeshotel
./scripts/init.sh                # prompts for OpenAI key, starts containers
python3 hermes-tui.py            # terminal control panel
python3 hermes-web.py            # fleet status → http://localhost:3099
```

First time? The TUI will show **★ Create First Hermes ★** — enter a name and domain to get started.

## Repository layout

```
hermeshotel/
├── docker-compose.yml          # auto-generated from instances.json
├── .env                        # secrets & model config
├── hermes-tui.py               # TUI control panel
├── hermes-web.py               # lightweight fleet status web
├── instances.json              # dynamic agent list
├── scripts/
│   ├── init.sh                 # one-command bootstrap
│   ├── add-hermes.sh           # add agent from template (with domain + Caddy)
│   ├── generate-compose.py     # compose generator
│   └── monitor.sh              # container monitor
├── profiles/
│   └── operator/               # template for new agents
├── config/
│   └── Caddyfile               # reverse proxy
└── docs/                       # detailed guides
```

## Services

| Service           | Container         | Host port  |
|-------------------|-------------------|------------|
| Hermes Agent      | hermes-<name>     | 3000+      |
| Redis             | hermes-redis      | internal   |
| Light status web  | hermeshotel-web   | 3099       |

## VPS Deployment

### 1. Create VPS
- Hetzner CX11 (2 vCPU, 4GB RAM) or equivalent
- Ubuntu 22.04+ LTS
- Open ports: 80, 443, 22

### 2. DNS Setup
Point your domain(s) to the VPS IP:
```
A-record: hermes.example.com    → YOUR_VPS_IP
A-record: operator.example.com  → YOUR_VPS_IP
```

### 3. Install & Run
```bash
# SSH to VPS
ssh root@YOUR_VPS_IP

# Install Docker & Caddy
curl -fsSL https://get.docker.com | sh
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update && apt-get install -y caddy

# Clone & setup
git clone <repo> /opt/hermeshotel && cd /opt/hermeshotel
./scripts/init.sh

# Configure Caddy with your domain(s), then:
sudo cp config/Caddyfile /etc/caddy/Caddyfile
sudo caddy reload
```

### 4. Verify
```bash
docker compose -f docker-compose.yml ps
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/
```

## Add a new Hermes agent

Via TUI: press `a` (Add Instance) → enter name and domain.

Via CLI:
```bash
./scripts/add-hermes.sh <name> <domain>
# Example:
./scripts/add-hermes.sh sales sales.example.com
```

This copies the operator template, creates a unique session token, updates `instances.json`, regenerates `docker-compose.yml`, adds a Caddy route, and starts the container.

## Common commands

```bash
docker compose -f docker-compose.yml up -d          # start all
docker compose -f docker-compose.yml logs -f         # follow logs
docker compose -f docker-compose.yml ps              # status
docker compose -f docker-compose.yml restart <svc>   # restart one agent

python3 hermes-tui.py       # TUI control panel
python3 hermes-web.py       # fleet status → http://localhost:3099

sudo caddy reload           # after editing config/Caddyfile
```

## Configuration

### .env (root)
```env
OPENAI_API_KEY=sk-…
HERMES_MODEL=gpt-4.1
LLM_BASE_URL=https://api.openai.com/v1
FLOWWINK_API_KEY=fwk_…        # optional, for MCP
HERMES_OPERATOR_TOKEN=…        # auto-generated
HERMES_LOG_LEVEL=info
PYTHONUNBUFFERED=1
```

### profiles/*/config.yaml
Each agent has its own config: personality, MCP servers, toolsets, model overrides. The operator profile is used as a template for new agents.

### config/Caddyfile
Reverse proxy mapping. Update domains to match your setup, then `sudo caddy reload`.

## Private LLM Configuration

The profiles use Hermes' custom OpenAI-compatible provider format:

```yaml
model:
  provider: custom
  default: gpt-4.1
  base_url: https://api.openai.com/v1
  api_mode: chat_completions

custom_providers:
  - name: custom_llm
    base_url: https://api.openai.com/v1
    key_env: OPENAI_API_KEY
    api_mode: chat_completions
    model: gpt-4.1
    models:
      gpt-4.1:
        context_length: 128000
```

## Health checks

```bash
curl -fsS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:3000/
```
Expected: `200`

Inside a container:
```bash
docker exec hermes-operator /bin/sh -lc \
  '. /opt/hermes/.venv/bin/activate && hermes -z "Svara med endast orden: fleet ok"'
```

## Notes

- Official Docker image: `nousresearch/hermes-agent:latest`
- Config files mounted read-write so the Hermes UI can persist changes
- `docker-compose.yml` is auto-generated by `scripts/generate-compose.py` — don't edit manually
- Inter-agent communication happens via Kanban board and direct API, not MCP

## Documentation

See `docs/` for detailed guides:

- `hermes-communication-patterns.md` — how to dispatch tasks to agents
- `official-ui-setup.md` — official Hermes dashboard setup
- `containerized-hermes-lessons.md` — lessons learned
- `container-boot-settings.md` — container boot configuration
- `light-web-panel.md` — fleet status panel
- `mcp-orchestration-plan.md` — MCP orchestration plan
- `easypanel-tui.md` — EasyPanel TUI guide
