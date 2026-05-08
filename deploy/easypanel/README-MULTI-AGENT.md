# Hermes Multi-Agent E-Commerce Setup

Tre Hermes-agenter som samverkar i ett e-handels/BSS-flöde.

## Arkitektur

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  CUSTOMER   │───▶│   BSS/ERP   │───▶│  SUPPLIER   │
│  (Kund)     │◄───│  (Operatör) │◄───│ (Leverantör)│
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  Flowwink   │
                   │  MCP (200)  │
                   └─────────────┘
```

## Profiler

| Agent | Roll | URL | MCP |
|-------|------|-----|-----|
| `customer` | E-handelskund | customer.hermes.froste.eu | ❌ |
| `operator` | BSS-operatör | operator.hermes.froste.eu | ✅ Flowwink |
| `supplier` | Leverantör | supplier.hermes.froste.eu | ❌ |

## Deploy på Easypanel

### 1. Skapa Docker Compose Service

I Easypanel (easy.froste.eu):
1. **Create Service** → **Docker Compose**
2. Repository: `https://github.com/magnusfroste/hermesstack`
3. Branch: `main`
4. Compose file: `docker-compose.multi-agent.yml`

### 2. Konfigurera Miljövariabler

```bash
# Obligatoriskt
OPENAI_API_KEY=sk-...
FLOWWINK_API_KEY=fw-...  # För operator

# Domäner (sätts automatiskt av Easypanel)
EASYPANEL_DOMAIN_CUSTOMER=customer.hermes.froste.eu
EASYPANEL_DOMAIN_OPERATOR=operator.hermes.froste.eu
EASYPANEL_DOMAIN_SUPPLIER=supplier.hermes.froste.eu
```

### 3. Skapa Domäner

I Easypanel → Domains:
- `customer.hermes.froste.eu` → hermes-customer:3000
- `operator.hermes.froste.eu` → hermes-operator:3000
- `supplier.hermes.froste.eu` → hermes-supplier:3000

### 4. Deploy

Klicka **Deploy** - Easypanel bygger 3 containrar.

## Användning

### Simulera ett köp-flöde:

1. **Kunden besöker BSS:**
   ```
   Gå till: https://customer.hermes.froste.eu
   "Hej! Jag vill köpa 10 st laptops för mitt företag"
   ```

2. **Operatör hanterar order:**
   ```
   Gå till: https://operator.hermes.froste.eu
   Systemet visar inkommande order från kunden
   "Skicka order till leverantör för 10 laptops"
   ```

3. **Leverantör bekräftar:**
   ```
   Gå till: https://supplier.hermes.froste.eu
   "Bekräfta order och leverans inom 3 dagar"
   ```

## Teknisk Arkitektur

### Isolering via HERMES_HOME

Varje agent har egen data- och konfigurationsisolerad miljö:
```
/data/hermes-profiles/
├── customer/   # Kundagentens data
├── operator/   # Operatörens data + Flowwink MCP
└── supplier/   # Leverantörens data
```

### Konfiguration per agent

- `@/Users/mafr/Code/github/hermesstack/profiles/customer/config.yaml` - Kundbeteende
- `@/Users/mafr/Code/github/hermesstack/profiles/operator/config.yaml` - Operatör med MCP
- `@/Users/mafr/Code/github/hermesstack/profiles/supplier/config.yaml` - Leverantörsbeteende

### Kommunikation

Agenter kommunicerar via:
- HTTP API endpoints (via `gateway` eller `dashboard`)
- Delad Redis (valfritt, för message queue)
- Direkta HTTP-anrop mellan containrar

## Filstruktur

```
hermesstack/
├── docker-compose.multi-agent.yml   # Tre agenter + Redis
├── Dockerfile.multi-agent            # Build med profilstöd
├── profiles/
│   ├── customer/config.yaml        # Kundkonfiguration
│   ├── operator/config.yaml          # Operatör + Flowwink MCP
│   └── supplier/config.yaml          # Leverantörskonfig
├── .env.multi-agent.example         # Miljövariabler
└── README-MULTI-AGENT.md            # Denna fil
```

## Nästa Steg

- [ ] Ansluta Flowwink MCP (200 ytor)
- [ ] Sätta upp webhook-endpoints för realtidsnotiser
- [ ] Implementera orderflöde via API-anrop
- [ ] Testa hela kedjan: Kund → Operatör → Leverantör

## Felsökning

### Problem: Agenter kan inte kommunicera
Lösning: Kontrollera att `hermes-network` är korrekt konfigurerad i docker-compose.

### Problem: Flowwink MCP inte ansluten
Lösning: Verifiera `FLOWWINK_API_KEY` är satt för operator-profilen.

### Problem: CORS-fel
Lösning: Dockerfile patchar CORS automatiskt, men verifiera att ändringen applicerades.
