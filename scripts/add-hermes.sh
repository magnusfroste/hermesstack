#!/usr/bin/env bash
# Add a new Hermes agent from operator template.
# Usage: ./scripts/add-hermes.sh <profile-name>
# Example: ./scripts/add-hermes.sh sales

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

PROFILE="$1"
if [ -z "$PROFILE" ]; then
  echo "Usage: $0 <profile-name>  (e.g. $0 sales)"
  exit 1
fi

if [ -d "profiles/$PROFILE" ]; then
  error "profiles/$PROFILE already exists"
  exit 1
fi

# ── Copy operator template ──
info "Copying profiles/operator → profiles/$PROFILE"
cp -r profiles/operator "profiles/$PROFILE"

# ── Update instances.json (append new agent) ──
info "Updating instances.json"
python3 - "$PROFILE" <<'PY'
import sys, json, os
profile = sys.argv[1]
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
    "domain": f"{profile}.froste.eu",
    "port": next_port,
    "container": f"hermes-{profile}",
    "emoji": "🤖",
    "profile": profile,
    "active": True
}
instances.append(new_inst)
with open(inst_path, "w") as f:
    json.dump(data, f, indent=2)
print(f"✔ instances.json updated — port {next_port}")
PY

# ── Ensure session token in .env ──
profile_upper=$(echo "$PROFILE" | tr '[:lower:]' '[:upper:]')
token_var="HERMES_${profile_upper}_TOKEN"
if ! grep -q "^${token_var}=" .env; then
  token_val="hermes-${PROFILE}-$(openssl rand -hex 8)"
  echo "${token_var}=${token_val}" >> .env
  info "Added ${token_var} to .env"
else
  info "${token_var} already in .env"
fi

# ── Regenerate docker‑compose.yml ──
info "Regenerating docker-compose.yml"
python3 scripts/generate-compose.py

# ── Start the new container ──
info "Starting hermes-$PROFILE"
docker compose -f docker-compose.yml up -d "hermes-$PROFILE"

echo ""
info "Added hermes-$PROFILE successfully"
echo "  TUI:  python3 hermes-tui.py      (refresh to see new agent)"
echo "  Web:  python3 hermes-web.py"
echo "  Logs: docker compose -f docker-compose.yml logs -f hermes-$PROFILE"
