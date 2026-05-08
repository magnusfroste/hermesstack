# Hermes Multi-Agent E-Commerce Setup

## Arkitektur: 3 Agenter med olika roller

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    CUSTOMER     │────▶│     BSS/ERP     │────▶│   SUPPLIER    │
│   (Besökare)    │     │   (Operatör)    │     │  (Leverantör) │
│                 │◄────│                 │◄────│               │
│  - Bläddrar     │     │  - Tar emot     │     │  - Tar emot   │
│  - Lägger order │     │    ordrar       │     │    ordrar     │
│  - Betalar      │     │  - Hanterar     │     │  - Levererar  │
│                 │     │    lager        │     │               │
└─────────────────┘     │  - Skickar till │     └─────────────────┘
                        │    supplier     │
                        │  - Full MCP     │
                        │    till Flowwink│
                        └─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   Flowwink      │
                    │  CMS/CRM/ERP    │
                    │  (200 MCP-ytor) │
                    └─────────────────┘
```

## Profiler

| Profil | Roll | MCP-åtkomst | Huvuduppgift |
|--------|------|-------------|--------------|
| `customer` | E-handelskund | Begränsad | Simulera kundbeteende, lägga ordrar |
| `operator` | BSS-operatör | Full (Flowwink) | Hantera ordrar, lager, kommunikation |
| `supplier` | Leverantör | Begränsad | Ta emot ordrar, bekräfta leverans |

## Teknisk Implementation

### 1. Profilstruktur (HERMES_HOME isolation)

```bash
# Varje agent får egen profil via HERMES_HOME
HERMES_HOME=/data/hermes-profiles/customer   # Kundagent
HERMES_HOME=/data/hermes-profiles/operator   # Operatör med Flowwink MCP
HERMES_HOME=/data/hermes-profiles/supplier   # Leverantörsagent
```

### 2. Konfiguration per profil

**Operator** (`~/.hermes/config.yaml`):
```yaml
personality: bss_operator
mcp_servers:
  flowwink:
    url: https://api.flowwink.com/mcp
    headers:
      Authorization: Bearer ${FLOWWINK_API_KEY}
    timeout: 120
```

**Customer** (`~/.hermes/config.yaml`):
```yaml
personality: ecommerce_customer
goals:
  - "Hitta produkter"
  - "Lägg beställningar"
  - "Få bra priser"
```

**Supplier** (`~/.hermes/config.yaml`):
```yaml
personality: b2b_supplier
goals:
  - "Ta emot ordrar"
  - "Bekräfta leveranstider"
  - "Hantera lager"
```

### 3. Kommunikation mellan agenter

Alternativ:
- **A)** Gateway API endpoints (webhooks mellan agenter)
- **B)** Delad message queue (Redis/PostgreSQL)
- **C)** Direkta HTTP-anrop mellan Hermes-instanser

Rekommendation: **Alternativ A** - Varje agent exponerar API-endpoints via `gateway` eller `dashboard`.

## Deployment

Tre separata Easypanel-tjänster eller en Docker Compose med 3 containrar.
