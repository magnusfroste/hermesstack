# 🏨 HermesHotel — Self-Hosted AI Agent Stack

Ett användarvänligt **TUI-dashboard** för att hantera en stack av autonoma AI-agenter (Hermes).
Self-hosted, privat, och enkelt att sätta upp på valfri VPS.

```
╔══════════════════════════════════════════════════════════════╗
║  🏛️ HERMES COMMAND CENTER  |  v0.14.0  |  2026-05-13      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  ┌─ SYSTEM ────────────────────────────────────────────┐    ║
║  │ System: up 5 days | Mem: 1234MB (62%) | Load: 0.52 │    ║
║  └─────────────────────────────────────────────────────┘    ║
║                                                              ║
║  ┌─ AGENTS ────────────────────────────────────────────┐    ║
║  │ STATUS   NAME        DOMAIN              MODEL      │    ║
║  │ ● UP     CUSTOMER    customer.froste.eu  gpt-4o-mini│    ║
║  │ ● UP     OPERATOR    operator.froste.eu  gpt-4o-mini│    ║
║  │ ● UP     SUPPLIER    supplier.froste.eu  gpt-4o-mini│    ║
║  └─────────────────────────────────────────────────────┘    ║
║                                                              ║
║  ┌─ DOMAINS ───────────────────────────────────────────┐    ║
║  │ Global model: openai/gpt-4o-mini                    │    ║
║  │ Config:   /opt/hermeshotel/.env                     │    ║
║  │ Compose:  /opt/hermeshotel/deploy/vps/...           │    ║
║  └─────────────────────────────────────────────────────┘    ║
║                                                              ║
║  [1] Dashboard  [2] Update  [3] Model  [4] Logs             ║
║  [5] Restart    [6] Test   [7] Config [8] Chat  [Q] Quit    ║
╚══════════════════════════════════════════════════════════════╝
```

## Funktioner

| Funktion | Beskrivning |
|----------|-------------|
| 🖥️ **Arcane TUI Dashboard** | Full kontroll i terminalen — status, loggar, konfiguration |
| 💬 **Inbyggd Chat** | Chatta med valfri agent direkt från TUI:n |
| 🔒 **Self-Hosted** | Allt kör på din egen VPS — inga tredjeparter |
| 🤖 **Privat LLM** | Stöd för lokal/privat LLM eller moln-LLM |
| 🌐 **Auto-HTTPS** | Caddy reverse proxy med Let's Encrypt |
| 🔄 **3 Agenter** | Customer, Operator, Supplier — samarbetar autonomt |
| 🛠️ **MCP Integration** | Flowwink MCP med 200+ verktyg |

## Snabbstart

### 1. Krav
- **VPS**: Ubuntu 22.04+ (min 4GB RAM, 2 vCPU)
- **Docker** + **Docker Compose**
- **Domän** med DNS pekande mot VPS:ens IP

### 2. DNS Setup
```
customer.froste.eu    A    DIN_VPS_IP
operator.froste.eu    A    DIN_VPS_IP
supplier.froste.eu    A    DIN_VPS_IP
```

### 3. Klona repo
```bash
git clone https://github.com/magnusfroste/hermesstack.git /opt/hermeshotel
cd /opt/hermeshotel
```

### 4. Konfigurera
```bash
cp .env.example .env
nano .env
# Fyll i:
#   OPENAI_API_KEY=sk-...
#   HERMES_CUSTOMER_TOKEN=...
#   HERMES_OPERATOR_TOKEN=...
#   HERMES_SUPPLIER_TOKEN=...
```

### 5. Installera Caddy
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install caddy

