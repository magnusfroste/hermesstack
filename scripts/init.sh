#!/usr/bin/env bash
# HermesHotel Quickstart — one‑command bootstrap
# Run inside cloned repo; creates .env and brings up all agents.

set -e

GREEN='\033[0;32m'; CYAN='\033[0;36m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info() { echo -e "${GREEN}✓${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║          HermesHotel — Multi-Agent Quickstart           ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Check Docker ──
if ! command -v docker &>/dev/null; then
  info "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker && systemctl start docker
else
  info "Docker $(docker --version | cut -d' ' -f3 | tr -d ',')"
fi

if ! docker compose version &>/dev/null; then
  info "Installing docker-compose plugin..."
  apt-get update && apt-get install -y docker-compose-plugin
fi

# ── Prepare repo ──
cd /opt/hermeshotel || { error "Directory not found"; exit 1; }
if [ -d ".git" ]; then
  git pull -q || true
else
  info "Cloning repository..."
  git clone -q <your-repo-url> . || true
fi

# ── .env ──
if [ ! -f .env ]; then
  info "Creating .env (minimal)"
  read -rp "${BLUE}OpenAI API key:${NC} " OPENAI_KEY
  [ -n "$OPENAI_KEY" ] || { echo "✗ OpenAI key required"; exit 1; }
  read -rp "${BLUE}Flowwink API key (optional, fwk_…):${NC} " FLOWWINK_KEY

  # Generate session tokens for default profiles
  OP_TOKEN="hermes-op-$(openssl rand -hex 8)"
  CU_TOKEN="hermes-cu-$(openssl rand -hex 8)"
  SU_TOKEN="hermes-su-$(openssl rand -hex 8)"

  cat > .env <<EOF
OPENAI_API_KEY=${OPENAI_KEY}
HERMES_MODEL=autoversio
${FLOWWINK_KEY:+FLOWWINK_API_KEY=${FLOWWINK_KEY}}
HERMES_OPERATOR_TOKEN=${OP_TOKEN}
HERMES_CUSTOMER_TOKEN=${CU_TOKEN}
HERMES_SUPPLIER_TOKEN=${SU_TOKEN}
HERMES_LOG_LEVEL=info
PYTHONUNBUFFERED=1
EOF
  info ".env created"
else
  info ".env already present — skipping"
fi

# ── Generate compose file ──
info "Generating docker-compose.yml from profiles & instances"
python3 scripts/generate-compose.py

# ── Start containers ──
info "Starting services"
docker compose -f docker-compose.yml pull -q || true
docker compose -f docker-compose.yml up -d

# ── Health check ──
info "Waiting for health..."
sleep 14
if docker compose -f docker-compose.yml ps | grep -q "healthy"; then
  echo ""
  echo -e "${GREEN}✔ HermesHotel is up!${NC}"
  echo ""
  echo "  TUI:      python3 hermes-tui.py"
  echo "  Web:      python3 hermes-web.py  → http://localhost:3099"
  echo "  Logs:     docker compose -f docker-compose.yml logs -f"
else
  echo -e "${YELLOW}⚠ Still starting — check: docker compose -f docker-compose.yml ps${NC}"
fi
