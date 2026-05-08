# Hermes Multi-Agent E-commerce Stack

Tre autonoma AI-agenter (Customer, Operator, Supplier) som simulerar e-handel/BSS via Flowwink MCP.

## Arkitektur

```
┌─────────────────────────────────────────────────────────────┐
│                    MÄNSKLIG OBSERVATÖR                       │
│                      (Du / Admin)                            │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
         ┌─────▼──────┐               ┌──────▼──────┐
         │  Customer  │               │  Operator   │
         │  Dashboard │◄── Prata ───►│  Dashboard  │
         │  (:3001)   │               │  (:3002)    │
         └─────┬──────┘               └──────┬──────┘
               │  "Vad har du shoppat?"         │  "Godkänn order #123"
               │                                │
         ┌─────▼───────────────────────────▼──────┐
         │            FLOWWINK MCP                   │
         │    • Nyhetsbrev-prenumerationer           │
         │    • Ordrar                               │
         │    • Leverantörs-PO                       │
         │    • Lager                                │
         └──────────────┬─────────────────────────────┘
                        │
              ┌─────────▼────────┐
              │    Supplier      │
              │    Dashboard     │
              │   (:3003)        │
              └──────────────────┘
```

## Tre Agenter

| Agent | Roll | Autonom | Domän | API Token |
|-------|------|---------|-------|-------------|
| **Customer** | E-handelskund | ✅ Ja | `customer.hermes.froste.eu` | `hermes-customer-secret-token-2024-magnusfroste` |
| **Operator** | BSS/ERP Admin | ✅ Ja | `operator.hermes.froste.eu` | `hermes-operator-secret-token-2024-magnusfroste` |
| **Supplier** | Leverantör | ✅ Ja | `supplier.hermes.froste.eu` | `hermes-supplier-secret-token-2024-magnusfroste` |

## Deployment Alternativ

Välj det som passar dig bäst:

### 🚀 Alternativ A: VPS (Rekommenderat)
**För:** Full kontroll, enkla domäner, lätt felsökning

```bash
# På ny Ubuntu VPS
curl -fsSL https://raw.githubusercontent.com/magnusfroste/hermesstack/main/deploy/vps/vps-setup.sh | bash
```

