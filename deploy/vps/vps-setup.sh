#!/bin/bash
# =============================================================================
# Hermes Multi-Agent - One-Command VPS Setup
# Usage: curl -fsSL https://raw.githubusercontent.com/magnusfroste/hermesstack/main/deploy/vps/vps-setup.sh | bash
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║         Hermes Multi-Agent VPS Setup v2.0              ║"
echo "║   Customer • Operator • Supplier + Flowwink MCP        ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Helper functions ──
prompt() {
    local label="$1" default="$2"
    if [ -n "$default" ]; then
        read -rp "${BLUE}${label}${NC} [${YELLOW}${default}${NC}]: " input
        echo "${input:-$default}"
    else
        read -rp "${BLUE}${label}${NC}: " input
        echo "$input"
    fi
}

info()    { echo -e "${GREEN}✓${NC} $1"; }
warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
error()   { echo -e "${RED}✗${NC} $1"; }
step()    { echo -e "\n${CYAN}▸${NC} ${BLUE}$1${NC}"; }

# ── Interactive Configuration ──
step "Configuration"
echo -e "${YELLOW}Press Enter to use default values in [brackets].${NC}"
echo ""

BASE_DOMAIN=$(prompt "Base domain (3 subdomains will be created)" "hermes.example.com")
OPENAI_KEY=$(prompt "OpenAI API key (sk-proj-...)" "")
ANTHROPIC_KEY=$(prompt "Anthropic API key (optional, sk-ant-...)" "")
FLOWWINK_KEY=$(prompt "Flowwink API key (optional, fwk_...)" "")

# Validate OpenAI key
if [ -z "$OPENAI_KEY" ]; then
    error "OpenAI API key is required. Exiting."
    exit 1
fi

# Generate unique session tokens
OPERATOR_TOKEN="hermes-op-$(openssl rand -hex 8)"
CUSTOMER_TOKEN="hermes-cu-$(openssl rand -hex 8)"
SUPPLIER_TOKEN="hermes-su-$(openssl rand -hex 8)"

# Derive subdomains
DOMAIN_BASE="${BASE_DOMAIN#*.}"
CUSTOMER_DOMAIN="customer.${DOMAIN_BASE}"
OPERATOR_DOMAIN="operator.${DOMAIN_BASE}"
SUPPLIER_DOMAIN="supplier.${DOMAIN_BASE}"

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "  Domains:  ${CYAN}${CUSTOMER_DOMAIN}${NC}, ${CYAN}${OPERATOR_DOMAIN}${NC}, ${CYAN}${SUPPLIER_DOMAIN}${NC}"
echo -e "  OpenAI:   ${CYAN}${OPENAI_KEY:0:12}...${NC}"
echo -e "  Tokens:   Generated automatically"
echo ""

read -rp "${YELLOW}Continue with this configuration? [Y/n] ${NC}" confirm
if [[ "$confirm" =~ ^[Nn]$ ]]; then
    echo -e "${RED}Aborted.${NC}"
    exit 0
fi

# ── System Setup ──
step "Installing system dependencies"

apt-get update && apt-get upgrade -y

# Docker (with compose plugin)
if ! command -v docker &>/dev/null; then
    info "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    info "Docker already installed: $(docker --version)"
fi

# Ensure docker compose v2 is available
if ! docker compose version &>/dev/null; then
    info "Installing docker compose plugin..."
    apt-get install -y docker-compose-plugin
fi

# Caddy
if ! command -v caddy &>/dev/null; then
    info "Installing Caddy..."
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
    systemctl enable caddy
else
    info "Caddy already installed: $(caddy version)"
fi

# ── Deploy ──
step "Deploying Hermes Multi-Agent"

mkdir -p /opt/hermesstack
cd /opt/hermesstack

if [ -d ".git" ]; then
    info "Pulling latest version..."
    git pull origin main 2>/dev/null || true
else
    info "Cloning repository..."
    git clone https://github.com/magnusfroste/hermesstack.git .
fi

# Create .env with user values
info "Creating .env configuration..."
cat > .env << ENVEOF
# ─────────────────────────────────────────────
# Hermes Multi-Agent Configuration
# Generated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
# ─────────────────────────────────────────────

# LLM Provider (at least one required)
OPENAI_API_KEY=${OPENAI_KEY}
${ANTHROPIC_KEY:+ANTHROPIC_API_KEY=${ANTHROPIC_KEY}}

