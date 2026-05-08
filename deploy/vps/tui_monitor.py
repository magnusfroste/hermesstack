#!/usr/bin/env python3
"""
Hermes TUI Monitor - Container Dashboard
En arcane-inspirerad TUI för att övervaka Hermes-agenter
"""

import asyncio
import json
import subprocess
import time
from datetime import datetime
from typing import List, Dict, Any

# Enkel TUI utan external deps (bara standard library)
# För mer avancerad: använd rich eller textual

class HermesTUI:
    """Terminal UI för Hermes monitoring"""
    
    def __init__(self):
        self.agents = ["hermes-customer", "hermes-operator", "hermes-supplier", "hermes-redis"]
        self.running = True
        
    def clear_screen(self):
        """Rensa skärmen"""
        print("\033[2J\033[H", end="")
        
    def get_container_status(self, name: str) -> Dict[str, Any]:
        """Hämta container status via docker ps"""
        try:
            result = subprocess.run(
                ["docker", "ps", "-f", f"name={name}", "--format", "{{json .}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.stdout.strip():
                # Parse JSON output
                lines = result.stdout.strip().split('\n')
                if lines:
                    return json.loads(lines[0])
            
            # Container not running
            return {
                "Names": name,
                "State": "stopped",
                "Status": "Not running",
                "Ports": "",
                "CreatedAt": ""
            }
            
        except Exception as e:
            return {
                "Names": name,
                "State": "error",
                "Status": str(e),
                "Ports": "",
                "CreatedAt": ""
            }
    
    def get_logs(self, name: str, lines: int = 5) -> List[str]:
        """Hämta senaste loggar"""
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), name],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip().split('\n')[-lines:]
        except:
            return ["No logs available"]
    
    def get_stats(self, name: str) -> str:
        """Hämta CPU/Memory stats"""
        try:
            result = subprocess.run(
                ["docker", "stats", name, "--no-stream", "--format", "CPU: {{.CPUPerc}} | RAM: {{.MemUsage}}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except:
            return "Stats unavailable"
    
    def draw_header(self):
        """Rita header"""
        print("╔" + "═" * 78 + "╗")
        print("║" + " 🏛️  HERMES MULTI-AGENT DASHBOARD ".center(78) + "║")
        print("║" + f" ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(78) + "║")
        print("╠" + "═" * 78 + "╣")
    
    def draw_agent_card(self, agent: str, status: Dict, stats: str, logs: List[str]):
        """Rita agent info card"""
        state = status.get("State", "unknown")
        status_text = status.get("Status", "Unknown")
        ports = status.get("Ports", "")
        
        # Status färg (via emoji)
        status_emoji = "🟢" if state == "running" else "🔴" if state == "stopped" else "🟡"
        
        print(f"║ {status_emoji} {agent.upper():15} │ {status_text[:40]:40} │ {stats[:20]:20} ║")
        
        # Visa portar om det finns
        if ports:
            print(f"║   └─ Ports: {ports[:60]:60} ║")
        
        # Visa senaste log-rad
        if logs and logs[0]:
            last_log = logs[-1][:70]
            print(f"║   └─ 📝 {last_log:70} ║")
        
        print("╟" + "─" * 78 + "╢")
    
    def draw_footer(self):
        """Rita footer med kommandon"""
        print("╠" + "═" * 78 + "╣")
        print("║  KOMMANDON:  [R] Uppdatera  │  [L] Visa loggar  │  [Q] Avsluta        ║")
        print("╚" + "═" * 78 + "╝")
        print("\n Tryck Ctrl+C för att avsluta\n")
    
    def refresh(self):
        """Uppdatera display"""
        self.clear_screen()
        self.draw_header()
        
        for agent in self.agents:
            status = self.get_container_status(agent)
            stats = self.get_stats(agent)
            logs = self.get_logs(agent)
            self.draw_agent_card(agent, status, stats, logs)
        
        self.draw_footer()
    
    def show_logs(self, agent: str, lines: int = 50):
        """Visa fulla loggar för agent"""
        self.clear_screen()
        print(f"=== LOGGAR: {agent} ===\n")
        
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(lines), "-f", agent],
                timeout=10  # Visa i 10 sekunder
            )
        except subprocess.TimeoutExpired:
            pass
        
        input("\nTryck Enter för att fortsätta...")
    
    def run(self):
        """Huvudloop"""
        try:
            while self.running:
                self.refresh()
                
                # Vänta på input (timeout för auto-refresh)
                try:
                    import select
                    import sys
                    
                    # Vänta 2 sekunder på input, annars refresh
                    if select.select([sys.stdin], [], [], 2)[0]:
                        cmd = sys.stdin.read(1).lower()
                        
                        if cmd == 'q':
                            self.running = False
                        elif cmd == 'r':
                            continue  # Refresh sker automatiskt
                        elif cmd == 'l':
                            print("\nVälj agent för loggar (c=customer, o=operator, s=supplier, r=redis): ")
                            agent_cmd = sys.stdin.read(1).lower()
                            agent_map = {
                                'c': 'hermes-customer',
                                'o': 'hermes-operator', 
                                's': 'hermes-supplier',
                                'r': 'hermes-redis'
                            }
                            if agent_cmd in agent_map:
                                self.show_logs(agent_map[agent_cmd])
                                
                except (select.error, KeyboardInterrupt):
                    self.running = False
                    
        except KeyboardInterrupt:
            print("\n\nAvslutar...")
    
    def simple_run(self):
        """Enklare version utan select (fallback)"""
        try:
            while self.running:
                self.refresh()
                time.sleep(3)  # Auto-refresh var 3:e sekund
        except KeyboardInterrupt:
            print("\n\nAvslutar...")

def main():
    """Entry point"""
    print("🏛️  Startar Hermes TUI Dashboard...")
    print("(Tryck Ctrl+C för att avsluta)\n")
    time.sleep(1)
    
    tui = HermesTUI()
    
    # Försök med interaktiv version, fallback till auto-refresh
    try:
        import select
        tui.run()
    except ImportError:
        print("ℹ️  Kör i auto-refresh läge (inget interaktivt stöd)")
        tui.simple_run()

if __name__ == "__main__":
    main()
