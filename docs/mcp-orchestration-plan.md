# HermesHotel MCP Orchestration Plan

HermesHotel should expose a restricted MCP control surface so a trusted Hermes operator can spin up, inspect, update, and retire additional Hermes instances.

This is not implemented yet. It is the next layer after the official UI, TUI config cockpit, and light web panel.

## Goal

Allow a Hermes agent to manage a fleet of Hermes agents safely:

- Create a new profile.
- Allocate a port/domain/container name.
- Add an instance to `instances.json`.
- Patch compose/Caddy/profile config.
- Pull the official image.
- Recreate the affected service.
- Report status back to the agent.

## Proposed MCP Tools

### `hermeshhotel_list_instances`

Returns:

- `instances.json`
- Docker compose status
- public URLs
- current image ID
- health state

### `hermeshhotel_spawn_instance`

Input:

```json
{
  "name": "researcher",
  "domain": "researcher.froste.eu",
  "port": 3004,
  "profile_template": "operator",
  "model": "llama-3-8b",
  "toolsets": ["core", "web_search", "terminal", "files", "delegate"]
}
```

Actions:

1. Create `profiles/<name>/config.yaml` from a template.
2. Add compose service `hermes-<name>`.
3. Add Caddy route for the domain.
4. Add entry to `instances.json`.
5. Validate YAML/Caddy.
6. Reload Caddy.
7. Recreate/start service.
8. Return the new dashboard URL.

### `hermeshhotel_remove_instance`

Input:

```json
{
  "name": "researcher",
  "keep_data": true
}
```

Actions:

- Stop the compose service.
- Mark inactive or remove from `instances.json`.
- Optionally keep named volume/profile.
- Require explicit destructive approval before deleting volumes/files.

### `hermeshhotel_pull_image`

Pulls:

```text
nousresearch/hermes-agent:latest
```

Returns before/after image IDs and created timestamps.

### `hermeshhotel_recreate_instance`

Input:

```json
{"name": "operator"}
```

Runs compose recreate for the selected Hermes service and returns health.

### `hermeshhotel_get_config`

Returns masked config contents from the same allowlist used by the TUI Config Cockpit:

- `.env`
- `docker-compose.yml`
- `config/Caddyfile`
- `profiles/*/config.yaml`
- `instances.json`

Secrets must be masked.

### `hermeshhotel_patch_config`

Applies a structured patch to an allowlisted file:

- Create backup.
- Apply patch.
- Validate JSON/YAML/Caddy/env.
- Return diff/summary.
- Do not apply/restart unless explicitly requested.

### `hermeshhotel_reload_proxy`

Validates and reloads Caddy:

```bash
caddy validate --config config/Caddyfile
cp config/Caddyfile /etc/caddy/Caddyfile
caddy reload --config /etc/caddy/Caddyfile
```

## Safety Rules

- Only operate inside `/opt/hermeshotel`.
- Only edit allowlisted files.
- Mask all secrets in tool output.
- Always create backups before writes.
- Validate before applying.
- Separate dry-run from apply.
- Require explicit approval for:
  - deleting volumes
  - removing profiles
  - pruning images
  - changing public proxy routes
- Prefer official image `nousresearch/hermes-agent:latest`.
- Do not expose mutation tools through the light web panel.

## Implementation Target

Proposed files:

```text
mcp/hermeshotel_server.py
mcp/README.md
```

The MCP server should reuse the same conceptual registry as the TUI Config Cockpit:

- config file allowlist
- validators
- apply/restart modes
- secret masking
- instance registry

## Operator Config Hook

Once implemented, register the MCP in `profiles/operator/config.yaml` as a local MCP server. The exact Hermes MCP format should be verified against the current official image before enabling it in production.

Conceptual config:

```yaml
mcp_servers:
  hermeshotel:
    command: python3
    args:
      - /opt/hermeshotel/mcp/hermeshotel_server.py
    timeout: 120
```

Because the official Hermes container does not currently mount the whole repo, this may require either:

- mounting `/opt/hermeshotel/mcp` into the operator container, or
- exposing the MCP server over HTTP from a separate container.

Recommended direction: separate `hermeshotel-mcp` container with narrow volume mounts and explicit permissions.