# Default model
HERMES_MODEL=openai/gpt-4o-mini

# Flowwink MCP (operator only)
${FLOWWINK_KEY:+FLOWWINK_API_KEY=${FLOWWINK_KEY}}

# Session tokens (unique per installation)
HERMES_OPERATOR_TOKEN=${OPERATOR_TOKEN}
HERMES_CUSTOMER_TOKEN=${CUSTOMER_TOKEN}
HERMES_SUPPLIER_TOKEN=${SUPPLIER_TOKEN}

# Logging
HERMES_LOG_LEVEL=info
PYTHONUNBUFFERED=1
ENVEOF

# Configure Caddy
info "Configuring Caddy reverse proxy..."
sed -e "s/customer\.hermes\.example\.com/${CUSTOMER_DOMAIN}/g" \
    -e "s/operator\.hermes\.example\.com/${OPERATOR_DOMAIN}/g" \
    -e "s/supplier\.hermes\.example\.com/${SUPPLIER_DOMAIN}/g" \
    deploy/vps/Caddyfile.template > /etc/caddy/Caddyfile 2>/dev/null || \
cp deploy/vps/Caddyfile /etc/caddy/Caddyfile

systemctl reload caddy

# ── Start Services ──
step "Starting containers"

# Use docker compose (v2) with fallback to docker-compose (v1)
DC_CMD="docker compose"
if ! docker compose version &>/dev/null; then
    DC_CMD="docker-compose"
fi

cd /opt/hermesstack
$DC_CMD -f deploy/vps/docker-compose.vps.yml pull 2>/dev/null || true
$DC_CMD -f deploy/vps/docker-compose.vps.yml up -d --build

# ── Health Check ──
step "Verifying services"
sleep 10

MAX_RETRIES=30
RETRY=0
ALL_HEALTHY=false

while [ $RETRY -lt $MAX_RETRIES ]; do
    STATUS=$($DC_CMD -f deploy/vps/docker-compose.vps.yml ps --format json 2>/dev/null || \
             $DC_CMD -f deploy/vps/docker-compose.vps.yml ps --format '{{.Name}}\t{{.Status}}' 2>/dev/null)

    if echo "$STATUS" | grep -q "healthy"; then
        HEALTHY_COUNT=$(echo "$STATUS" | grep -c "healthy" || true)
        if [ "$HEALTHY_COUNT" -ge 3 ]; then
            ALL_HEALTHY=true
            break
        fi
    fi

    RETRY=$((RETRY + 1))
    sleep 5
done

# ── Results ──
echo ""
if $ALL_HEALTHY; then
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ✓ Hermes Multi-Agent is running!               ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Domains (point DNS A-records to this VPS IP):${NC}"
    echo -e "  Customer:  ${CYAN}https://${CUSTOMER_DOMAIN}${NC}"
    echo -e "  Operator:  ${CYAN}https://${OPERATOR_DOMAIN}${NC}"
    echo -e "  Supplier:  ${CYAN}https://${SUPPLIER_DOMAIN}${NC}"
    echo ""
    echo -e "${BLUE}Session Tokens (save these!):${NC}"
    echo -e "  Operator:  ${YELLOW}${OPERATOR_TOKEN}${NC}"
    echo -e "  Customer:  ${YELLOW}${CUSTOMER_TOKEN}${NC}"
    echo -e "  Supplier:  ${YELLOW}${SUPPLIER_TOKEN}${NC}"
    echo ""
    echo -e "${BLUE}Management:${NC}"
    echo -e "  Logs:       ${CYAN}cd /opt/hermesstack && docker compose -f deploy/vps/docker-compose.vps.yml logs -f${NC}"
    echo -e "  Status:     ${CYAN}cd /opt/hermesstack && docker compose -f deploy/vps/docker-compose.vps.yml ps${NC}"
    echo -e "  TUI:        ${CYAN}cd /opt/hermesstack && python3 deploy/vps/hermes-tui.py${NC}"
    echo ""
else
    echo -e "${YELLOW}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${YELLOW}║   ⚠ Services starting... Check logs for details.       ║${NC}"
    echo -e "${YELLOW}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    $DC_CMD -f deploy/vps/docker-compose.vps.yml ps
    echo ""
    echo -e "${BLUE}View logs:${NC}"
    echo -e "  ${CYAN}cd /opt/hermesstack && docker compose -f deploy/vps/docker-compose.vps.yml logs -f${NC}"
fi
