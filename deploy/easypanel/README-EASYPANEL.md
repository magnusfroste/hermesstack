# Hermes Agent - Easypanel Deployment

Deploy Hermes Agent on Easypanel at `easy.froste.eu`

## Quick Deploy

1. **In Easypanel UI** (at https://easy.froste.eu):
   - Click "Create Service"
   - Select "Docker Compose"
   - Point to this GitHub repo

2. **Configure Environment Variables** in Easypanel:
   ```
   OPENAI_API_KEY=sk-...
   ANTHROPIC_API_KEY=sk-ant-...
   HERMES_MODEL=openai/gpt-4o-mini
   EASYPANEL_DOMAIN=hermes.froste.eu
   ```

3. **Deploy** - Easypanel bygger och startar automatiskt

## URLs efter deploy

| Tjänst | URL |
|--------|-----|
| Dashboard | `https://hermes.froste.eu` |

## Data Persistence

- Hermes config, minne och loggar sparas i Docker volume `hermes-data`

## Tekniska detaljer

### CORS & Traefik
Dockerfile patchar `hermes_cli/web_server.py` för att tillåta externa origins (nödvändigt för Traefik reverse proxy):
```python
# Bytt från:
allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
# Till:
allow_origins=["*"]
```

### Port & Binding
- Container exponerar port `3000`
- Startas med `--host 0.0.0.0 --insecure` för att acceptera extern trafik

### WebSocket Support
Traefik labels inkluderar WebSocket-support för realtidsfunktioner.
