#!/bin/bash
# Hermes Container Monitor
# Enkel bash-version som använder docker ps + watch

HERMES_AGENTS=("hermes-customer" "hermes-operator" "hermes-supplier" "hermes-redis")

show_dashboard() {
    clear
    echo "╔══════════════════════════════════════════════════════════════════════════╗"
    echo "║              🏛️  HERMES MULTI-AGENT DASHBOARD                            ║"
    echo "║              $(date '+%Y-%m-%d %H:%M:%S')                                      ║"
    echo "╠══════════════════════════════════════════════════════════════════════════╣"
    echo "║ CONTAINER          │ STATUS     │ PORTS           │ HEALTH              ║"
    echo "╠════════════════════╪════════════╪═════════════════╪═════════════════════╣"
    
    for agent in "${HERMES_AGENTS[@]}"; do
        # Hämta container info
        info=$(docker ps -f "name=$agent" --format "{{.Names}}|{{.State}}|{{.Ports}}|{{.Status}}" 2>/dev/null)
        
        if [ -n "$info" ]; then
            IFS='|' read -r name state ports status <<< "$info"
            emoji="🟢"
            health="OK"
        else
            name="$agent"
            state="stopped"
            ports="-"
            status="Not running"
            emoji="🔴"
            health="DOWN"
        fi
        
        printf "║ %s %-15s │ %-10s │ %-15s │ %-19s ║\n" "$emoji" "$name" "$state" "${ports:0:15}" "$health"
    done
    
    echo "╠══════════════════════════════════════════════════════════════════════════╣"
    echo "║  KOMMANDON:  'lazydocker' för full TUI  │  'docker-compose logs -f'      ║"
    echo "╚══════════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Senaste log-rad:"
    docker-compose -f /opt/hermesstack/deploy/vps/docker-compose.vps.yml logs --tail 1 2>/dev/null | tail -1
}

# Huvudloop
while true; do
    show_dashboard
    sleep 3
done
