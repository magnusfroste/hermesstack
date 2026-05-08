# AI API Access Setup

För att jag (AI-assistenten) ska kunna prata med Hermes direkt.

## Alternativ 1: Enkelst (rekommenderat)

Du kör API-klienten på din maskin och delar output med mig.

### Steg:

1. **Installera dependencies**:
```bash
pip install httpx websockets
```

2. **Kör en chat**:
```bash
python api_client.py "Hej! Vad kan du göra som kund?"
```

3. **Dela output med mig** - så kan jag se vad Hermes svarade!

---

## Alternativ 2: API Bridge (avancerat)

Skapa en separat endpoint som jag kan anropa direkt.

### Steg:

1. **Lägg till i docker-compose.yml** (för Easypanel-instansen):

```yaml
  api-bridge:
    build:
      context: .
      dockerfile: Dockerfile.bridge
    ports:
      - "8000:8000"
    environment:
      - HERMES_URL=http://hermes:3000
      - HERMES_TOKEN=hermes-customer-secret-token-2024-magnusfroste
    depends_on:
      - hermes
```

2. **Skapa Dockerfile.bridge**:

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn httpx
COPY api_bridge.py .
CMD ["python", "api_bridge.py"]
```

3. **Exponera port 8000 i Easypanel** och mappa en domän till den.

4. **Dela URL med mig** - t.ex. `https://api-hermes.froste.eu/chat`

---

## Test

När det är satt upp kan jag göra:

```bash
# Via curl
curl -X POST https://hermes.froste.eu/api/sessions \
  -H "Authorization: Bearer hermes-customer-secret-token-2024-magnusfroste" \
  -d '{"name": "AI Chat"}'
```

Eller du kör lokalt och delar svaret med mig!

---

**Vilket alternativ föredrar du?** 
- A) Enkelt - du kör skriptet och delar output
- B) Avancerat - API bridge med egen endpoint
