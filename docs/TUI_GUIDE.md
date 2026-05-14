# TUI Monitoring för Hermes VPS

Arcane-inspirerade dashboards för att övervaka dina Hermes-agenter.

## Alternativ 1: Lazydocker (REKOMMENDERAT) 🏆

Det bästa TUI-verktyget för Docker!

### Installation (30 sekunder):

```bash
# Via Homebrew (Mac/Linux)
brew install lazydocker

# Via script (Linux)
curl https://raw.githubusercontent.com/jesseduffield/lazydocker/master/scripts/install_update_linux.sh | bash

# Eller manuell
cd /tmp
curl -Lo lazydocker.tar.gz "https://github.com/jesseduffield/lazydocker/releases/latest/download/lazydocker_$(uname -s)_$(uname -m).tar.gz"
tar xf lazydocker.tar.gz lazydocker
sudo mv lazydocker /usr/local/bin/
```

### Användning:

```bash
# Gå till projektmappen
cd /opt/hermeshotel

# Starta lazydocker
lazydocker
```

### I Lazydocker:
- **Tab** - Växla mellan containers, loggar, stats
- **Enter** - Visa loggar för en container
- **r** - Restart container
- **d** - Remove container
- **s** - Stop container
- **b** - Bulk commands
- **q** - Quit

---

## Alternativ 2: Vår Custom TUI

### Python-version (fancy):

```bash
cd /opt/hermeshotel
python3 tui_monitor.py
```

Visar:
- 🟢/🔴 Status för varje agent
- CPU/RAM användning
- Senaste log-rad
- Auto-refresh var 3:e sekund

### Bash-version (enkel):

```bash
cd /opt/hermeshotel
chmod +x monitor.sh
./monitor.sh
```

---

## Alternativ 3: Standard Docker-kommandon

### Watch mode (auto-refresh):

```bash
# Klassisk docker ps med auto-refresh
cd /opt/hermeshotel
watch -n 2 'docker-compose ps'

# Eller mer detaljerat
watch -n 3 'docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
```

### Loggar i realtid:

```bash
# Alla agenter
docker-compose logs -f

# Bara operator
docker-compose logs -f hermes-operator

# Bara customer
docker-compose logs -f hermes-customer
```

### Stats (CPU/RAM):

```bash
# Real-time stats
docker stats

# Eller för specifika containers
docker stats hermes-customer hermes-operator hermes-supplier
```

---

## Alternativ 4: ctop (lightweight)

```bash
# Installera
curl -Lo ctop https://github.com/bcicen/ctop/releases/download/v0.7.7/ctop-0.7.7-linux-amd64
sudo mv ctop /usr/local/bin/
sudo chmod +x /usr/local/bin/ctop

# Kör
ctop
```

---

## Rekommendation

| Verktyg | Komplexitet | Features | Rekommendation |
|---------|-------------|----------|----------------|
| **Lazydocker** | Medium | ⭐⭐⭐⭐⭐ | **Bäst!** |
| **tui_monitor.py** | Låg | ⭐⭐⭐ | Custom för Hermes |
| **watch + docker ps** | Minimal | ⭐⭐ | Alltid tillgänglig |
| **ctop** | Låg | ⭐⭐⭐ | Lightweight |

---

## Arcane Style Bonus 🎨

För äkta Arcane-vibe, använd med:

```bash
# Installera cool-retro-term eller liknande terminal
# Sätt font till "Fira Code" eller "Hack"
# Använd färgschema "Gruvbox Dark" eller "Monokai Pro"

# I lazydocker/tui_monitor:
# - Grönt = Agent OK
# - Rött = Agent Down  
# - Gult = Agent startar
```

---

## Quick Commands Reference

```bash
# Övervaka allt
cd /opt/hermeshotel && lazydocker

# Snabb status
docker-compose ps

# Senaste loggar
docker-compose logs --tail 20

# Restart allt
docker-compose restart

# Full restart (bygg om)
docker-compose up -d --build
```
