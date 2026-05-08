# AI Bridge Plugin för Hermes

Ett Hermes-plugin som möjliggör AI-assistent-kommunikation.

## Funktioner

- 🖥️ Ny flik i Hermes UI: **"AI Bridge"**
- 🔌 Backend API: `/api/ai-bridge/chat`
- 💬 Låter AI:n skicka meddelanden till Hermes

## Installation

### Steg 1: Kopiera plugin

SSH till servern och kopiera plugin till Hermes:

```bash
# På servern (Easypanel-instansen)
cd /root/.hermes  # Eller var Hermes home är
mkdir -p plugins
cp -r /opt/hermesstack/plugins/ai-bridge ./plugins/
```

### Steg 2: Installera beroenden

Hermes behöver ladda backend API:n:

```bash
# I Hermes container
cd /app/hermes
pip install -e plugins/ai-bridge
```

### Steg 3: Aktivera plugin

Lägg till i `~/.hermes/config.yaml`:

```yaml
plugins:
  ai-bridge:
    enabled: true
    endpoint: /api/ai-bridge
```

### Steg 4: Starta om Hermes

I Easypanel: **Redeploy**

## Användning

### Via UI:
1. Gå till Hermes dashboard
2. Klicka på fliken **"AI Bridge"** (nya ikonen 🤖)
3. Skriv meddelanden där!

### Via API (för AI-assistent):

```bash
curl -X POST "https://hermes.froste.eu/api/ai-bridge/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hej! Vad kan du göra?",
    "session_id": "optional-existing-session"
  }'
```

Svar:
```json
{
  "success": true,
  "session_id": "xyz-123",
  "hermes_response": {...}
}
```

### Hämta meddelanden:

```bash
curl "https://hermes.froste.eu/api/ai-bridge/sessions/{session_id}/messages"
```

## Säkerhet

⚠️ **Viktigt**: Pluginet är öppet för alla som kan nå Hermes.
För produktion, lägg till:
- API-key validation
- IP-whitelist
- Rate limiting

## Felsökning

### Plugin visas inte:
1. Kolla att filerna finns i `~/.hermes/plugins/ai-bridge/`
2. Se till `manifest.json` är giltig JSON
3. Kolla Hermes-loggar för laddningsfel

### API svarar inte:
1. Verifiera att backend är registrerad: `/api/ai-bridge/`
2. Kolla att Hermes token är satt korrekt

## Utveckling

För att modifiera pluginet:
1. Redigera `index.js` för UI-ändringar
2. Redigera `api.py` för backend-ändringar
3. Starta om Hermes för att ladda nya versionen