# Kopiera konfig
cp deploy/vps/Caddyfile /etc/caddy/Caddyfile
sudo systemctl enable caddy && sudo systemctl start caddy
```

### 6. Starta agenter
```bash
cd /opt/hermeshotel/deploy/vps
docker compose -f docker-compose.vps.yml --env-file /opt/hermeshotel/.env up -d
```

### 7. Starta gateways
```bash
docker exec -d hermes-customer python -m hermes_cli.main gateway run
docker exec -d hermes-operator python -m hermes_cli.main gateway run
docker exec -d hermes-supplier python -m hermes_cli.main gateway run
```

### 8. Öppna TUI
```bash
cd /opt/hermeshotel/deploy/vps
python3 hermes-tui.py
```

## Hantera Agenterna via TUI

| Tangent | Funktion |
|---------|----------|
| **1** | Status Dashboard (live uppdatering) |
| **2** | Uppdatera alla agenter (pull + rebuild) |
| **3** | Byt LLM-modell (GPT-4, Claude, etc.) |
| **4** | Visa loggar (scrollbar per agent) |
| **5** | Starta om agent |
| **6** | Testa API och Flowwink MCP |
| **7** | Visa/edit miljövvariabler |
| **8** | **Chatta med agent** (skicka uppdrag!) |
| **R** | Uppdatera dashboard |
| **Q** | Avsluta |

## Kommunikation med Agenter

### Via TUI (Rekommenderat)
Tryck **8** i dashboarden och skriv ditt meddelande. Fungerar med alla tre agenter.

### Via Web
- `https://customer.froste.eu` — Kundagentens dashboard
- `https://operator.froste.eu` — Operatörens dashboard
- `https://supplier.froste.eu` — Leverantörens dashboard

### Via CLI
```bash
docker exec hermes-operator python -m hermes_cli.main chat -q "Ditt meddelande" -Q --provider openai -m gpt-4o-mini
```

## LLM-Konfiguration

### Moln-LLM (OpenAI)
```bash
# .env
OPENAI_API_KEY=sk-...
HERMES_MODEL=gpt-4o-mini
```

### Privat/Lokal LLM
```yaml
# profiles/operator/config.yaml
providers:
  local:
    api_key_env: LOCAL_API_KEY
    api_mode: chat_completions
    base_url: http://localhost:11434/v1  # t.ex. Ollama
    default_model: llama3

model: local/llama3
```

## Arkitektur

```
┌─────────────────────────────────────────────────────────┐
│                    DU / ADMIN                            │
│              Python TUI Dashboard                        │
└──────────────┬──────────────┬───────────────────────────┘
               │              │
          ┌────▼────┐    ┌───▼─────┐
          │Customer │    │Operator │
          │  :3001  │    │  :3002  │
          └────┬────┘    └────┬────┘
               │               │
          ┌────▼───────────────▼────┐
          │      FLOWWINK MCP       │
          │   200+ verktyg/API:er   │
          └───────────┬─────────────┘
                      │
               ┌──────▼──────┐
               │  Supplier   │
               │   :3003     │
               └─────────────┘
```

## Filstruktur

```
hermeshotel/
├── deploy/vps/
│   ├── docker-compose.vps.yml   # Docker-konfiguration
│   ├── Caddyfile                # Reverse proxy + HTTPS
│   ├── Dockerfile.multi-agent   # Agent-bygge
│   └── hermes-tui.py            # TUI Dashboard
├── profiles/
│   ├── customer/config.yaml     # Kundagentens konfig
│   ├── operator/config.yaml     # Operatörens konfig
│   └── supplier/config.yaml     # Leverantörens konfig
└── .env                         # Miljövariabler
```

## Verktyg per Agent

Alla agenter har generösa toolsets aktiverade:

| Toolset | Beskrivning |
|---------|-------------|
| **core** | Grundläggande AI-kapacitet |
| **web_search** | Söka information på webben |
| **terminal** | Köra shell-kommandon |
| **files** | Läsa, skriva, söka i filer |
| **delegate** | Delegera uppgifter till andra agenter |

## Felsökning

### Gateway inte igång
```bash
docker exec hermes-operator python -m hermes_cli.main gateway run
```

### Caddy problem
```bash
journalctl -u caddy -f
caddy validate --config /etc/caddy/Caddyfile
```

### Container problem
```bash
docker compose -f docker-compose.vps.yml logs -f hermes-operator
docker compose -f docker-compose.vps.yml ps
```

## Kostnad

| Komponent | Kostnad |
|-----------|---------|
| VPS (Hetzner CX11) | ~€4.51/mån |
| OpenAI API | ~$5-20/mån |
| Domän | ~€10-15/år |
| **Totalt** | ~€10-20/mån |

---

**HermesHotel** — Hantera din AI-agent-stack från terminalen. Self-hosted, privat, enkelt.
