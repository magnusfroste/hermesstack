# Hermes Multi-Agent - VPS Setup Guide

Snabbstart för Hetzner/DigitalOcean VPS med Caddy som reverse proxy.

## Arkitektur

```
┌─────────────────────────────────────────┐
│  Din VPS (Ubuntu 22.04+)                │
│                                         │
│  Caddy (:80, :443)                      │
│    ├── customer.hermes.froste.eu → :3001
│    ├── operator.hermes.froste.eu → :3002
│    └── supplier.hermes.froste.eu → :3003│
│                                         │
│  Docker Compose                         │
│    ├── hermes-customer  (:3001)         │
│    ├── hermes-operator  (:3002)         │
│    ├── hermes-supplier  (:3003)         │
│    └── redis                          │
└─────────────────────────────────────────┘
```

## Steg-för-steg

### 1. Skapa VPS
- Hetzner CX11 (2 vCPU, 4GB RAM, €4.51/mån)
- Ubuntu 22.04 LTS
- Brandvägg: Tillåt port 80, 443, 22

### 2. DNS Setup
```
A-record: customer.hermes.froste.eu → DIN_VPS_IP
A-record: operator.hermes.froste.eu → DIN_VPS_IP
A-record: supplier.hermes.froste.eu → DIN_VPS_IP
```

### 3. Kör Setup Script
```bash
# SSH till VPS
ssh root@DIN_VPS_IP

# Kör setup
curl -fsSL https://raw.githubusercontent.com/magnusfroste/hermesstack/main/vps-setup.sh | bash

# Eller manuellt:
git clone https://github.com/magnusfroste/hermesstack.git /opt/hermesstack
cd /opt/hermesstack
./vps-setup.sh
```

### 4. Konfigurera miljövariabler
```bash
nano /opt/hermesstack/.env
```

Fyll i:
```bash
OPENAI_API_KEY=sk-...  # Din OpenAI API-nyckel
```

### 5. Starta tjänster
```bash
cd /opt/hermesstack
docker-compose -f docker-compose.vps.yml up -d
```

### 6. Verifiera
```bash
# Se loggar
docker-compose -f docker-compose.vps.yml logs -f

# Testa API
curl https://operator.hermes.froste.eu/api/status
```

## Användbara kommandon

| Kommando | Beskrivning |
|----------|-------------|
| `docker-compose logs -f hermes-operator` | Se Operator-loggar |
| `docker-compose logs -f hermes-customer` | Se Customer-loggar |
| `docker-compose logs -f hermes-supplier` | Se Supplier-loggar |
| `docker-compose ps` | Status på alla tjänster |
| `docker-compose restart` | Starta om allt |
| `docker-compose down` | Stoppa allt |
| `docker-compose up -d` | Starta allt |

## Caddy-konfiguration

Caddy hanterar automatiskt SSL-certifikat via Let's Encrypt.

### Caddy Admin
```bash
# Se Caddy-konfiguration
caddy list-modules

# Reload Caddy efter ändringar
systemctl reload caddy

# Se Caddy-loggar
journalctl -u caddy -f
```

### Troubleshooting

**Problem: Domänen svarar inte**
```bash
# Kolla DNS
dig customer.hermes.froste.eu

# Kolla Caddy
curl -I https://customer.hermes.froste.eu

# Kolla att containern körs
docker ps
```

**Problem: SSL-certifikat fungerar inte**
```bash
# Se Caddy-logs
journalctl -u caddy -f

# Testa Let's Encrypt
caddy validate --config /etc/caddy/Caddyfile
```

**Problem: Container kraschar**
```bash
# Se logs
docker-compose logs hermes-operator

# Restart
docker-compose restart hermes-operator
```

## Säkerhet

- Agenter exponeras bara lokalt (`127.0.0.1:3001-3003`)
- Endast Caddy (port 80/443) är publikt tillgänglig
- Auto-SSL via Let's Encrypt
- Ingen Traefik-komplexitet!

## API Access

När allt är igång kan jag (som AI-assistent) prata med agenter:

```bash
# WebSocket till Operator
wscat -c "wss://operator.hermes.froste.eu/api/ws?token=hermes-operator-secret-token-2024-magnusfroste"

# HTTP API
curl "https://operator.hermes.froste.eu/api/sessions/xyz/messages?token=hermes-operator-secret-token-2024-magnusfroste"
```

## Kostnad

- **VPS**: ~€4.51/mån (Hetzner CX11)
- **OpenAI API**: Beroende på användning (~$5-20/mån för test)
- **Domän**: ~€10-15/år
- **Totalt**: ~€10-20/mån
