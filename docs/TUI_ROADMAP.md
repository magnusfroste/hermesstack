# Hermes TUI Roadmap - Fullständig CLI Dashboard

Vision: Ett Arcane-inspirerat TUI för total kontroll över Hermes-agenter.

## ✅ Fas 1: Monitoring (KLAR)
- [x] Container status (running/stopped)
- [x] CPU/RAM stats
- [x] Logg-viewer
- [x] Auto-refresh

## 🚧 Fas 2: Kontroll (NÄSTA)
- [ ] **Profil-hantering**
  - [ ] Lista tillgängliga profiler (`ls profiles/`)
  - [ ] Ladda profil: `customer`, `operator`, `supplier`
  - [ ] Byta profil i realtid (restart container)
  - [ ] Visa aktiv profil config

- [ ] **LLM Endpoint Management**
  - [ ] Byta modell: GPT-4, Claude, etc.
  - [ ] Ändra API-nycklar
  - [ ] Växla mellan OpenAI/Anthropic/local
  - [ ] Testa endpoint (ping)

- [ ] **Image Management**
  - [ ] Check för nyare image på GitHub
  - [ ] Pull & rebuild vid behov
  - [ ] Visa versionshistorik
  - [ ] Rollback till tidigare version

## 🎯 Fas 3: Chat i TUI (SPECIAL)
- [ ] **Inbyggd chat-klient**
  - [ ] Skriva meddelanden direkt i TUI
  - [ ] Se svar i realtid
  - [ ] Historik-scroll
  - [ ] Multi-session support
  
- [ ] **Split-view:**
  ```
  ┌─────────────────┬─────────────────┐
  │  AGENT STATUS   │   CHAT LOG      │
  │  🟢 Operator    │   > Hej!        │
  │  🟢 Customer    │   < Hej! Jag... │
  │  🔴 Supplier    │   > Vad kan...  │
  └─────────────────┴─────────────────┘
  │ PROMPT: [Skriv här...]            │
  └───────────────────────────────────┘
  ```

## 🚀 Fas 4: Avancerat (FRAMTID)
- [ ] **MCP Server Management**
  - [ ] Lista aktiva MCP servrar
  - [ ] Aktivera/avaktivera Flowwink
  - [ ] Testa MCP tools
  - [ ] Se MCP logs

- [ ] **Gateway Control**
  - [ ] Starta/stoppa Telegram/Discord/Slack
  - [ ] Konfigurera tokens
  - [ ] Se gateway logs

- [ ] **Autonomous Mode**
  - [ ] Aktivera "Auto-pilot" för agenter
  - [ ] Schemalägg uppgifter (cron)
  - [ ] Se autonoma actions i realtid

## 🎨 UI Design (Arcane Style)

```
╔══════════════════════════════════════════════════════════════════╗
║  🏛️ HERMES COMMAND CENTER  │  Operator │ v0.13.0                ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ┌─ AGENTS ─────────────────────────────────────────────────┐   ║
║  │ 🟢 Operator  │ GPT-4 │ Running │ 14 tools │ 3 sessions  │   ║
║  │ 🟢 Customer  │ GPT-4 │ Running │ 8 tools  │ 1 session   │   ║
║  │ 🔴 Supplier  │ ---   │ Stop    │ 0 tools  │ 0 sessions  │   ║
║  └──────────────────────────────────────────────────────────┘   ║
║                                                                  ║
║  ┌─ CHAT ───────────────────────────────────────────────────┐   ║
║  │ 12:05:30 > Hej! Vad kan du göra?                      │   ║
║  │ 12:05:35 < Jag kan hantera BSS/ERP via Flowwink MCP   │   ║
║  │ 12:05:35 < Jag har tillgång till 224+ verktyg       │   ║
║  │                                                         │   ║
║  │ > [Skriv här...]                                      │   ║
║  └──────────────────────────────────────────────────────────┘   ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║  [P] Profil  [L] LLM  [I] Image  [C] Chat  [S] Stats  [Q] Quit  ║
╚══════════════════════════════════════════════════════════════════╝
```

## Teknisk Implementation

### Alternativ A: Rich (Python)
```python
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt

# Avancerad TUI med Rich
console = Console()
```

### Alternativ B: Textual (Python)
```python
from textual.app import App
from textual.widgets import DataTable, Input, Log

# Full React-liknande TUI
```

### Alternativ C: Charm (Go)
```go
// Bubble Tea framework
// Mer prestanda, men kräver Go
```

## Prioritering

| Feature | Prioritet | Tid | Beskrivning |
|---------|-----------|-----|-------------|
| Profil-byta | 🔥 HIGH | 2h | Byta customer↔operator↔supplier |
| LLM-byta | 🔥 HIGH | 1h | Växla OpenAI/Claude |
| Chat i TUI | 🔥 HIGH | 3h | WebSocket chat direkt i terminal |
| Image-check | MEDIUM | 1h | Se om ny version finns |
| MCP management | LOW | 4h | Konfigurera Flowwink etc. |

## Nästa steg

**Imorgon kan vi bygga:**
1. **Profil-switcher** - Byta mellan agenter utan rebuild
2. **LLM-selector** - Byta modell i realtid
3. **Chat-TUI** - Chatta direkt från terminalen

**Vill du att vi fokuserar på detta imorgon?** 🚀

*Just nu: Vänta på att VPS-bygget slutförs, sen kan vi testa grundfunktionaliteten!*
