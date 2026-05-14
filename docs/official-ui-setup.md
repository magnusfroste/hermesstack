# HermesHotel — Official Hermes UI Stack

HermesHotel runs three Hermes Agent instances behind Caddy with the official Docker image:

- `operator.froste.eu` → `hermes-operator` on local port `3002`
- `customer.froste.eu` → `hermes-customer` on local port `3001`
- `supplier.froste.eu` → `hermes-supplier` on local port `3003`

The current priority is the official Hermes dashboard/web UI and a working operator agent. The custom `hermes-tui.py` is secondary and should not block the official UI.

## Current Working Setup

- Docker image: `nousresearch/hermes-agent:latest`
- Dashboard: started by the official image entrypoint with `HERMES_DASHBOARD=1`
- Embedded web chat: enabled with `HERMES_DASHBOARD_TUI=1`
- Reverse proxy: Caddy on ports `80` and `443`
- Private LLM endpoint: `https://code4.autoversio.ai/v1`
- Model: `autoversio`
- Flowwink MCP: configured on the operator profile

Access URLs:

```text
https://operator.froste.eu
https://customer.froste.eu
https://supplier.froste.eu
```

## Start And Verify

Run from the repository root:

```bash
docker compose -f docker-compose.yml --env-file .env up -d
```

Check container health:

```bash
docker compose -f docker-compose.yml --env-file .env ps
```

Expected state:

```text
hermes-customer   healthy   127.0.0.1:3001->3000
hermes-operator   healthy   127.0.0.1:3002->3000
hermes-supplier   healthy   127.0.0.1:3003->3000
hermes-redis      running
```

Check public UI responses:

```bash
curl -fsS -o /dev/null -w 'operator %{http_code}\n' https://operator.froste.eu/
curl -fsS -o /dev/null -w 'customer %{http_code}\n' https://customer.froste.eu/
curl -fsS -o /dev/null -w 'supplier %{http_code}\n' https://supplier.froste.eu/
```

Expected: `200` for each.

## Private LLM Config

The profiles use Hermes' canonical custom provider format:

```yaml
model:
  provider: custom
  default: autoversio
  base_url: https://code4.autoversio.ai/v1
  api_mode: chat_completions

custom_providers:
  - name: code4
    base_url: https://code4.autoversio.ai/v1
    key_env: OPENAI_API_KEY
    api_mode: chat_completions
    model: autoversio
    models:
      autoversio:
        context_length: 128000
```

Files:

- `profiles/operator/config.yaml`
- `profiles/customer/config.yaml`
- `profiles/supplier/config.yaml`

The `.env` file should also use:

```bash
HERMES_MODEL=autoversio
```

The private endpoint exposes OpenAI-compatible endpoints:

```bash
curl https://code4.autoversio.ai/v1/models
```

A quick in-container model test:

```bash
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes -z "Svara med endast orden: autoversio aktiv"'
```

Expected output:

```text
autoversio aktiv
```

## Operator And Flowwink

The operator profile contains the Flowwink MCP server:

```yaml
mcp_servers:
  flowwink:
    url: https://rzhjotxffjfsdlhrdkpj.supabase.co/functions/v1/mcp-server
    headers:
      Authorization: Bearer ${FLOWWINK_API_KEY_VALUE}
```

The real key is stored in `.env` as `FLOWWINK_API_KEY` and currently also written into `profiles/operator/config.yaml` because the MCP config expects an Authorization header value.

Important: do not commit real keys to public repositories. Rotate any key that has been exposed in chat/logs.

## Operator Chat Findings

The latest operator chat is valuable for containerizing Hermes because it separated core UI health from optional tool setup.

What the operator confirmed:

- Flowwink MCP can return site-health/briefing and FlowPilot identity.
- Blogwatcher works when feeds are valid; broken feeds are RSS/source issues, not Hermes failures.
- HTML sketches and profile-home writes work once config/profile paths are writable.
- Skill updates from the official UI worked, proving the containerized operator can perform useful persistent work.
- Docker terminal/sandbox issues need their own diagnostics rather than being treated as dashboard failures.

Critical lessons captured from the operator chat:

