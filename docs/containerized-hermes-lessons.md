# Containerized Hermes Lessons

These notes capture the practical containerization findings from the operator Hermes chat while getting the official Hermes UI running.

The goal is not to make every optional tool work immediately. The goal is:

1. Official Hermes web UI loads and can save config.
2. `hermes-operator` is healthy.
3. Private LLM `autoversio` works.
4. Flowwink MCP works from the operator.
5. Optional tools are diagnosed as setup gaps, not mistaken for core UI failures.

## 1. Official Image Entry Point Matters

Use the official image entrypoint rather than bypassing it with direct Python commands.

Current image:

```yaml
image: nousresearch/hermes-agent:latest
```

The official entrypoint:

- Drops root privileges to the `hermes` user.
- Activates `/opt/hermes/.venv`.
- Creates Hermes home directories.
- Copies default config only when missing.
- Starts dashboard as a side process when `HERMES_DASHBOARD=1`.

Compose pattern used here:

```yaml
environment:
  - HERMES_HOME=/data/hermes-profiles/operator
  - HERMES_DASHBOARD=1
  - HERMES_DASHBOARD_HOST=0.0.0.0
  - HERMES_DASHBOARD_PORT=3000
  - HERMES_DASHBOARD_TUI=1
command: ["sleep", "infinity"]
```

The `sleep infinity` command keeps the container alive while the entrypoint starts the dashboard in the background.

## 2. Config Files Must Be Read-Write

Hermes UI and chat can update config. If `config.yaml` is mounted read-only, the UI/chat may load but saving fails.

Bad:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml:ro
```

Good:

```yaml
- /opt/hermeshotel/profiles/operator/config.yaml:/data/hermes-profiles/operator/config.yaml
```

Observed operator-chat symptoms:

```text
Failed to write file: /data/hermes-profiles/operator/config.yaml: Read-only file system
umount: must be superuser
mount: must be superuser
cp: cannot create regular file ... Read-only file system
```

Inside the container, this showed as a file-level mount:

```text
/dev/sda1 on /data/hermes-profiles/operator/config.yaml type ext4 (ro,relatime)
```

Fix from the host:

```bash
# remove :ro from compose, then recreate containers
docker compose -f docker-compose.yml --env-file .env up -d --force-recreate hermes-customer hermes-operator hermes-supplier
```

Verify:

```bash
docker exec hermes-operator /bin/sh -lc 'mount | grep /data/hermes-profiles/operator/config.yaml || true'
```

Expected: `rw`.

## 3. Dashboard Auth Requires Header-Friendly Proxying

The official dashboard injects a session token into HTML:

```text
window.__HERMES_SESSION_TOKEN__
```

The frontend sends it as:

```text
X-Hermes-Session-Token
```

Caddy must not block this header and should answer `OPTIONS` preflight. If this is wrong, the welcome page can load while protected API calls fail with `401` or browser CORS errors.

Verify:

```bash
token=$(curl -fsS https://operator.froste.eu/ | python3 -c 'import sys,re; data=sys.stdin.read(); print(re.search(r"__HERMES_SESSION_TOKEN__=\"([^\"]*)\"", data).group(1))')
curl -fsS -H "X-Hermes-Session-Token: $token" https://operator.froste.eu/api/config >/dev/null
```

## 4. Private LLM Should Use Custom Provider Format

The private endpoint is OpenAI-compatible and serves model `autoversio`.

Use:

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

Avoid stale model names such as:

```text
openai/gpt-4o-mini
```

The private endpoint will reject those with:

```text
The model `openai/gpt-4o-mini` does not exist
```

After changing model config, start a new dashboard chat/session; old sessions can retain old model state.

## 5. Terminal Docker Sandbox Is Separate From Hermes Container

Operator chat found that Hermes terminal tools may use a separate Docker sandbox image:

```text
TERMINAL_DOCKER_IMAGE=nikolaik/python-nodejs:python3.11-nodejs20
```

That sandbox is not the same as the official Hermes service container. It may have different packages, Python version, home directory, network, and env vars.

Important loaded config fields observed:

```text
terminal.backend = local
terminal.docker_image = nikolaik/python-nodejs:python3.11-nodejs20
terminal.docker_forward_env = []
terminal.container_persistent = true
```

If backend is `docker`, the empty `docker_forward_env`/`TERMINAL_DOCKER_FORWARD_ENV=[]` means API keys do not reach the sandbox.

Recommended env forwarding when Docker-backed terminal tools are used:

```bash
TERMINAL_DOCKER_FORWARD_ENV="FAL_KEY OPENAI_API_KEY ANTHROPIC_API_KEY HERMES_MODEL FLOWWINK_API_KEY"
```

Alternative: use the same image as the service container for terminal sandboxing, or keep backend local if that is intended.

## 6. Optional Tool Failures Are Setup Gaps

The operator chat produced useful output and identified optional missing setup:

- `FAL_KEY` missing → image generation unavailable.
- No sudo/root in runtime user → apt installs fail by design.
- Missing CLI packages (`pyfiglet`, `cowsay`, `boxes`, `toilet`) → bake them into an image or install to user-writable paths.
- Some RSS feeds returned `301`, `307`, or `404` → feed availability issue, not Hermes core failure.

Do not treat these as official UI failures. The operator can still be healthy and useful.

## 7. Toolsets May Need Modern Platform Config

The operator config currently has a top-level `toolsets:` list:

```yaml
toolsets:
  - core
  - web_search
  - terminal
  - files
  - delegate
```

Operator chat suggested newer Hermes versions may prefer platform-specific toolsets such as:

```yaml
platform_toolsets:
  cli:
    - hermes-cli
```

Treat this as a follow-up hardening step. Confirm against the running Hermes version before changing production config.

## 8. What Worked In Operator Chat

The operator delivered several useful results, which confirms the containerized Hermes setup is viable:

- Created and saved an HTML dashboard sketch in the operator profile home.
- Ran blogwatcher successfully after removing broken feeds.
- Indexed hundreds of AI blog articles.
- Confirmed Flowwink MCP returned site health and FlowPilot identity.
- Confirmed TTS worked when the required provider config was available.
- Diagnosed read-only config mounts and Docker terminal environment issues.
- Updated Hermes skills with durable troubleshooting notes from inside the official UI.

## 9. Minimal Acceptance Checklist

Before debugging optional tools, check these:

```bash
docker compose -f docker-compose.yml --env-file .env ps
curl -fsS -o /dev/null -w 'operator %{http_code}\n' https://operator.froste.eu/
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes -z "Svara med endast orden: autoversio aktiv"'
```

Expected:

- Operator container is `healthy`.
- Operator UI returns `200`.
- Hermes answers `autoversio aktiv`.

If all three pass, the core containerized Hermes stack is functioning.
