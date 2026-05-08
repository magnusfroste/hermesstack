#!/usr/bin/env python3
"""
Hermes Multi-Agent TUI — Full Control Dashboard
Manages customer, operator, supplier agents without entering containers.

Usage: python3 hermes-tui.py [options]
  --env-file PATH    Path to .env file (default: /opt/hermesstack/.env)
  --compose PATH     Path to docker-compose file
  --no-color         Disable ANSI colors
"""

import curses
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

# ── Configuration ──
COMPOSE_FILE = os.environ.get("HERMES_COMPOSE", "/opt/hermesstack/deploy/vps/docker-compose.vps.yml")
ENV_FILE = os.environ.get("HERMES_ENV", "/opt/hermesstack/.env")

AGENTS = {
    "customer":  {"port": 3001, "color": 2,  "emoji": "🛒"},
    "operator":  {"port": 3002, "color": 3,  "emoji": "⚙️"},
    "supplier":  {"port": 3003, "color": 4,  "emoji": "📦"},
}

# ── Color setup ──
COLORS_INIT = False
def init_colors():
    global COLORS_INIT
    if not COLORS_INIT:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)   # OK
        curses.init_pair(2, curses.COLOR_CYAN, -1)     # Customer
        curses.init_pair(3, curses.COLOR_YELLOW, -1)   # Operator
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)  # Supplier
        curses.init_pair(5, curses.COLOR_RED, -1)      # Error
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)  # Header
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Menu
        curses.init_pair(8, curses.COLOR_GREEN, curses.COLOR_BLACK)  # Success bg
        COLORS_INIT = True

# ── Utility ──
def run(cmd, timeout=30):
    """Run shell command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"

def docker_compose(subcmd):
    """Run docker compose command with correct binary."""
    rc, out, err = run(f"docker compose -f {COMPOSE_FILE} {subcmd}")
    if rc != 0:
        rc, out, err = run(f"docker-compose -f {COMPOSE_FILE} {subcmd}")
    return rc, out, err

def get_env_value(key):
    """Read a value from .env file."""
    try:
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return None

def set_env_value(key, value):
    """Update or add a value in .env file."""
    lines = []
    found = False
    try:
        with open(ENV_FILE) as f:
            for line in f:
                if line.strip().startswith(key + "="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line)
    except FileNotFoundError:
        pass
    if not found:
        lines.append(f"{key}={value}\n")
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)

def check_agent_health(name, port):
    """Check agent health via HTTP API."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/status", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return "healthy", data.get("model", "unknown")
    except Exception:
        return "unreachable", ""

# ── Screen rendering helpers ──
def draw_border(stdscr, y1, x1, y2, x2, color=0):
    """Draw a box border."""
    h, w = stdscr.getmaxyx()
    if y2 >= h or x2 >= w:
        return
    for x in range(x1, min(x2, w)):
        try:
            stdscr.addch(y1, x, curses.ACS_HLINE, color)
            stdscr.addch(y2, x, curses.ACS_HLINE, color)
        except curses.error:
            pass
    for y in range(y1, min(y2 + 1, h)):
        try:
            stdscr.addch(y, x1, curses.ACS_VLINE, color)
            stdscr.addch(y, x2, curses.ACS_VLINE, color)
        except curses.error:
            pass
    try:
        stdscr.addch(y1, x1, curses.ACS_ULCORNER, color)
        stdscr.addch(y1, x2, curses.ACS_URCORNER, color)
        stdscr.addch(y2, x1, curses.ACS_LLCORNER, color)
        stdscr.addch(y2, x2, curses.ACS_LRCORNER, color)
    except curses.error:
        pass

def draw_text(stdscr, y, x, text, color=0, bold=False):
    """Draw text safely."""
    try:
        attr = color
        if bold:
            attr |= curses.A_BOLD
        stdscr.addnstr(y, x, text, 200, attr)
    except curses.error:
        pass

