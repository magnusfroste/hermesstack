# Container Boot Settings

This file documents the settings added to make the official Hermes Docker image behave like a usable VPS-hosted Hermes installation.

## Goal

Run Hermes in containers while keeping the official Hermes web UI usable:

- The dashboard must load through Caddy.
- The dashboard must be able to call protected `/api/*` routes.
- The dashboard must be able to save `config.yaml`.
- The operator must use the private `llama-3-8b` LLM endpoint.
- The operator must load Flowwink MCP.

## Compose Settings

File: `docker-compose.yml`

Each Hermes service uses:

```yaml
image: nousresearch/hermes-agent:latest
```

The official image entrypoint is intentionally kept. It prepares the Hermes runtime, activates the venv, fixes ownership, creates profile directories, and optionally starts the dashboard side process.

Dashboard startup is controlled by env vars:

```yaml
environment:
  - HERMES_HOME=/data/hermes-profiles/operator
  - HERMES_MODEL=${HERMES_MODEL:-llama-3-8b}
  - OPENAI_API_KEY=${OPENAI_API_KEY}
  - FLOWWINK_API_KEY=${FLOWWINK_API_KEY}
  - HERMES_DASHBOARD=1
  - HERMES_DASHBOARD_HOST=0.0.0.0
  - HERMES_DASHBOARD_PORT=3000
  - HERMES_DASHBOARD_TUI=1
command: ["sleep", "infinity"]
```

Why `sleep infinity`:

- The official entrypoint starts `hermes dashboard` in the background when `HERMES_DASHBOARD=1`.
- The foreground command keeps the container alive.
- This preserves official image behavior instead of bypassing it with direct `python -m ...` commands.

## Profile Mounts

Configs are bind-mounted from the repo into each Hermes profile:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml
```

They must be read-write. Do not add `:ro`, because the official dashboard and Hermes chat save config updates.

## Ports

Containers expose dashboard port `3000` only to localhost:

```yaml
ports:
  - "127.0.0.1:3002:3000"
```

Caddy is the only public entrypoint.

## Caddy Settings

File: `config/Caddyfile`

Caddy reverse proxies public domains to local ports and handles preflight/auth headers:

```caddyfile
(hermes_headers) {
    @options method OPTIONS
    respond @options 204

    header {
        Access-Control-Allow-Origin "*"
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "X-Hermes-Session-Token, Authorization, Content-Type, Accept, Origin, X-Requested-With"
        Access-Control-Expose-Headers "X-Hermes-Session-Token"
        Access-Control-Max-Age "3600"
        Cache-Control "no-store"
    }
}
```

The official dashboard injects an ephemeral token into HTML. Browser API calls send it as `X-Hermes-Session-Token`. If Caddy blocks this header, the welcome page can load while API calls fail.

## Private LLM Settings

Files:

- `profiles/operator/config.yaml`
- `profiles/customer/config.yaml`
- `profiles/supplier/config.yaml`
- `.env`

The running model is `llama-3-8b`:

```yaml
model:
  provider: custom
  default: llama-3-8b
  base_url: https://code4.llama-3-8b.ai/v1
  api_mode: chat_completions

custom_providers:
  - name: code4
    base_url: https://code4.llama-3-8b.ai/v1
    key_env: OPENAI_API_KEY
    api_mode: chat_completions
    model: llama-3-8b
    models:
      llama-3-8b:
        context_length: 128000
```

`.env` also contains:

```bash
HERMES_MODEL=llama-3-8b
```

## Flowwink Settings

File: `profiles/operator/config.yaml`

The operator profile includes Flowwink MCP:

```yaml
mcp_servers:
  flowwink:
    url: https://rzhjotxffjfsdlhrdkpj.supabase.co/functions/v1/mcp-server
    headers:
      Authorization: Bearer <FLOWWINK_API_KEY>
    timeout: 120
    connect_timeout: 60
```

The real key is managed through `.env` as `FLOWWINK_API_KEY`, but the MCP header currently stores the bearer value directly in the profile config.

## Runtime Verification

```bash
docker compose -f docker-compose.yml --env-file .env ps
curl -fsS -o /dev/null -w 'operator %{http_code}\n' https://operator.froste.eu/
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes -z "Svara med endast orden: hermes fungerar"'
```

Expected:

```text
hermes-operator healthy
operator 200
hermes fungerar
```

## Optional Hardening Still Open

These are not blockers for the official UI:

- Configure `TERMINAL_DOCKER_FORWARD_ENV` if terminal backend is changed to Docker.
- Add `FAL_KEY` if image generation is required.
- Confirm whether to migrate from top-level `toolsets:` to `platform_toolsets:` for the current Hermes version.
- Decide whether terminal sandbox should use the official Hermes image or stay local.