- `TERMINAL_DOCKER_FORWARD_ENV=[]` silently means no API keys enter Docker-backed terminal sandboxes.
- `FAL_KEY` absence only breaks image generation; it does not mean Hermes UI/operator is broken.
- No `sudo` in runtime is expected for the `hermes` user; bake required CLI tools into images or install to user-writable paths.
- Top-level `toolsets:` may be less appropriate than modern platform-specific config such as `platform_toolsets` in newer Hermes versions.
- The terminal sandbox image can differ from the official service image, so package/Python differences are expected unless configured.

More details: `docs/containerized-hermes-lessons.md`.

## Caddy/Auth Headers

Hermes dashboard protects API routes with an ephemeral session token injected into the HTML as `window.__HERMES_SESSION_TOKEN__`. The frontend sends it with:

```text
X-Hermes-Session-Token
```

Caddy must allow this header and handle `OPTIONS` preflight. The working config is in:

- `config/Caddyfile`
- `/etc/caddy/Caddyfile`

After changes:

```bash
cp config/Caddyfile /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile
caddy reload --config /etc/caddy/Caddyfile
```

Verify auth through the proxy:

```bash
token=$(curl -fsS https://operator.froste.eu/ | python3 -c 'import sys,re; data=sys.stdin.read(); print(re.search(r"__HERMES_SESSION_TOKEN__=\"([^\"]*)\"", data).group(1))')
curl -fsS -H "X-Hermes-Session-Token: $token" https://operator.froste.eu/api/config >/dev/null
```

## Writable Config Mounts

The official Hermes UI must be able to write `config.yaml`. Do not mount profile configs as read-only.

Correct compose mount:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml
```

Incorrect compose mount:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml:ro
```

If this is wrong, Hermes chat/UI errors include:

```text
Read-only file system
Device or resource busy
Failed to write config.yaml
```

Verify inside the container:

```bash
docker exec hermes-operator /bin/sh -lc 'ls -l /data/hermes-profiles/operator/config.yaml; mount | grep /data/hermes-profiles/operator/config.yaml || true'
```

Expected mount mode: `rw`.

## Official UI Over Custom TUI

The official Hermes dashboard is the source of truth for operation and chat. The custom terminal dashboard in `hermes-tui.py` can be useful for host-level status, but it is secondary.

Do not treat TUI chat failures as blockers if:

- `https://operator.froste.eu/` loads
- `/api/config` works with `X-Hermes-Session-Token`
- `hermes-operator` is healthy
- `hermes -z` works inside the operator container

## Common Troubleshooting

### Old `openai/gpt-4o-mini` Error

Error:

```text
The model `openai/gpt-4o-mini` does not exist
```

Cause: stale session/config/env still points at the old model while the private endpoint only serves `autoversio`.

Fix:

```bash
grep -R "gpt-4o-mini\|openai/gpt-4o-mini" -n .
docker exec hermes-operator /bin/sh -lc 'grep -R "gpt-4o-mini\|openai/gpt-4o-mini" -n /data/hermes-profiles/operator 2>/dev/null || true'
```

Then update stale values to `autoversio`, recreate containers, and start a new dashboard chat session.

### Dashboard Loads But API Fails With 401

Cause: browser/API requests are missing `X-Hermes-Session-Token` or Caddy blocks the preflight/header.

Fix: use the Caddy config in `config/Caddyfile`, reload Caddy, then hard-refresh the browser with `Ctrl+F5`.

### Hermes Cannot Write Config

Cause: profile `config.yaml` is mounted read-only.

Fix: remove `:ro` from compose, then recreate containers:

```bash
docker compose -f docker-compose.yml --env-file .env up -d --force-recreate hermes-customer hermes-operator hermes-supplier
```

### Tooling Missing Inside Sandbox

Some failures are sandbox/setup issues rather than Hermes UI failures:

- `FAL_KEY` missing → image generation unavailable
- `pyfiglet`, `cowsay`, `boxes`, `toilet` missing → CLI-art tools unavailable unless baked into an image
- `TERMINAL_DOCKER_FORWARD_ENV=[]` → env vars are not forwarded into terminal sandbox

These are lower priority than official UI/operator stability.
