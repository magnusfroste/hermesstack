# Sätt upp Hermes som Customer Agent

Konfigurera din befintliga Hermes-instans i Easypanel för att agera som autonom kund.

## Steg 1: Environment Variables

I Easypanel, lägg till dessa miljövariabler:

```bash
# LLM
OPENAI_API_KEY=sk-...
HERMES_MODEL=autoversio

# Logging
HERMES_LOG_LEVEL=debug
PYTHONUNBUFFERED=1

# Session token (för API-åtkomst)
HERMES_SESSION_TOKEN=hermes-customer-secret-token-2024-magnusfroste

# Flowwink MCP (redan satt)
FLOWWINK_API_KEY=fwk_36ef2653369bef8c0f0af1290ac0df760e030a351700da4e230d77b2805ae68c
```

## Steg 2: Kopiera profil till container

I Easypanel → Din service → **Volumes**:

Lägg till volume mount:
- **Host Path**: (tom - använd inline config)
- **Container Path**: `/root/.hermes/config.yaml`
- **Content**: Kopiera innehållet från `profiles/customer-simple/config.yaml`

**Alternativ**: Använd Dockerfile som kopierar profilen automatiskt.

## Steg 3: Starta om

Klicka **Redeploy** i Easypanel.

## Steg 4: Verifiera

Gå till `https://hermes.froste.eu/sessions` och skapa en session.

Testa:
```
"Vad kan du göra?"
```

Agenten ska svara att den kan:
- Bläddra produkter
- Lägga beställningar
- Prenumerera på nyhetsbrev
- Ställa frågor

## Autonom drift

Agenten kommer automatiskt (var 30:e minut):
1. Bläddra produkter
2. Ev. lägga beställningar
3. Prenumerera på nyhetsbrev
4. Ställa frågor

## Övervakning

Du kan när som helst gå till dashboard och fråga:
```
"Vad har du gjort idag?"
"Vilka ordrar har du lagt?"
"Vad har du i kundvagnen?"
```

## API Access

Som AI-assistent kan jag prata med kunden via:

```bash
# WebSocket
wss://hermes.froste.eu/api/ws?token=hermes-customer-secret-token-2024-magnusfroste

# HTTP
GET https://hermes.froste.eu/api/sessions/{id}/messages
```

## Felsökning

Om agenten inte ansluter till Flowwink:
```bash
# Kolla logs i Easypanel
docker logs <container-id>

# Verifiera MCP connection
```