**Fördelar:**
- ✅ Enkel multi-domän setup med Caddy
- ✅ Auto SSL (Let's Encrypt)
- ✅ Fulla Docker logs (`docker-compose logs -f`)
- ✅ Ingen Traefik-komplexitet

**Se:** [`deploy/vps/`](deploy/vps/)

### 🎛️ Alternativ B: Easypanel
**För:** Om du redan använder Easypanel

```bash
# Importera docker-compose.multi-agent.yml i Easypanel
```

**Fördelar:**
- ✅ UI-baserad hantering
- ✅ Automatisk backups
- ⚠️ Multi-domäner kräver manuell config

**Se:** [`deploy/easypanel/`](deploy/easypanel/)

## Snabbstart (VPS)

### 1. Skapa VPS
- **Hetzner**: CX11 (2 vCPU, 4GB RAM) - €4.51/mån
- **OS**: Ubuntu 22.04 LTS

### 2. DNS Setup
```
customer.hermes.froste.eu    A    DIN_VPS_IP
operator.hermes.froste.eu    A    DIN_VPS_IP
supplier.hermes.froste.eu    A    DIN_VPS_IP
```

### 3. Installera
```bash
ssh root@DIN_VPS_IP
curl -fsSL https://raw.githubusercontent.com/magnusfroste/hermesstack/main/deploy/vps/vps-setup.sh | bash
```

### 4. Konfigurera
```bash
nano /opt/hermesstack/.env
# Fyll i: OPENAI_API_KEY=sk-...
```

### 5. Starta
```bash
cd /opt/hermesstack
docker-compose -f deploy/vps/docker-compose.vps.yml up -d
```

### 6. Verifiera
```bash
# Se loggar
docker-compose -f deploy/vps/docker-compose.vps.yml logs -f

# Testa
curl https://operator.hermes.froste.eu/api/status
```

## Kommunikation med Agenter

När agenter är igång kan jag (som AI-assistent) prata med dem:

### WebSocket (Real-tid)
```javascript
// Anslut till Operator
wss://operator.hermes.froste.eu/api/ws?token=hermes-operator-secret-token-2024-magnusfroste

// Skicka meddelande
{"jsonrpc":"2.0","method":"prompt.submit","params":{"session_id":"xyz","text":"Vad har du gjort idag?"}}
```

### HTTP API (Historik)
```bash
# Hämta meddelanden
curl "https://operator.hermes.froste.eu/api/sessions/{id}/messages"
```

## Miljövariabler

```bash
# Required
OPENAI_API_KEY=sk-...              # Din OpenAI API-nyckel

# Optional
HERMES_MODEL=openai/gpt-4o-mini    # LLM modell
HERMES_OPERATOR_TOKEN=...          # Statisk token för API
HERMES_CUSTOMER_TOKEN=...          # Statisk token för API
HERMES_SUPPLIER_TOKEN=...          # Statisk token för API
FLOWWINK_API_KEY=fwk-...           # Flowwink MCP (redan satt)
```

## Användbara Kommandon

| Kommando | Beskrivning |
|----------|-------------|
| `docker-compose logs -f hermes-operator` | Se Operator-loggar live |
| `docker-compose logs -f hermes-customer` | Se Customer-loggar live |
| `docker-compose logs -f hermes-supplier` | Se Supplier-loggar live |
| `docker-compose ps` | Status på alla tjänster |
| `docker-compose restart` | Starta om allt |
| `docker-compose down && docker-compose up -d` | Full restart |

## Felsökning

### Problem: Domänen svarar inte
```bash
# Kolla DNS
dig operator.hermes.froste.eu

# Kolla Caddy
curl -I https://operator.hermes.froste.eu

# Kolla containern
docker ps
docker-compose logs hermes-operator
```

### Problem: SSL-certifikat fungerar inte
```bash
# Se Caddy-logs
journalctl -u caddy -f

# Testa Caddy-konfig
caddy validate --config /etc/caddy/Caddyfile
```

### Problem: Container kraschar
```bash
# Se detaljerade logs
docker-compose logs hermes-operator | tail -50

# Restart
docker-compose restart hermes-operator
```

## Filstruktur

```
hermesstack/
├── deploy/
│   ├── easypanel/           # Easypanel deployment
│   │   ├── docker-compose.multi-agent.yml
│   │   ├── README-EASYPANEL.md
│   │   └── easypanel-*.json
│   └── vps/                 # VPS deployment (rekommenderat)
│       ├── docker-compose.vps.yml
│       ├── Caddyfile
│       ├── vps-setup.sh
│       └── README-VPS.md
├── profiles/                # Agent-konfigurationer
│   ├── customer/
│   ├── operator/
│   └── supplier/
├── Dockerfile.multi-agent   # Multi-agent build
├── .env.example            # Exempel-miljövariabler
└── README.md               # Denna fil
```

## Teknisk Info

- **Hermes Agent**: v0.13.0 (från NousResearch/hermes-agent)
- **MCP Protocol**: Model Context Protocol för verktyg
- **Flowwink**: BSS/ERP/CMS med 224+ verktyg
- **Caddy**: Reverse proxy med auto-SSL
- **Docker**: Container-orkestrering

## Kostnad

| Komponent | Kostnad |
|-----------|---------|
| VPS (Hetzner CX11) | €4.51/mån |
| OpenAI API | ~$5-20/mån (beroende på användning) |
| Domän | ~€10-15/år |
| **Totalt** | ~€10-20/mån |

## Support

- **GitHub Issues**: [magnusfroste/hermesstack](https://github.com/magnusfroste/hermesstack)
- **Dokumentation**: Se respektive `deploy/*/README-*.md`

---

**Redo att dra igång?** Välj VPS eller Easypanel ovan! 🚀