# ── Main TUI ──
class HermesTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.selected = 0
        self.menu_items = [
            ("1", "Status Dashboard", self.show_dashboard),
            ("2", "Update All Agents", self.update_agents),
            ("3", "Change Model", self.change_model),
            ("4", "View Logs", self.view_logs),
            ("5", "Restart Agent", self.restart_agent),
            ("6", "Test API / Flowwink", self.test_api),
            ("7", "Environment Config", self.edit_env),
            ("q", "Quit", None),
        ]

    def run(self):
        init_colors()
        curses.curs_set(0)
        self.stdscr.nodelay(False)
        self.stdscr.timeout(3000)  # refresh every 3s

        while True:
            self.stdscr.erase()
            self.draw_header()
            self.draw_menu()
            self.draw_footer()
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q')):
                break
            elif key == curses.KEY_UP:
                self.selected = max(0, self.selected - 1)
            elif key == curses.KEY_DOWN:
                self.selected = min(len(self.menu_items) - 1, self.selected + 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                self.execute_selected()
            elif key == ord('r') or key == ord('R'):
                self.show_dashboard()
            elif key == ord('1'):
                self.show_dashboard()
            elif key == ord('2'):
                self.update_agents()
            elif key == ord('3'):
                self.change_model()
            elif key == ord('4'):
                self.view_logs()
            elif key == ord('5'):
                self.restart_agent()
            elif key == ord('6'):
                self.test_api()
            elif key == ord('7'):
                self.edit_env()

    def draw_header(self):
        h, w = self.stdscr.getmaxyx()
        title = " HERMES MULTI-AGENT TUI "
        draw_border(self.stdscr, 0, 0, 2, w - 1, curses.color_pair(6) | curses.A_BOLD)
        draw_text(self.stdscr, 1, (w - len(title)) // 2, title,
                  curses.color_pair(6) | curses.A_BOLD)

    def draw_menu(self):
        y = 4
        for key, label, _ in self.menu_items:
            if label == "Quit":
                y += 1
                continue
            prefix = "▶ " if self.selected == self.menu_items.index((key, label, _)) else "  "
            draw_text(self.stdscr, y, 2, f"{prefix}{key}. {label}",
                      curses.color_pair(2) if self.selected == self.menu_items.index((key, label, _)) else 0)
            y += 1

    def draw_footer(self):
        h, w = self.stdscr.getmaxyx()
        footer = " ↑↓ Navigate | Enter Select | R Refresh | Q Quit "
        draw_border(self.stdscr, h - 3, 0, h - 1, w - 1, curses.color_pair(6))
        draw_text(self.stdscr, h - 2, (w - len(footer)) // 2, footer,
                  curses.color_pair(6))

    def execute_selected(self):
        _, _, func = self.menu_items[self.selected]
        if func:
            self.stdscr.nodelay(False)
            self.stdscr.timeout(-1)
            func()
            self.stdscr.nodelay(False)
            self.stdscr.timeout(3000)

    def show_dashboard(self):
        """Show live status of all agents."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " AGENT STATUS ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 4, w - 1, curses.color_pair(6))

        y = 6
        for name, info in AGENTS.items():
            status, model = check_agent_health(name, info["port"])
            color = curses.color_pair(info["color"])

            # Get container status
            _, ps_out, _ = docker_compose(f"ps --format '{{{{.Name}}}}\t{{{{.Status}}}}' 2>/dev/null")
            container_status = "not found"
            for line in ps_out.splitlines():
                if name in line.lower():
                    container_status = line.split("\t")[-1] if "\t" in line else line.split(None, 1)[-1]
                    break

            draw_text(self.stdscr, y, 2, f" {info['emoji']} {name.upper()}", color | curses.A_BOLD)
            draw_text(self.stdscr, y + 1, 4, f"API:      {status}")
            draw_text(self.stdscr, y + 1, 25, f"Model:    {model or '—'}")
            draw_text(self.stdscr, y + 2, 4, f"Port:     {info['port']}")
            draw_text(self.stdscr, y + 2, 25, f"Status:   {container_status}")
            y += 4

        # Show current model from .env
        model = get_env_value("HERMES_MODEL")
        if model:
            draw_text(self.stdscr, y + 1, 2, f" Global model: {model}", curses.A_BOLD)

        draw_text(self.stdscr, h - 4, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.nodelay(False)
        self.stdscr.getch()

    def update_agents(self):
        """Pull latest images and rebuild."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " UPDATING ALL AGENTS ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        draw_text(self.stdscr, 5, 2, "Pulling latest images...")
        self.stdscr.refresh()
        rc, out, err = docker_compose("pull")
        draw_text(self.stdscr, 6, 2, out[-200:] if out else err[-200:] if err else "Done")

        draw_text(self.stdscr, 8, 2, "Rebuilding and restarting...")
        self.stdscr.refresh()
        rc, out, err = docker_compose("up -d --build")
        draw_text(self.stdscr, 9, 2, out[-200:] if out else err[-200:] if err else "Done")

        draw_text(self.stdscr, 12, 2, f"Return code: {rc}", curses.A_BOLD)
        draw_text(self.stdscr, 14, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def change_model(self):
        """Change the HERMES_MODEL for all agents."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " CHANGE MODEL ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        current = get_env_value("HERMES_MODEL") or "not set"
        draw_text(self.stdscr, 5, 2, f"Current model: {current}")
        draw_text(self.stdscr, 6, 2, "")
        draw_text(self.stdscr, 7, 2, "Available models:")
        models = [
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "openai/o1-mini",
            "openai/o1",
            "anthropic/claude-sonnet-4-20250514",
            "anthropic/claude-sonnet-4-5-20250514",
            "anthropic/claude-opus-4-20250514",
            "anthropic/claude-3-5-haiku-20241022",
        ]
        for i, m in enumerate(models):
            marker = "→" if m == current else " "
            draw_text(self.stdscr, 9 + i, 4, f"{marker} {i + 1}. {m}")

        draw_text(self.stdscr, 18, 2, "Select number (or 'c' for custom): ")
        self.stdscr.refresh()

        curses.echo()
        curses.curs_set(1)
        try:
            ch = self.stdscr.getch()
            if 49 <= ch <= 56:  # 1-8
                new_model = models[ch - 49]
            elif ch in (ord('c'), ord('C')):
                draw_text(self.stdscr, 19, 2, "Enter model (provider/name): ")
                self.stdscr.refresh()
                new_model = self.stdscr.getstr(19, 35, 60).decode().strip()
            else:
                return
        finally:
            curses.noecho()
            curses.curs_set(0)

        if not new_model:
            return

        set_env_value("HERMES_MODEL", new_model)
        draw_text(self.stdscr, 20, 2, f"Model changed to: {new_model}")
        draw_text(self.stdscr, 21, 2, "Restarting all agents...")
        self.stdscr.refresh()
        docker_compose("restart")
        draw_text(self.stdscr, 22, 2, "Done. Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def view_logs(self):
        """View logs for a specific agent."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " VIEW LOGS ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        draw_text(self.stdscr, 5, 2, "Select agent:")
        draw_text(self.stdscr, 6, 4, "1. customer")
        draw_text(self.stdscr, 7, 4, "2. operator")
        draw_text(self.stdscr, 8, 4, "3. supplier")
        draw_text(self.stdscr, 9, 4, "4. all")
        self.stdscr.refresh()

        curses.echo()
        try:
            ch = self.stdscr.getch()
        finally:
            curses.noecho()

        agent_map = {ord('1'): 'hermes-customer', ord('2'): 'hermes-operator',
                     ord('3'): 'hermes-supplier', ord('4'): ''}
        agent = agent_map.get(ch)
        if not agent and ch not in agent_map:
            return

        self.stdscr.erase()
        draw_text(self.stdscr, 0, 0, f" LOGS: {agent or 'all'} (q=quit) ", curses.color_pair(6) | curses.A_BOLD)
        self.stdscr.refresh()

        cmd = f"docker compose -f {COMPOSE_FILE} logs --tail=100 {agent}".replace("docker compose", "docker-compose")
        rc, out, err = run(cmd, timeout=10)
        output = out or err or "No logs available."

        # Show logs with scrolling
        lines = output.splitlines()
        offset = 0
        max_y, max_x = self.stdscr.getmaxyx()
        visible = max_y - 2

        while True:
            self.stdscr.erase()
            for i in range(visible):
                idx = offset + i
                if idx < len(lines):
                    line = lines[idx][:max_x - 2]
                    color = 0
                    if "error" in line.lower():
                        color = curses.color_pair(5)
                    elif "warn" in line.lower():
                        color = curses.color_pair(3)
                    try:
                        self.stdscr.addnstr(i + 1, 1, line, max_x - 2, color)
                    except curses.error:
                        pass
            draw_text(self.stdscr, max_y - 1, 1, f"Lines {offset + 1}-{min(offset + visible, len(lines))}/{len(lines)} | ↑↓ scroll | q quit",
                      curses.color_pair(6))
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q')):
                break
            elif key == curses.KEY_DOWN and offset < len(lines) - visible:
                offset += 1
            elif key == curses.KEY_UP and offset > 0:
                offset -= 1
            elif key == curses.KEY_PPAGE:
                offset = max(0, offset - visible)
            elif key == curses.KEY_NPAGE:
                offset = min(len(lines) - visible, offset + visible)

    def restart_agent(self):
        """Restart a specific agent."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " RESTART AGENT ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        draw_text(self.stdscr, 5, 2, "Select agent:")
        for i, name in enumerate(AGENTS.keys(), 1):
            draw_text(self.stdscr, 5 + i, 4, f"{i}. {name}")
        draw_text(self.stdscr, 9, 4, "4. all")
        self.stdscr.refresh()

        curses.echo()
        try:
            ch = self.stdscr.getch()
        finally:
            curses.noecho()

        agent_map = {ord('1'): 'hermes-customer', ord('2'): 'hermes-operator',
                     ord('3'): 'hermes-supplier', ord('4'): ''}
        agent = agent_map.get(ch, '')

        self.stdscr.erase()
        draw_text(self.stdscr, 2, 2, f"Restarting {agent or 'all agents'}...")
        self.stdscr.refresh()

        docker_compose(f"restart {agent}".strip())

        time.sleep(5)
        # Check health
        for name, info in AGENTS.items():
            if agent and agent != name and agent != '':
                continue
            status, model = check_agent_health(name, info['port'])
            color = curses.color_pair(1) if status == "healthy" else curses.color_pair(5)
            draw_text(self.stdscr, 5, 2, f"  {name}: {status}", color)

        draw_text(self.stdscr, 10, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def test_api(self):
        """Test API connectivity and Flowwink MCP."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " API / FLOWWINK TEST ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        y = 5

        # Test each agent's API
        for name, info in AGENTS.items():
            token = get_env_value(f"HERMES_{name.upper()}_TOKEN")
            status, model = check_agent_health(name, info["port"])

            color = curses.color_pair(1) if status == "healthy" else curses.color_pair(5)
            draw_text(self.stdscr, y, 2, f"{info['emoji']} {name}: ", color | curses.A_BOLD)
            draw_text(self.stdscr, y, 20, f"Status: {status}")
            y += 1

            if token:
                draw_text(self.stdscr, y, 4, f"Token: {token[:20]}...")
                y += 1

            # Try a real API call
            if status == "healthy":
                try:
                    url = f"http://127.0.0.1:{info['port']}/api/status?token={token}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read())
                        draw_text(self.stdscr, y, 4, f"API OK — Model: {data.get('model', '?')}")
                except Exception as e:
                    draw_text(self.stdscr, y, 4, f"API Error: {str(e)[:50]}")
                y += 2

        # Test Flowwink MCP
        y += 1
        draw_text(self.stdscr, y, 2, " FLOWWINK MCP ", curses.A_BOLD)
        y += 1
        fw_key = get_env_value("FLOWWINK_API_KEY")
        if fw_key:
            draw_text(self.stdscr, y, 4, f"Key: {fw_key[:20]}...")
            y += 1
            # Try operator's Flowwink connection
            op_token = get_env_value("HERMES_OPERATOR_TOKEN")
            try:
                url = f"http://127.0.0.1:3002/api/status?token={op_token}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                    draw_text(self.stdscr, y, 4, f"Operator API: OK")
            except Exception as e:
                draw_text(self.stdscr, y, 4, f"Operator API: {str(e)[:50]}")
            y += 1
            draw_text(self.stdscr, y, 4, "Note: Flowwink MCP is configured in operator/config.yaml")
            draw_text(self.stdscr, y + 1, 4, "Test MCP via operator dashboard: https://operator.yourdomain.com")
        else:
            draw_text(self.stdscr, y, 4, "No FLOWWINK_API_KEY configured")

        draw_text(self.stdscr, h - 4, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def edit_env(self):
        """View and edit environment variables."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " ENVIRONMENT CONFIG ", curses.color_pair(6) | curses.A_BOLD)
        draw_border(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        y = 5
        draw_text(self.stdscr, y, 2, f"File: {ENV_FILE}")
        y += 2

        try:
            with open(ENV_FILE) as f:
                for line in f:
                    line = line.rstrip()
                    if line and not line.startswith("#"):
                        key = line.split("=", 1)[0]
                        val = line.split("=", 1)[1] if "=" in line else ""
                        # Mask sensitive values
                        if "KEY" in key or "TOKEN" in key or "SECRET" in key:
                            display_val = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
                        else:
                            display_val = val
                        draw_text(self.stdscr, y, 4, f"{key}={display_val}")
                        y += 1
        except FileNotFoundError:
            draw_text(self.stdscr, y, 2, f"File not found: {ENV_FILE}")

        draw_text(self.stdscr, y + 2, 2, "To edit: nano /opt/hermesstack/.env")
        draw_text(self.stdscr, y + 3, 2, "Then restart: docker compose -f deploy/vps/docker-compose.vps.yml restart")
        draw_text(self.stdscr, h - 4, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()


def main(stdscr):
    tui = HermesTUI(stdscr)
    tui.run()


if __name__ == "__main__":
    # Parse CLI args
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--env-file" and i < len(sys.argv):
            ENV_FILE = sys.argv[i + 1]
        elif arg == "--compose" and i < len(sys.argv):
            COMPOSE_FILE = sys.argv[i + 1]

    curses.wrapper(main)
