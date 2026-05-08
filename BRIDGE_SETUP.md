# HTTP Bridge för AI-kommunikation

Gör så att jag (AI-assistenten) kan prata med Hermes direkt via HTTP.

## Alternativ 1: Lägg till i befintlig Docker Compose (multi-agent)

Om du kör multi-agent via `docker-compose.multi-agent.yml`:

```yaml
  hermes-bridge:
    build:
      context: ./deploy/easypanel
      dockerfile: Dockerfile.bridge
    container_name: hermes-bridge
    restart: unless-stopped
    environment:
      - HERMES_URL=http://hermes-customer:3000  # Eller hermes-operator:3000
      - HERMES_TOKEN=${HERMES_CUSTOMER_TOKEN}
    ports:
      - "8080:8080"
    networks:
      - hermes-network
    depends_on:
      - hermes-customer
```

## Alternativ 2: Separat Easypanel service (för single instance)

Om du har EN Hermes-instans i Easypanel:

1. **Skapa ny App service** i Easypanel:
   - Name: `hermes-bridge`
   - Build Context: `./deploy/easypanel`
   - Dockerfile: `Dockerfile.bridge`
   - Port: `8080`

2. **Environment Variables**:
   ```
   HERMES_URL=http://hermes:3000  # Intern URL till din Hermes service
   HERMES_TOKEN=hermes-customer-secret-token-2024-magnusfroste
   ```

3. **Domain**: Mappa en domän till port 8080
   - T.ex: `bridge.hermes.froste.eu` → `hermes-bridge:8080`

## Användning

När bridgen är igång kan jag skicka:

```bash
curl -X POST "https://bridge.hermes.froste.eu/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hej! Vad kan du göra?"}'
```

Svar:
```json
{
  "session_id": "xyz",
  "response": "Hej! Jag kan...",
  "status": "success"
}
```

## Säkerhet

⚠️ **VIKTIGT**: Begränsa access till bridge:
- Sätt `allow_origins` till specifika IPs i `hermes_bridge.py`
- Eller lägg till API-key check
- Använd inte `allow_origins=["*"]` i produktion!

## Test lokalt

```bash
cd deploy/easypanel
docker build -f Dockerfile.bridge -t hermes-bridge .
docker run -p 8080:8080 \
  -e HERMES_URL=https://hermes.froste.eu \
  -e HERMES_TOKEN=hermes-customer-secret-token-2024-magnusfroste \
  hermes-bridge
```

Testa:
```bash
curl http://localhost:8080/
curl -X POST http://localhost:8080/chat \
  -d '{"message": "Hej!"}'
```
