# Hermes Communication Patterns — HermesHotel

How to dispatch tasks and communicate with running Hermes agents in the HermesHotel setup.

## Architecture

Each Hermes agent runs as a Docker container with:
- `sleep infinity` as the main command (keeps container alive)
- Dashboard side-process on port 3000 (internal) / mapped to host port (3001, 3002, 3003)
- Full Hermes CLI available inside the container via the venv

```
Host port 3001 → hermes-customer:3000
Host port 3002 → hermes-operator:3000
Host port 3003 → hermes-supplier:3000
```

## Communication Methods

### 1. Single Query (non-interactive)

Use `hermes -z "prompt"` for quick questions. Runs in a new session or resumes recent one. Returns when the agent finishes its response.

```bash
docker exec hermes-operator /bin/sh -lc \
  '. /opt/hermes/.venv/bin/activate && hermes -z "What model am I using?"'
```

**Limitations**: Blocks until the agent responds. Not suitable for long-running tasks. Timeout via `timeout 120`.

### 2. Interactive Chat

```bash
docker exec hermes-operator /bin/sh -lc \
  '. /opt/hermes/.venv/bin/activate && hermes chat'
```

Opens an interactive terminal session. Useful for manual exploration.

### 3. Cron Jobs (scheduled / async tasks)

For long-running work, schedule via Hermes cron:

```bash
docker exec hermes-operator /bin/sh -lc \
  '. /opt/hermes/.venv/bin/activate && hermes cron create 0 "Run the Flowwink MCP scan..."'
```

The cron scheduler picks up the job on the next tick and runs it asynchronously. The agent processes it in the background and delivers results via the configured delivery channel (gateway, webhook, or dashboard notification).

### 4. Kanban Board (multi-agent orchestration)

For complex work that needs decomposition, tracking, and routing:

```bash
docker exec hermes-operator /bin/sh -lc \
  '. /opt/hermes/.venv/bin/activate && hermes kanban create \
    --title "Flowwink MCP Systematic Scan" \
    --body "Test all 265 MCP tools systematically..." \
    --assignee operator'
```

**Kanban lifecycle:**
1. Orchestrator creates tasks via `kanban_create()` or `hermes kanban create`
2. Dispatcher spawns worker processes with `--skills kanban-worker`
3. Worker gets a fresh workspace and the KANBAN_GUIDANCE system prompt
4. Worker completes via `kanban_complete(summary, metadata)` or blocks via `kanban_block(reason)`
5. Results are visible on the dashboard and via `hermes kanban list`

**When to use Kanban:**
- Multiple specialists needed (different profiles)
- Work should survive crash/restart
- Human-in-the-loop review needed
- Parallel subtasks can run concurrently
- Audit trail matters

### 5. Dashboard HTTP API

The Hermes dashboard exposes an HTTP API on port 3000 (internal). The session token is set via `HERMES_SESSION_TOKEN` environment variable.

```bash
TOKEN=$(docker exec hermes-operator printenv HERMES_SESSION_TOKEN)
curl -s http://127.0.0.1:3002/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Hermes-Session-Token: $TOKEN" \
  -d '{"message":"..."}'
```

**Note**: The exact API endpoints and auth mechanism may vary by Hermes version. Check the dashboard docs at `https://hermes-agent.nousresearch.com/docs`.

## Best Practices

### DO:
- Use `hermes -z` for quick questions and smoke tests
- Use `hermes cron create` for async, long-running tasks
- Use Kanban for complex, multi-step work that needs tracking
- Use `hermes chat` for interactive exploration
- Always activate the venv: `. /opt/hermes/.venv/bin/activate && hermes ...`
- Use `timeout` to prevent hanging CLI calls

### DON'T:
- Don't use `-z` for tasks that take minutes — it will block and timeout
- Don't modify agent config files while the agent is running (it may reload unexpectedly)
- Don't bypass the Kanban dispatcher for multi-agent work — it handles dependencies, retries, and workspace isolation
- Don't hardcode profile names in task assignments — discover available profiles first via `hermes profile list`

## TUI Integration

The HermesHotel TUI (`hermes-tui.py`) provides:
- **Chat with Agent** (menu `c`) — wraps `docker exec ... hermes chat`
- **Test API / Flowwink** (menu `6`) — runs smoke tests via `hermes -z`
- **Add Instance** (menu `a`) — creates new profiles and containers
- **Config Files** (menu `8`) — edit `.env`, compose, profiles directly

## Dispatching a Long-Running Task (Example)

For the Flowwink MCP systematic scan (265 tools):

```bash
# Method 1: Cron (recommended for async)
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes cron create 0 "
SYSTEMATIC FLOWWINK MCP SCAN:
1. List all tools via MCP tools/list
2. For each tool, call it with minimal params
3. Report findings via openclaw_report_finding with proper type/title
4. Summarize when done
"'

# Method 2: Kanban (if you need tracking/review)
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes kanban create \
  --title "Flowwink MCP Full Scan" \
  --body "Test all 265 tools. Report via openclaw_report_finding. Types: bug, ux_issue, suggestion, positive, performance, missing_feature."'

# Method 3: Chat (blocks until done — use with long timeout)
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && timeout 600 hermes chat -q "
Flowwink MCP Systematic Scan: test all 265 tools and report findings..."
```

## Monitoring

```bash
# Check kanban tasks
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes kanban list'

# Check cron jobs
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes cron list'

# Check sessions
docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes sessions list'

# View agent logs
docker compose -f docker-compose.yml logs -f hermes-operator
```
