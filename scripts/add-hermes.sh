#!/usr/bin/env bash
# Add a new Hermes agent from operator template.
# Usage: ./scripts/add-hermes.sh <profile-name> [domain]
# Example: ./scripts/add-hermes.sh sales sales.example.com

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

PROFILE="$1"
DOMAIN="$2"
if [ -z "$PROFILE" ]; then
  echo "Usage: $0 <profile-name> [domain]  (e.g. $0 sales sales.example.com)"
  exit 1
fi

if [ -d "profiles/$PROFILE" ]; then
  # Profile already exists — use it as-is (first-run with operator template)
  info "profiles/$PROFILE already exists — using existing profile"
else
  # Copy operator template
  info "Copying profiles/operator → profiles/$PROFILE"
  cp -r profiles/operator "profiles/$PROFILE"
fi

# ── Update instances.json (append new agent) ──
info "Updating instances.json"
python3 - "$PROFILE" "$DOMAIN" <<'PY'
import sys, json, os
profile = sys.argv[1]
domain = sys.argv[2]
root = "/opt/hermeshotel"
inst_path = os.path.join(root, "instances.json")
with open(inst_path) as f:
    data = json.load(f)
instances = data.get("instances", [])
used_ports = [i.get("port", 0) for i in instances if i.get("port")]
next_port = max(used_ports + [3000]) + 1
new_inst = {
    "name": profile,
    "label": profile.capitalize() + " Agent",
    "domain": domain,
    "port": next_port,
    "container": f"hermes-{profile}",
    "emoji": "🤖",
    "profile": profile,
    "active": True
}
instances.append(new_inst)
with open(inst_path, "w") as f:
    json.dump(data, f, indent=2)
print(f"✔ instances.json updated — port {next_port}, domain {domain}")
PY

# ── Ensure session token in .env ──
profile_upper=$(echo "$PROFILE" | tr '[:lower:]' '[:upper:]')
token_var="HERMES_SESSION_TOKEN"
if ! grep -q "^${token_var}=" .env; then
  token_val="hermes-${PROFILE}-$(openssl rand -hex 8)"
  echo "${token_var}=${token_val}" >> .env
  info "Added ${token_var} to .env"
else
  info "${token_var} already in .env"
fi

# ── Update Caddyfile with new domain ──
CADDYFILE="config/Caddyfile"
if [ -f "$CADDYFILE" ]; then
  # Check if domain already exists in Caddyfile
  if ! grep -q "$DOMAIN" "$CADDYFILE"; then
    # Get the host port for this container from compose
    HOST_PORT=$(docker compose -f docker-compose.yml config 2>/dev/null | grep -A2 "hermes-$PROFILE" | grep "127.0.0.1" | head -1 | sed 's/.*127.0.0.1:\([0-9]*\):3000.*/\1/')
    if [ -z "$HOST_PORT" ]; then
      # Calculate from instances.json
      HOST_PORT=$(python3 -c "
import json
with open('instances.json') as f:
    data = json.load(f)
for i in data.get('instances', []):
    if i['name'] == '$PROFILE':
        print(i.get('port', 3000))
        break
")
    fi
    # Add Caddy block for new domain
    cat >> "$CADDYFILE" <<CADDEOF

$DOMAIN {
  reverse_proxy 127.0.0.1:${HOST_PORT}
}
CADDEOF
    info "Added $DOMAIN → 127.0.0.1:${HOST_PORT} to Caddyfile"
    info "Run: sudo caddy reload"
  else
    info "$DOMAIN already in Caddyfile"
  fi
fi

# ── Regenerate docker‑compose.yml ──
info "Regenerating docker-compose.yml"
python3 scripts/generate-compose.py

# ── Start the new container ──
info "Starting hermes-$PROFILE"
docker compose -f docker-compose.yml up -d "hermes-$PROFILE"

echo ""
info "Added hermes-$PROFILE successfully"
echo "  Domain: $DOMAIN"
echo "  TUI:    python3 hermes-tui.py"
echo "  Web:    python3 hermes-web.py"
echo "  Logs:   docker compose -f docker-compose.yml logs -f hermes-$PROFILE"
echo ""
echo "Remember: sudo caddy reload  (to apply new domain)"
