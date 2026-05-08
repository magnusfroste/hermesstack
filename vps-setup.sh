#!/bin/bash
# Hermes Multi-Agent VPS Setup Script
# Kör på ny Ubuntu VPS (Hetzner, DigitalOcean, etc.)

set -e

echo "🚀 Hermes Multi-Agent VPS Setup"
echo "================================"

# 1. Uppdatera systemet
echo "📦 Uppdaterar systemet..."
apt-get update && apt-get upgrade -y

# 2. Installera Docker
echo "🐳 Installerar Docker..."
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER

# 3. Installera Docker Compose
echo "🐳 Installerar Docker Compose..."
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# 4. Installera Caddy
echo "🌐 Installerar Caddy..."
apt-get install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt-get update
apt-get install -y caddy

# 5. Skapa projektkatalog
echo "📁 Skapar projektkatalog..."
mkdir -p /opt/hermesstack
cd /opt/hermesstack

# 6. Klona repo
echo "⬇️ Klonar repository..."
git clone https://github.com/magnusfroste/hermesstack.git .

# 7. Skapa .env fil (användaren måste fylla i)
echo "📝 Skapar .env fil..."
cat > .env << 'EOF'
# ============================================
# LLM PROVIDERS (minst en krävs)
# ============================================
OPENAI_API_KEY=sk-...  # Fyll i din OpenAI API-nyckel

# ============================================
# HERMES KONFIGURATION
# ============================================
HERMES_MODEL=openai/gpt-4o-mini

# ============================================
# FLOWWINK MCP
# ============================================
FLOWWINK_API_KEY=fwk_1cf484bf2fe6cd480b20ac7af53d5cf2dae5382f1a7c51c3f5042dd8bc26a369

# ============================================
# SESSION TOKENS (statiska för API-åtkomst)
# ============================================
HERMES_OPERATOR_TOKEN=hermes-operator-secret-token-2024-magnusfroste
HERMES_CUSTOMER_TOKEN=hermes-customer-secret-token-2024-magnusfroste
HERMES_SUPPLIER_TOKEN=hermes-supplier-secret-token-2024-magnusfroste
EOF

echo "⚠️  VIKTIGT: Redigera /opt/hermesstack/.env och fyll i din OPENAI_API_KEY!"

# 8. Installera Caddy-konfiguration
echo "🌐 Installerar Caddy-konfiguration..."
cp Caddyfile /etc/caddy/Caddyfile
systemctl reload caddy

# 9. Starta tjänster
echo "🏃 Startar Hermes Multi-Agent..."
docker-compose up -d

echo ""
echo "✅ Setup färdigt!"
echo "=================="
echo "Redigera: nano /opt/hermesstack/.env"
echo "Starta om: docker-compose up -d"
echo "Se loggar: docker-compose logs -f"
echo ""
echo "Domäner:"
echo "  - https://customer.hermes.froste.eu"
echo "  - https://operator.hermes.froste.eu"
echo "  - https://supplier.hermes.froste.eu"
