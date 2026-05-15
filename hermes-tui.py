#!/usr/bin/env python3
"""
Hermes Multi-Agent TUI — Arcane-Style Full Control Dashboard
Manages customer, operator, supplier agents without entering containers.

Usage: python3 hermes-tui.py [options]
  --env-file PATH    Path to .env file (default: /opt/hermeshotel/.env)
  --compose PATH     Path to docker-compose file
  --no-color         Disable ANSI colors
"""

import curses
import json
import os
import subprocess
import shlex
import sys
import time
import re
import urllib.request
import urllib.error
import tempfile
from pathlib import Path
from datetime import datetime

VERSION = "0.16.0"

# ── Configuration ──
COMPOSE_FILE = os.environ.get("HERMES_COMPOSE", "/opt/hermeshotel/docker-compose.yml")
ENV_FILE = os.environ.get("HERMES_ENV", "/opt/hermeshotel/.env")
INSTANCES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instances.json")
ROOT_DIR = Path("/opt/hermeshotel")

COLORS = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2, 3, 4, 5]

def load_instances():
    """Load instances from instances.json. Returns empty list if none exist."""
    try:
        with open(INSTANCES_FILE) as f:
            data = json.load(f)
            return data.get("instances", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_instances(instances):
    """Save instances to instances.json."""
    with open(INSTANCES_FILE, "w") as f:
        json.dump({"instances": instances}, f, indent=2)

def get_agents():
    """Build agents dict from instances for TUI display."""
    instances = load_instances()
    agents = {}
    for i, inst in enumerate(instances):
        if not inst.get("active", True):
            continue
        agents[inst["name"]] = {
            "port": inst["port"],
            "domain": inst["domain"],
            "container": inst.get("container", f"hermes-{inst['name']}"),
            "emoji": inst.get("emoji", "🤖"),
            "color": COLORS[i % len(COLORS)],
            "label": inst.get("label", inst["name"]),
        }
    return agents


def get_config_files():
    """Return the config files that define the containerized Hermes stack."""
    return [
        {
            "key": "env",
            "label": "Global Environment",
            "path": Path(ENV_FILE),
            "kind": "env",
            "restart": "all",
            "why": "Secrets, HERMES_MODEL, Flowwink key, dashboard tokens.",
        },
        {
            "key": "compose",
            "label": "Docker Compose",
            "path": Path(COMPOSE_FILE),
            "kind": "yaml",
            "restart": "recreate",
            "why": "Official image, dashboard env vars, ports, writable config mounts.",
        },
        {
            "key": "caddy",
            "label": "Caddy Reverse Proxy",
            "path": ROOT_DIR / "config/Caddyfile",
            "kind": "caddy",
            "restart": "caddy",
            "why": "HTTPS, domains, dashboard auth headers, OPTIONS preflight.",
        },
        {
            "key": "operator",
            "label": "Operator Profile",
            "path": ROOT_DIR / "profiles/operator/config.yaml",
            "kind": "yaml",
            "restart": "operator",
            "why": "Private LLM, Flowwink MCP, operator tools and approvals.",
        },
        {
            "key": "customer",
            "label": "Customer Profile",
            "path": ROOT_DIR / "profiles/customer/config.yaml",
            "kind": "yaml",
            "restart": "customer",
            "why": "Customer persona, model endpoint, tools.",
        },
        {
            "key": "supplier",
            "label": "Supplier Profile",
            "path": ROOT_DIR / "profiles/supplier/config.yaml",
            "kind": "yaml",
            "restart": "supplier",
            "why": "Supplier persona, model endpoint, tools.",
        },
        {
            "key": "instances",
            "label": "TUI Instances",
            "path": Path(INSTANCES_FILE),
            "kind": "json",
            "restart": "none",
            "why": "Which agents/domains the TUI displays and controls.",
        },
        {
            "key": "boot-doc",
            "label": "Boot Settings Doc",
            "path": ROOT_DIR / "docs/container-boot-settings.md",
            "kind": "markdown",
            "restart": "none",
            "why": "Human map of why each container setting exists.",
        },
        {
            "key": "ui-doc",
            "label": "Official UI Doc",
            "path": ROOT_DIR / "docs/official-ui-setup.md",
            "kind": "markdown",
            "restart": "none",
            "why": "Official UI, Caddy auth, writable mount troubleshooting.",
        },
    ]


def mask_secret_line(line):
    """Mask obvious secrets for display while preserving enough context."""
    upper = line.upper()
    secret_markers = ("KEY", "TOKEN", "SECRET", "AUTHORIZATION: BEARER", "PASSWORD")
    if not any(marker in upper for marker in secret_markers):
        return line
    if "=" in line:
        key, val = line.split("=", 1)
        val = val.strip()
        if len(val) > 12:
            return f"{key}={val[:8]}...{val[-4:]}"
        return f"{key}=***"
    bearer = re.search(r"(Authorization:\s*Bearer\s+)(\S+)", line, re.IGNORECASE)
    if bearer:
        val = bearer.group(2)
        masked = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
        return line[:bearer.start(2)] + masked + line[bearer.end(2):]
    return re.sub(r"([A-Za-z0-9_\-]{12})[A-Za-z0-9_\-]+([A-Za-z0-9_\-]{4})", r"\1...\2", line)


def validate_config_file(path, kind):
    """Run lightweight validation for edited config files."""
    if kind == "json":
        try:
            json.loads(path.read_text())
            return True, "JSON OK"
        except Exception as e:
            return False, f"JSON error: {e}"
    if kind == "yaml":
        rc, out, err = run(f"python3 - <<'PY'\nimport sys, yaml\nwith open({shlex.quote(str(path))!r}) as f:\n    yaml.safe_load(f)\nprint('YAML OK')\nPY", timeout=10)
        if rc == 0:
            return True, out.strip() or "YAML OK"
        return False, (err or out or "YAML validation failed").strip()[:300]
    if kind == "env":
        bad = []
        for i, line in enumerate(path.read_text().splitlines(), 1):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" not in stripped:
                bad.append(str(i))
        if bad:
            return False, "Invalid .env lines: " + ", ".join(bad[:8])
        return True, "ENV OK"
    if kind == "caddy":
        rc, out, err = run(f"caddy validate --config {shlex.quote(str(path))}", timeout=20)
        if rc == 0:
            return True, "Caddy config OK"
        return False, (err or out or "Caddy validation failed").strip()[:300]
    return True, "No validator for this file type"


def apply_config_restart(config):
    """Apply the operational step implied by a config file edit."""
    mode = config.get("restart")
    if mode == "none":
        return 0, "No restart needed", ""
    if mode == "caddy":
        path = config["path"]
        rc, out, err = run(f"cp {shlex.quote(str(path))} /etc/caddy/Caddyfile && caddy reload --config /etc/caddy/Caddyfile", timeout=30)
        return rc, out, err
    env_arg = f"--env-file {shlex.quote(ENV_FILE)}"
    if mode == "recreate":
        return docker_compose(f"{env_arg} up -d --force-recreate")
    if mode == "all":
        return docker_compose(f"{env_arg} up -d --force-recreate hermes-customer hermes-operator hermes-supplier")
    return docker_compose(f"{env_arg} up -d --force-recreate hermes-{mode}")


AGENTS = get_agents()

# ── Color setup ──
COLORS_INIT = False
def init_colors():
    global COLORS_INIT
    if not COLORS_INIT:
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_GREEN, -1)
        curses.init_pair(2, curses.COLOR_CYAN, -1)
        curses.init_pair(3, curses.COLOR_YELLOW, -1)
        curses.init_pair(4, curses.COLOR_MAGENTA, -1)
        curses.init_pair(5, curses.COLOR_RED, -1)
        curses.init_pair(6, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_WHITE)
        curses.init_pair(8, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(9, curses.COLOR_WHITE, -1)
        curses.init_pair(10, curses.COLOR_BLUE, -1)
        curses.init_pair(11, curses.COLOR_WHITE, curses.COLOR_BLACK)
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

def get_container_stats():
    """Get CPU/RAM stats for all running containers via docker stats --no-stream."""
    stats = {}
    rc, out, err = run("docker stats --no-stream --format '{{.Name}}\\t{{.CPUPerc}}\\t{{.MemUsage}}\\t{{.MemPerc}}'")
    if rc == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                name = parts[0].strip()
                stats[name] = {
                    "cpu": parts[1].strip(),
                    "mem_usage": parts[2].strip(),
                    "mem_perc": parts[3].strip(),
                }
    return stats

def get_container_uptime():
    """Get uptime for all running containers via docker ps --format."""
    uptimes = {}
    rc, out, err = run("docker ps --format '{{.Names}}\\t{{.Status}}'")
    if rc == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                name = parts[0].strip()
                status = parts[1].strip()
                # Extract uptime from status like "Up 3 hours" or "Up 2 minutes"
                match = re.search(r"Up\s+(.+)", status)
                if match:
                    uptimes[name] = match.group(1).strip()
                else:
                    uptimes[name] = status
    return uptimes

def get_short_model(model):
    """Shorten model name for display."""
    if not model or model == "unknown" or model == "—":
        return "—"
    # Remove provider prefix
    if "/" in model:
        return model.split("/", 1)[1]
    return model[:20]

def get_system_info():
    """Get basic system info (uptime, load, total memory)."""
    info = {"uptime": "", "load": "", "mem_total": "", "mem_used": ""}
    try:
        rc, out, err = run("uptime")
        if rc == 0:
            # Parse: 18:50:25 up 5 days, 3:22, 1 user, load average: 0.52, 0.58, 0.59
            parts = out.strip().split(",", 1)[0]
            info["uptime"] = parts.split("up", 1)[1].strip() if "up" in parts else ""
            # Load average
            load_match = re.search(r"load average:\s+([\d.]+)", out)
            if load_match:
                info["load"] = load_match.group(1)
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            mem = {}
            for line in f:
                key, val = line.split(":")
                mem[key.strip()] = int(val.strip().split()[0])  # in kB
            total = mem.get("MemTotal", 0)
            avail = mem.get("MemAvailable", total)
            used = total - avail
            info["mem_total"] = f"{total // 1024}MB"
            info["mem_used"] = f"{used // 1024}MB ({used * 100 // max(total, 1)}%)"
    except Exception:
        info["mem_total"] = "N/A"
        info["mem_used"] = "N/A"
    return info

# ── Arcane box-drawing helpers ──
BOX = {
    "tl": "\u2554", "tr": "\u2557", "bl": "\u255a", "br": "\u255d",
    "h":  "\u2550", "v":  "\u2551",
    "lt": "\u2560", "rt": "\u2563", "tt": "\u2566", "bt": "\u2569",
}

def draw_arcane_box(stdscr, y1, x1, y2, x2, color=0):
    """Draw a box with double-line Arcane-style borders."""
    h, w = stdscr.getmaxyx()
    if y2 >= h or x2 >= w or y1 > y2 or x1 > x2:
        return
    for x in range(x1 + 1, min(x2, w)):
        try:
            stdscr.addch(y1, x, BOX["h"], color)
            stdscr.addch(y2, x, BOX["h"], color)
        except curses.error:
            pass
    for y in range(y1 + 1, min(y2, h)):
        try:
            stdscr.addch(y, x1, BOX["v"], color)
            stdscr.addch(y, x2, BOX["v"], color)
        except curses.error:
            pass
    try:
        stdscr.addch(y1, x1, BOX["tl"], color)
        stdscr.addch(y1, x2, BOX["tr"], color)
        stdscr.addch(y2, x1, BOX["bl"], color)
        stdscr.addch(y2, x2, BOX["br"], color)
    except curses.error:
        pass

def draw_panel_title(stdscr, y, x, title, color=0):
    """Draw a panel title with background fill."""
    h, w = stdscr.getmaxyx()
    end_x = w - 2
    title_str = f" {title} "
    fill = " " * max(0, end_x - x - len(title_str))
    try:
        stdscr.addnstr(y, x, title_str + fill, end_x - x, color)
    except curses.error:
        pass

def draw_text(stdscr, y, x, text, color=0, bold=False, max_len=None):
    """Draw text safely."""
    if max_len is None:
        max_len = 400
    try:
        attr = color
        if bold:
            attr |= curses.A_BOLD
        stdscr.addnstr(y, x, text, max_len, attr)
    except curses.error:
        pass

def center_text(text, width):
    """Return (x_pos) to center text in given width."""
    return max(0, (width - len(text)) // 2)

# ── Main TUI ──
class HermesTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.selected = 0
        instances = load_instances()
        if not instances:
            # First-run: only show "Create First Hermes" and Quit
            self.menu_items = [
                ("f", "★  Create First Hermes — Setup your first agent  ★", self.create_first_hermes),
                ("w", "Web Panel — Configure status panel domain", self.web_panel_config),
                ("q", "Quit", None),
            ]
            self.first_run = True
        else:
            self.first_run = False
            self.menu_items = [
                ("1", "Status Dashboard", self.show_dashboard),
                ("2", "Update All Agents", self.update_agents),
                ("3", "Change Model", self.change_model),
                ("4", "View Logs", self.view_logs),
                ("5", "Restart Agent", self.restart_agent),
                ("6", "Test API / Flowwink", self.test_api),
                ("7", "Environment Config", self.edit_env),
                ("8", "Config Files", self.config_files),
                ("9", "Fleet / Images", self.fleet_panel),
                ("a", "Add Instance", self.add_instance),
                ("0", "Remove Instance", self.remove_instance),
                ("w", "Web Panel", self.web_panel_config),
                ("m", "MCP Orchestration", self.mcp_panel),
                ("c", "Chat with Agent", self.chat_agent),
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
            elif key == ord('8'):
                self.config_files()
            elif key == ord('9'):
                self.fleet_panel()
            elif key in (ord('a'), ord('A')):
                self.add_instance()
            elif key == ord('0'):
                self.remove_instance()
            elif key in (ord('m'), ord('M')):
                self.mcp_panel()
            elif key in (ord('w'), ord('W')):
                self.web_panel_config()
            elif key in (ord('f'), ord('F')):
                self.create_first_hermes()
            elif key in (ord('c'), ord('C')):
                self.chat_agent()

    def draw_header(self):
        h, w = self.stdscr.getmaxyx()
        if self.first_run:
            title = " HERMESHOTEL — FIRST RUN "
            subtitle = "  Welcome! Press Enter to create your first Hermes agent.  "
        else:
            title = " HERMES MULTI-AGENT TUI "
            subtitle = None
        draw_arcane_box(self.stdscr, 0, 0, 2, w - 1, curses.color_pair(6) | curses.A_BOLD)
        draw_text(self.stdscr, 1, (w - len(title)) // 2, title,
                  curses.color_pair(6) | curses.A_BOLD)
        if subtitle:
            draw_text(self.stdscr, 1, (w - len(subtitle)) // 2 + len(title) // 2, subtitle,
                      curses.color_pair(3) | curses.A_BOLD)

    def draw_menu(self):
        y = 4
        if self.first_run:
            h, w = self.stdscr.getmaxyx()
            msg = "No Hermes agents found. Let's set up your first one!"
            draw_text(self.stdscr, y, center_text(msg, w), msg, curses.color_pair(3) | curses.A_BOLD)
            y += 1
            msg2 = "You'll need: OPENAI_API_KEY set in .env, and a domain pointing to this server."
            draw_text(self.stdscr, y, center_text(msg2, w), msg2, curses.color_pair(8))
            y += 2
        for key, label, _ in self.menu_items:
            if label == "Quit":
                y += 1
                continue
            prefix = "▶ " if self.selected == self.menu_items.index((key, label, _)) else "  "
            style = curses.color_pair(6) | curses.A_BOLD if self.first_run and self.selected == self.menu_items.index((key, label, _)) else (curses.color_pair(2) if self.selected == self.menu_items.index((key, label, _)) else 0)
            draw_text(self.stdscr, y, 2, f"{prefix}{key}. {label}", style)
            y += 1

    def draw_footer(self):
        h, w = self.stdscr.getmaxyx()
        if self.first_run:
            footer = " Press Enter to setup | Q Quit "
        else:
            footer = " ↑↓ Navigate | Enter Select | R Refresh | Q Quit "
        draw_arcane_box(self.stdscr, h - 3, 0, h - 1, w - 1, curses.color_pair(6))
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
        """Arcane-style live dashboard with auto-refresh."""
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)
        tick = 0

        try:
            while True:
                tick += 1
                self.stdscr.erase()
                h, w = self.stdscr.getmaxyx()
                if h < 15 or w < 60:
                    draw_text(self.stdscr, h // 2, 2, "Terminal too small. Resize.", curses.color_pair(5))
                    self.stdscr.refresh()
                    key = self.stdscr.getch()
                    if key in (ord('q'), ord('Q'), 27):
                        break
                    continue

                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # ── Header bar ──
                title = f" \U0001f3db\ufe0f HERMES COMMAND CENTER  |  v{VERSION}  |  {now} "
                draw_arcane_box(self.stdscr, 0, 0, 2, w - 1, curses.color_pair(6) | curses.A_BOLD)
                draw_text(self.stdscr, 1, center_text(title, w), title,
                          curses.color_pair(6) | curses.A_BOLD)

                # ── System info bar ──
                if tick % 10 == 1:
                    self._sys_info = get_system_info()
                sys_info = getattr(self, '_sys_info', {})
                sys_line = f" System: {sys_info.get('uptime', 'N/A')} | Mem: {sys_info.get('mem_used', 'N/A')} / {sys_info.get('mem_total', 'N/A')}"
                if sys_info.get('load'):
                    sys_line += f" | Load: {sys_info['load']}"
                draw_arcane_box(self.stdscr, 3, 0, 4, w - 1, curses.color_pair(10))
                draw_text(self.stdscr, 3, 2, " SYSTEM ", curses.color_pair(10) | curses.A_BOLD)
                draw_text(self.stdscr, 4, 2, sys_line, curses.color_pair(10))

                # ── Collect agent data ──
                if tick % 6 == 1:
                    self._container_stats = get_container_stats()
                    self._container_uptime = get_container_uptime()
                    self._agent_health = {}
                    for name, info in AGENTS.items():
                        s, m = check_agent_health(name, info["port"])
                        self._agent_health[name] = (s, m)

                container_stats = getattr(self, '_container_stats', {})
                container_uptime = getattr(self, '_container_uptime', {})
                agent_health = getattr(self, '_agent_health', {})

                # ── Agent panel ──
                panel_top = 6
                panel_bottom = panel_top + 2 + len(AGENTS) + 2
                if panel_bottom > h - 5:
                    panel_bottom = h - 5
                draw_arcane_box(self.stdscr, panel_top, 0, panel_bottom, w - 1, curses.color_pair(11))
                draw_panel_title(self.stdscr, panel_top, 2, " AGENTS ", curses.color_pair(11) | curses.A_BOLD)

                # Table header
                hdr_y = panel_top + 1
                hdr = f"{'STATUS':<8}{'NAME':<12}{'DOMAIN':<28}{'MODEL':<18}{'PORT':<7}{'CPU':<7}{'MEM':<10}{'UPTIME'}"
                draw_text(self.stdscr, hdr_y, 2, hdr, curses.color_pair(9) | curses.A_BOLD, max_len=w - 3)

                # Separator
                draw_text(self.stdscr, hdr_y + 1, 2, "\u2550" * (w - 4), curses.color_pair(11))

                # Agent rows
                row_y = hdr_y + 2
                for name, info in AGENTS.items():
                    if row_y >= panel_bottom - 1:
                        break
                    color = curses.color_pair(info["color"])
                    status, model = agent_health.get(name, ("checking", ""))
                    is_healthy = status == "healthy"
                    dot = "\u25cf" if is_healthy else "\u25cb"
                    status_text = f"{dot} UP" if is_healthy else f"{dot} DOWN"

                    cname = f"hermes-{name}"
                    cstats = container_stats.get(cname, {})
                    cpu = cstats.get("cpu", "N/A")
                    mem = cstats.get("mem_perc", "N/A")
                    uptime = container_uptime.get(cname, "\u2014")

                    short_model = get_short_model(model)
                    domain = info["domain"]

                    row = f"{status_text:<8}{name.upper():<12}{domain:<28}{short_model:<18}{info['port']:<7}{cpu:<7}{mem:<10}{uptime}"
                    draw_text(self.stdscr, row_y, 2, row, color, max_len=w - 3)
                    row_y += 1

                # ── Domain panel ──
                dom_top = panel_bottom
                dom_bottom = dom_top + 5
                if dom_bottom > h - 4:
                    dom_bottom = h - 4
                draw_arcane_box(self.stdscr, dom_top, 0, dom_bottom, w - 1, curses.color_pair(10))
                draw_panel_title(self.stdscr, dom_top, 2, " DOMAINS ", curses.color_pair(10) | curses.A_BOLD)

                dom_y = dom_top + 1
                global_model = get_env_value("HERMES_MODEL") or "not set"
                draw_text(self.stdscr, dom_y, 4, f"Global model: {global_model}", curses.color_pair(10))
                draw_text(self.stdscr, dom_y + 1, 4, f"Config:   {ENV_FILE}", curses.color_pair(10))
                draw_text(self.stdscr, dom_y + 2, 4, f"Compose:  {COMPOSE_FILE}", curses.color_pair(10))

                # ── Bottom action bar ──
                action_y = h - 3
                draw_arcane_box(self.stdscr, action_y, 0, h - 1, w - 1, curses.color_pair(6))
                actions = " [1] Dash [2] Update [3] Model [4] Logs [5] Restart [6] Test [8] Files [9] Fleet [M] MCP [C] Chat [Q] Quit "
                draw_text(self.stdscr, action_y, center_text(actions, w), actions, curses.color_pair(6))

                self.stdscr.refresh()

                # Input handling (non-blocking)
                key = self.stdscr.getch()
                if key in (ord('q'), ord('Q'), 27):
                    break
                elif key in (ord('r'), ord('R')):
                    tick = 100
                elif key == ord('1'):
                    tick = 100
                elif key == ord('2'):
                    self._leave_dashboard()
                    self.update_agents()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('3'):
                    self._leave_dashboard()
                    self.change_model()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('4'):
                    self._leave_dashboard()
                    self.view_logs()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('5'):
                    self._leave_dashboard()
                    self.restart_agent()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('6'):
                    self._leave_dashboard()
                    self.test_api()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('7'):
                    self._leave_dashboard()
                    self.edit_env()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('8'):
                    self._leave_dashboard()
                    self.config_files()
                    self._enter_dashboard()
                    tick = 100
                elif key == ord('9'):
                    self._leave_dashboard()
                    self.fleet_panel()
                    self._enter_dashboard()
                    tick = 100
                elif key in (ord('m'), ord('M')):
                    self._leave_dashboard()
                    self.mcp_panel()
                    self._enter_dashboard()
                    tick = 100
                elif key in (ord('c'), ord('C')):
                    self._leave_dashboard()
                    self.chat_agent()
                    self._enter_dashboard()
                    tick = 100
        finally:
            # Restore curses state for run() menu loop
            self.stdscr.nodelay(False)
            self.stdscr.timeout(3000)

    def _leave_dashboard(self):
        """Temporarily leave dashboard loop."""
        self.stdscr.nodelay(False)
        self.stdscr.timeout(-1)

    def _enter_dashboard(self):
        """Re-enter dashboard loop mode."""
        self.stdscr.nodelay(True)
        self.stdscr.timeout(100)

    def update_agents(self):
        """Pull latest images and rebuild."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        if h < 15 or w < 40:
            draw_text(self.stdscr, 2, 2, "Terminal too small.", curses.color_pair(5))
            self.stdscr.refresh()
            self.stdscr.getch()
            return

        draw_text(self.stdscr, 1, 2, " UPDATING ALL AGENTS ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        draw_text(self.stdscr, 5, 2, "Pulling latest images...")
        self.stdscr.refresh()
        rc, out, err = docker_compose("pull")
        draw_text(self.stdscr, 6, 2, (out[-200:] if out else err[-200:] if err else "Done"), max_len=w - 3)

        draw_text(self.stdscr, 8, 2, "Rebuilding and restarting...")
        self.stdscr.refresh()
        rc, out, err = docker_compose("up -d --build")
        draw_text(self.stdscr, 9, 2, (out[-200:] if out else err[-200:] if err else "Done"), max_len=w - 3)

        draw_text(self.stdscr, 12, 2, f"Return code: {rc}", curses.A_BOLD)
        draw_text(self.stdscr, 14, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def change_model(self):
        """Change the HERMES_MODEL for all agents."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        if h < 20 or w < 50:
            draw_text(self.stdscr, 2, 2, "Terminal too small.", curses.color_pair(5))
            self.stdscr.refresh()
            self.stdscr.getch()
            return

        draw_text(self.stdscr, 1, 2, " CHANGE MODEL ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        current = get_env_value("HERMES_MODEL") or "not set"
        draw_text(self.stdscr, 5, 2, f"Current model: {current}")
        draw_text(self.stdscr, 7, 2, "Available models:")
        models = [
            "llama-3-8b",
            "custom:code4:llama-3-8b",
        ]
        for i, m in enumerate(models):
            marker = "\u2192" if m == current else " "
            draw_text(self.stdscr, 9 + i, 4, f"{marker} {i + 1}. {m}")

        prompt_y = 18
        draw_text(self.stdscr, prompt_y, 2, "Select number (or 'c' for custom): ")
        self.stdscr.refresh()

        curses.echo()
        curses.curs_set(1)
        try:
            ch = self.stdscr.getch()
            if 49 <= ch <= 56:  # 1-8
                new_model = models[ch - 49]
            elif ch in (ord('c'), ord('C')):
                draw_text(self.stdscr, prompt_y + 1, 2, "Enter model (provider/name): ")
                self.stdscr.refresh()
                new_model = self.stdscr.getstr(prompt_y + 1, 35, 60).decode().strip()
            else:
                return
        finally:
            curses.noecho()
            curses.curs_set(0)

        if not new_model:
            return

        set_env_value("HERMES_MODEL", new_model)
        draw_text(self.stdscr, prompt_y + 2, 2, f"Model changed to: {new_model}")
        draw_text(self.stdscr, prompt_y + 3, 2, "Restarting all agents...")
        self.stdscr.refresh()
        docker_compose("restart")
        draw_text(self.stdscr, prompt_y + 4, 2, "Done. Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def view_logs(self):
        """View logs for a specific agent."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " VIEW LOGS ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

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
        if ch not in agent_map:
            return
        agent = agent_map[ch]

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
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

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
        if h < 10 or w < 40:
            draw_text(self.stdscr, 2, 2, "Terminal too small.", curses.color_pair(5))
            self.stdscr.refresh()
            self.stdscr.getch()
            return

        draw_text(self.stdscr, 1, 2, " API / FLOWWINK TEST ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        y = 5
        max_y = h - 4

        # Test each agent's API
        for name, info in AGENTS.items():
            if y >= max_y:
                break
            token = get_env_value(f"HERMES_{name.upper()}_TOKEN")
            status, model = check_agent_health(name, info["port"])

            color = curses.color_pair(1) if status == "healthy" else curses.color_pair(5)
            draw_text(self.stdscr, y, 2, f"{info['emoji']} {name}: ", color | curses.A_BOLD)
            draw_text(self.stdscr, y, 20, f"Status: {status}")
            y += 1

            if token and y < max_y:
                draw_text(self.stdscr, y, 4, f"Token: {token[:20]}...")
                y += 1

            # Try a real API call
            if status == "healthy" and y < max_y:
                try:
                    url = f"http://127.0.0.1:{info['port']}/api/status?token={token}"
                    req = urllib.request.Request(url)
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        data = json.loads(resp.read())
                        draw_text(self.stdscr, y, 4, f"API OK -- Model: {data.get('model', '?')}")
                except Exception as e:
                    draw_text(self.stdscr, y, 4, f"API Error: {str(e)[:50]}")
                y += 1

        # Test Flowwink MCP
        if y < max_y:
            y += 1
            draw_text(self.stdscr, min(y, max_y - 1), 2, " FLOWWINK MCP ", curses.A_BOLD)
            y += 1
            fw_key = get_env_value("FLOWWINK_API_KEY")
            if fw_key and y < max_y:
                draw_text(self.stdscr, y, 4, f"Key: {fw_key[:20]}...")
                y += 1
                if y < max_y:
                    op_token = get_env_value("HERMES_OPERATOR_TOKEN")
                    try:
                        url = f"http://127.0.0.1:3002/api/status?token={op_token}"
                        req = urllib.request.Request(url)
                        with urllib.request.urlopen(req, timeout=5) as resp:
                            data = json.loads(resp.read())
                            draw_text(self.stdscr, y, 4, "Operator API: OK")
                    except Exception as e:
                        draw_text(self.stdscr, y, 4, f"Operator API: {str(e)[:50]}")
                    y += 1
            elif y < max_y:
                draw_text(self.stdscr, y, 4, "No FLOWWINK_API_KEY configured")
                y += 1

        draw_text(self.stdscr, h - 3, 2, "Press any key to return...")
        self.stdscr.refresh()
        self.stdscr.getch()

    def edit_env(self):
        """View and edit environment variables."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        if h < 10 or w < 40:
            draw_text(self.stdscr, 2, 2, "Terminal too small.", curses.color_pair(5))
            self.stdscr.refresh()
            self.stdscr.getch()
            return

        draw_text(self.stdscr, 1, 2, " ENVIRONMENT CONFIG ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        # Read env vars first
        env_vars = []
        try:
            with open(ENV_FILE) as f:
                for line in f:
                    line = line.rstrip()
                    if line and not line.startswith("#"):
                        key = line.split("=", 1)[0]
                        val = line.split("=", 1)[1] if "=" in line else ""
                        if "KEY" in key or "TOKEN" in key or "SECRET" in key:
                            display_val = val[:8] + "..." + val[-4:] if len(val) > 12 else "***"
                        else:
                            display_val = val
                        env_vars.append(f"{key}={display_val}")
        except FileNotFoundError:
            env_vars = [f"File not found: {ENV_FILE}"]

        # Scrollable display
        max_lines = h - 8
        offset = 0

        while True:
            self.stdscr.erase()
            draw_text(self.stdscr, 1, 2, " ENVIRONMENT CONFIG ", curses.color_pair(6) | curses.A_BOLD)
            draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
            draw_text(self.stdscr, 4, 2, f"File: {ENV_FILE}", curses.A_DIM)

            y = 5
            for i in range(offset, min(offset + max_lines, len(env_vars))):
                if y >= h - 4:
                    break
                draw_text(self.stdscr, y, 4, env_vars[i], max_len=w - 5)
                y += 1

            scroll_info = f"[{offset + 1}-{min(offset + max_lines, len(env_vars))}/{len(env_vars)}] ↑↓ scroll | q quit"
            draw_text(self.stdscr, h - 3, 2, scroll_info, curses.color_pair(6))
            draw_text(self.stdscr, h - 2, 2, f"To edit: nano {ENV_FILE}", curses.A_DIM)
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q')):
                break
            elif key == curses.KEY_DOWN and offset < max(0, len(env_vars) - max_lines):
                offset += 1
            elif key == curses.KEY_UP and offset > 0:
                offset -= 1
            elif key == curses.KEY_NPAGE:
                offset = min(len(env_vars) - max_lines, offset + max_lines)
            elif key == curses.KEY_PPAGE:
                offset = max(0, offset - max_lines)



    def fleet_panel(self):
        """EasyPanel-style fleet and image controls."""
        actions = [
            ("1", "Pull latest Hermes image", self._fleet_pull_image),
            ("2", "Recreate Hermes services", self._fleet_recreate_agents),
            ("3", "Show image/version info", self._fleet_image_info),
            ("4", "Show compose status", self._fleet_compose_status),
            ("5", "Prune dangling images", self._fleet_prune_images),
        ]
        selected = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            draw_text(self.stdscr, 1, 2, " HERMESHOTEL EASYPANEL ", curses.color_pair(6) | curses.A_BOLD)
            draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
            draw_text(self.stdscr, 4, 2, "Fleet/image operations for all containerized Hermes instances.", curses.color_pair(10), max_len=w - 4)
            y = 6
            for idx, (key, label, _) in enumerate(actions):
                marker = "▶" if idx == selected else " "
                draw_text(self.stdscr, y, 4, f"{marker} {key}. {label}", curses.color_pair(2) if idx == selected else 0, max_len=w - 8)
                y += 1
            draw_text(self.stdscr, h - 2, 2, "↑↓ move | Enter run | q back", curses.color_pair(6), max_len=w - 4)
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                return
            if key == curses.KEY_DOWN:
                selected = min(len(actions) - 1, selected + 1)
            elif key == curses.KEY_UP:
                selected = max(0, selected - 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                actions[selected][2]()
            else:
                for idx, (shortcut, _, func) in enumerate(actions):
                    if key == ord(shortcut):
                        selected = idx
                        func()
                        break

    def _run_stream_screen(self, title, commands):
        """Run shell commands sequentially and show collected output."""
        lines = []
        for label, cmd, timeout in commands:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            draw_text(self.stdscr, 1, 2, f" {title} ", curses.color_pair(6) | curses.A_BOLD, max_len=w - 4)
            draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
            draw_text(self.stdscr, 5, 2, f"Running: {label}", curses.color_pair(3) | curses.A_BOLD, max_len=w - 4)
            draw_text(self.stdscr, 7, 2, cmd, curses.A_DIM, max_len=w - 4)
            self.stdscr.refresh()
            rc, out, err = run(cmd, timeout=timeout)
            lines.append(f"$ {label}")
            lines.append(f"rc={rc}")
            output = (out or err or "").splitlines()
            lines.extend(output[-20:] if output else ["(no output)"])
            lines.append("")
        self.message_screen(title, lines[-(self.stdscr.getmaxyx()[0] - 6):])

    def _fleet_pull_image(self):
        self._run_stream_screen("Pull Latest Image", [
            ("before image inspect", "docker image inspect nousresearch/hermes-agent:latest --format '{{.Id}} {{.Created}}'", 30),
            ("compose pull Hermes services", f"docker compose -f {shlex.quote(COMPOSE_FILE)} --env-file {shlex.quote(ENV_FILE)} pull hermes-customer hermes-operator hermes-supplier", 300),
            ("after image inspect", "docker image inspect nousresearch/hermes-agent:latest --format '{{.Id}} {{.Created}}'", 30),
        ])

    def _fleet_recreate_agents(self):
        self._run_stream_screen("Recreate Hermes Services", [
            ("recreate services", f"docker compose -f {shlex.quote(COMPOSE_FILE)} --env-file {shlex.quote(ENV_FILE)} up -d --force-recreate hermes-customer hermes-operator hermes-supplier", 300),
            ("compose ps", f"docker compose -f {shlex.quote(COMPOSE_FILE)} --env-file {shlex.quote(ENV_FILE)} ps", 60),
        ])

    def _fleet_image_info(self):
        self._run_stream_screen("Image / Version Info", [
            ("local image", "docker image inspect nousresearch/hermes-agent:latest --format '{{.RepoTags}} {{.Id}} {{.Created}}'", 30),
            ("operator hermes version", "docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && hermes --version'", 60),
            ("operator model smoke test", "docker exec hermes-operator /bin/sh -lc '. /opt/hermes/.venv/bin/activate && timeout 120 hermes -z '\"'\"'Svara med endast orden: fleet ok'\"'\"''", 160),
        ])

    def _fleet_compose_status(self):
        self._run_stream_screen("Compose Status", [
            ("compose ps", f"docker compose -f {shlex.quote(COMPOSE_FILE)} --env-file {shlex.quote(ENV_FILE)} ps", 60),
            ("docker stats snapshot", "docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}} {{.MemPerc}}'", 60),
        ])

    def _fleet_prune_images(self):
        self._run_stream_screen("Prune Dangling Images", [
            ("docker image prune", "docker image prune -f", 120),
        ])

    def mcp_panel(self):
        """Show HermesHotel MCP orchestration design and hooks."""
        lines = [
            "HermesHotel should expose MCP tools so one Hermes can spawn/manage more Hermes instances.",
            "",
            "Planned MCP tool surface:",
            "- hermeshotel_list_instances: read instances.json + compose status",
            "- hermeshotel_spawn_instance: create profile, compose service, port/domain, env token",
            "- hermeshotel_remove_instance: stop/remove service and mark inactive",
            "- hermeshotel_pull_image: pull nousresearch/hermes-agent:latest",
            "- hermeshotel_recreate_instance: recreate one Hermes service",
            "- hermeshotel_get_config: read masked config files",
            "- hermeshotel_patch_config: safe patch + validate + backup",
            "- hermeshotel_reload_proxy: validate/reload Caddy",
            "",
            "Security model:",
            "- allowlisted profile directory only",
            "- never return raw secrets",
            "- write backups before patching",
            "- validate YAML/JSON/Caddy before applying",
            "- require explicit approval for destructive remove/prune",
            "",
            "Next implementation target:",
            "- add a small MCP server under mcp/hermeshotel_server.py",
            "- register it in operator config as local stdio/http MCP",
            "- back it with the same config registry used by TUI option 8",
        ]
        self.message_screen("MCP Orchestration", lines)

    def web_panel_config(self):
        """Configure the HermesHotel web panel — domain, start/stop."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " WEB PANEL CONFIG ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))

        # Check if web panel container exists
        result = subprocess.run(
            ["docker", "inspect", "hermeshotel-web", "--format", "{{.State.Status}}"],
            capture_output=True, text=True
        )
        web_running = result.returncode == 0 and result.stdout.strip() == "running"

        # Check for domain in Caddyfile
        caddy_domain = "not configured"
        caddy_file = "/etc/caddy/Caddyfile"
        try:
            with open(caddy_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("{") and not line.startswith("}") and not line.startswith("(") and "hermeshotel" in line.lower() or "hermeshotel.froste.eu" in line:
                        if line.endswith("{") or ("hermeshotel" in line and "." in line):
                            caddy_domain = line.replace(" {", "").strip()
                            break
        except FileNotFoundError:
            pass

        lines = [
            f"Status: {'RUNNING' if web_running else 'STOPPED'}",
            f"Caddy domain: {caddy_domain}",
            f"Port: 3099",
            "",
            "Options:",
            "  d. Set Caddy Domain",
            f"  {'s' if web_running else 'S'}. {'Stop' if web_running else 'Start'} Web Panel",
            "  r. Reload Caddy",
            "",
        ]
        y = 5
        for line in lines:
            draw_text(self.stdscr, y, 2, line)
            y += 1
        draw_text(self.stdscr, y, 2, "q. Back")
        self.stdscr.refresh()

        while True:
            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                return
            elif key in (ord('d'), ord('D')):
                self.stdscr.erase()
                draw_text(self.stdscr, 1, 2, " SET WEB PANEL DOMAIN ", curses.color_pair(6) | curses.A_BOLD)
                draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
                draw_text(self.stdscr, 5, 2, "Domain (e.g. hermeshotel.example.com): ")
                self.stdscr.refresh()
                curses.echo()
                curses.curs_set(1)
                try:
                    domain = self.stdscr.getstr(5, 45, 40).decode().strip()
                finally:
                    curses.noecho()
                    curses.curs_set(0)
                if domain:
                    # Update Caddyfile
                    if not os.path.exists(caddy_file):
                        self.message_screen("Web Panel", [f"Caddyfile not found at {caddy_file}"])
                        continue
                    # Remove old hermeshotel block if exists
                    with open(caddy_file) as f:
                        content = f.read()
                    # Simple approach: append new block
                    with open(caddy_file, "a") as f:
                        f.write(f"\n{domain} {{\n    reverse_proxy localhost:3099\n}}\n")
                    self.message_screen("Web Panel", [f"Added {domain} → localhost:3099 to Caddyfile", "Press 'r' to reload Caddy"])
            elif key in (ord('s'), ord('S')):
                action = "start" if not web_running else "stop"
                subprocess.run(["docker", "compose", "-f", "docker-compose.yml", action, "hermeshotel-web"],
                               cwd="/opt/hermeshotel", capture_output=True)
                self.message_screen("Web Panel", [f"Web panel {action}ed"])
                return
            elif key in (ord('r'), ord('R')):
                result = subprocess.run(["caddy", "reload", "--config", caddy_file],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    self.message_screen("Web Panel", ["Caddy reloaded"])
                else:
                    self.message_screen("Web Panel", [f"Caddy reload failed: {result.stderr[:200]}"])

    def config_files(self):
        """Browse, view, validate, and edit stack config files."""
        configs = get_config_files()
        selected = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            if h < 16 or w < 70:
                draw_text(self.stdscr, 2, 2, "Terminal too small for config cockpit.", curses.color_pair(5))
                self.stdscr.refresh()
                self.stdscr.getch()
                return

            draw_text(self.stdscr, 1, 2, " CONFIG COCKPIT ", curses.color_pair(6) | curses.A_BOLD)
            draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
            draw_text(self.stdscr, 4, 2, "These files make the official Hermes container boot with the current settings.", curses.color_pair(10))

            top = 6
            visible = h - 11
            start = max(0, min(selected - visible + 1, len(configs) - visible))
            start = max(0, start)
            for row, idx in enumerate(range(start, min(start + visible, len(configs)))):
                cfg = configs[idx]
                marker = "▶" if idx == selected else " "
                exists = "OK" if cfg["path"].exists() else "MISS"
                color = curses.color_pair(2) if idx == selected else 0
                if exists == "MISS":
                    color = curses.color_pair(5)
                line = f"{marker} {idx + 1:>2}. {cfg['label']:<24} [{exists}] {str(cfg['path'])}"
                draw_text(self.stdscr, top + row, 2, line, color, max_len=w - 4)

            cfg = configs[selected]
            detail_y = h - 5
            draw_arcane_box(self.stdscr, detail_y - 1, 0, h - 1, w - 1, curses.color_pair(6))
            draw_text(self.stdscr, detail_y, 2, f"Why: {cfg['why']}", curses.color_pair(6), max_len=w - 4)
            draw_text(self.stdscr, detail_y + 1, 2, "Enter view | e edit | v validate | a apply/restart | ↑↓ move | q quit", curses.color_pair(6), max_len=w - 4)
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break
            if key == curses.KEY_DOWN:
                selected = min(len(configs) - 1, selected + 1)
            elif key == curses.KEY_UP:
                selected = max(0, selected - 1)
            elif key in (curses.KEY_ENTER, 10, 13):
                self.view_config_file(configs[selected])
            elif key in (ord('e'), ord('E')):
                self.edit_config_file(configs[selected])
            elif key in (ord('v'), ord('V')):
                self.validate_config_screen(configs[selected])
            elif key in (ord('a'), ord('A')):
                self.apply_config_screen(configs[selected])
            elif ord('1') <= key <= ord('9'):
                idx = key - ord('1')
                if idx < len(configs):
                    selected = idx

    def view_config_file(self, cfg):
        """Scrollable masked config viewer."""
        path = cfg["path"]
        try:
            raw_lines = path.read_text(errors="replace").splitlines()
            lines = [mask_secret_line(line) for line in raw_lines]
        except Exception as e:
            lines = [f"Could not read {path}: {e}"]

        offset = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            draw_text(self.stdscr, 0, 1, f" VIEW: {cfg['label']} ", curses.color_pair(6) | curses.A_BOLD, max_len=w - 2)
            draw_text(self.stdscr, 1, 1, str(path), curses.A_DIM, max_len=w - 2)
            visible = max(1, h - 5)
            for i in range(visible):
                idx = offset + i
                if idx >= len(lines):
                    break
                line = f"{idx + 1:>4}│ {lines[idx]}"
                color = curses.color_pair(3) if any(x in lines[idx].lower() for x in ("todo", "fixme", "missing")) else 0
                draw_text(self.stdscr, i + 3, 1, line, color, max_len=w - 2)
            footer = f"{offset + 1}-{min(offset + visible, len(lines))}/{len(lines)} | ↑↓ PgUp/PgDn scroll | e edit | v validate | q back"
            draw_text(self.stdscr, h - 1, 1, footer, curses.color_pair(6), max_len=w - 2)
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                break
            elif key == curses.KEY_DOWN and offset < max(0, len(lines) - visible):
                offset += 1
            elif key == curses.KEY_UP and offset > 0:
                offset -= 1
            elif key == curses.KEY_NPAGE:
                offset = min(max(0, len(lines) - visible), offset + visible)
            elif key == curses.KEY_PPAGE:
                offset = max(0, offset - visible)
            elif key in (ord('e'), ord('E')):
                self.edit_config_file(cfg)
                try:
                    raw_lines = path.read_text(errors="replace").splitlines()
                    lines = [mask_secret_line(line) for line in raw_lines]
                except Exception as e:
                    lines = [f"Could not read {path}: {e}"]
            elif key in (ord('v'), ord('V')):
                self.validate_config_screen(cfg)

    def edit_config_file(self, cfg):
        """Open a config in $EDITOR, validate it, and optionally apply changes."""
        path = cfg["path"]
        if not path.exists():
            self.message_screen("Edit Config", [f"File not found: {path}"])
            return
        editor = os.environ.get("EDITOR", "nano")
        backup = path.with_suffix(path.suffix + f".bak-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        try:
            backup.write_text(path.read_text())
        except Exception as e:
            self.message_screen("Edit Config", [f"Could not create backup:", str(e)])
            return

        curses.def_prog_mode()
        curses.endwin()
        rc = subprocess.call(f"{shlex.quote(editor)} {shlex.quote(str(path))}", shell=True)
        self.stdscr.refresh()
        curses.reset_prog_mode()
        curses.curs_set(0)

        ok, msg = validate_config_file(path, cfg["kind"])
        lines = [
            f"Editor exit code: {rc}",
            f"Backup: {backup}",
            f"Validation: {msg}",
        ]
        if not ok:
            lines += ["", "Validation failed. Press r to restore backup, any other key to keep edit."]
            key = self.message_screen("Validation Failed", lines, wait=False)
            if key in (ord('r'), ord('R')):
                path.write_text(backup.read_text())
                self.message_screen("Restored", [f"Restored from {backup}"])
            return

        lines += ["", "Press a to apply/restart now, any other key to return."]
        key = self.message_screen("Edit Saved", lines, wait=False)
        if key in (ord('a'), ord('A')):
            self.apply_config_screen(cfg)

    def validate_config_screen(self, cfg):
        ok, msg = validate_config_file(cfg["path"], cfg["kind"])
        title = "Validation OK" if ok else "Validation Failed"
        self.message_screen(title, [cfg["label"], str(cfg["path"]), "", msg])

    def apply_config_screen(self, cfg):
        self.stdscr.erase()
        draw_text(self.stdscr, 2, 2, f"Applying {cfg['label']}...", curses.color_pair(3) | curses.A_BOLD)
        draw_text(self.stdscr, 4, 2, f"Mode: {cfg.get('restart')}")
        self.stdscr.refresh()
        rc, out, err = apply_config_restart(cfg)
        output = (out or err or "Done").splitlines()
        lines = [f"Return code: {rc}", ""] + output[-12:]
        self.message_screen("Apply Result", lines)

    def message_screen(self, title, lines, wait=True):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, f" {title} ", curses.color_pair(6) | curses.A_BOLD, max_len=w - 4)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
        y = 5
        for line in lines:
            if y >= h - 3:
                break
            draw_text(self.stdscr, y, 2, str(line), max_len=w - 4)
            y += 1
        draw_text(self.stdscr, h - 2, 2, "Press any key to continue...", curses.color_pair(6), max_len=w - 4)
        self.stdscr.refresh()
        key = self.stdscr.getch()
        if wait:
            return key
        return key


    def create_first_hermes(self):
        """Create first Hermes instance with domain configuration."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " CREATE FIRST HERMES ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
        draw_text(self.stdscr, 5, 2, "No agents found. Let's set up your first Hermes!")
        draw_text(self.stdscr, 6, 2, "Name (e.g. operator): ")
        draw_text(self.stdscr, 7, 2, "Domain (e.g. operator.example.com): ")
        draw_text(self.stdscr, 8, 2, "OpenAI API Key (sk-proj-...): ")
        draw_text(self.stdscr, 9, 2, "LLM Base URL (https://api.openai.com/v1): ")
        self.stdscr.refresh()
        curses.echo()
        curses.curs_set(1)
        try:
            name = self.stdscr.getstr(6, 30, 20).decode().strip()
            domain = self.stdscr.getstr(7, 40, 40).decode().strip()
            api_key = self.stdscr.getstr(8, 35, 60).decode().strip()
            llm_url = self.stdscr.getstr(9, 45, 60).decode().strip()
        finally:
            curses.noecho()
            curses.curs_set(0)
        if not name:
            name = "operator"
        if not domain:
            self.message_screen("Create First Hermes", ["Domain is required."])
            return
        if not api_key:
            self.message_screen("Create First Hermes", ["OpenAI API Key is required."])
            return
        if not llm_url:
            llm_url = "https://api.openai.com/v1"
        # Update .env with API key and LLM URL
        env_path = "/opt/hermeshotel/.env"
        try:
            with open(env_path) as f:
                env_lines = f.readlines()
        except FileNotFoundError:
            env_lines = []
        new_env = []
        for line in env_lines:
            if line.startswith("OPENAI_API_KEY="):
                new_env.append(f"OPENAI_API_KEY={api_key}\n")
            elif line.startswith("LLM_BASE_URL="):
                new_env.append(f"LLM_BASE_URL={llm_url}\n")
            else:
                new_env.append(line)
        with open(env_path, "w") as f:
            f.writelines(new_env)
        # Run add-hermes.sh with domain
        add_script = "/opt/hermeshotel/scripts/add-hermes.sh"
        if not os.path.isfile(add_script):
            self.message_screen("Create First Hermes", [f"Script missing: {add_script}"])
            return
        proc = subprocess.run(
            ["/bin/bash", add_script, name, domain],
            capture_output=True, text=True, cwd="/opt/hermeshotel"
        )
        if proc.returncode != 0:
            self.message_screen("Create First Hermes", [f"Script failed (code {proc.returncode})", proc.stderr[:300]])
            return
        # Reload
        global AGENTS
        AGENTS = get_agents()
        self.message_screen("Create First Hermes", [
            f"✔ hermes-{name} created!",
            f"Domain: {domain}",
            f"API Key: {api_key[:12]}...",
            f"LLM URL: {llm_url}",
            "",
            "Container is starting... wait ~15s then visit:",
            f"  https://{domain}"
        ])

    def add_instance(self):
        """Add a new Hermes agent from operator template using scripts/add-hermes.sh."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        draw_text(self.stdscr, 1, 2, " ADD HERMES AGENT ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
        draw_text(self.stdscr, 5, 2, "Profile name (lowercase, e.g. sales): ")
        draw_text(self.stdscr, 6, 2, "Domain (e.g. sales.example.com): ")
        self.stdscr.refresh()
        curses.echo()
        curses.curs_set(1)
        try:
            name = self.stdscr.getstr(5, 40, 20).decode().strip()
            domain = self.stdscr.getstr(6, 40, 40).decode().strip()
        finally:
            curses.noecho()
            curses.curs_set(0)
        if not name or not name.islower() or not name.replace("_", "").isalnum():
            self.message_screen("Add Hermes", ["Invalid name. Use lowercase letters/underscores only."])
            return
        if not domain:
            domain = f"{name}.froste.eu"
        # Run add‑hermes.sh with domain
        add_script = "/opt/hermeshotel/scripts/add-hermes.sh"
        if not os.path.isfile(add_script):
            self.message_screen("Add Hermes", [f"Script missing: {add_script}"])
            return
        proc = subprocess.run(
            ["/bin/bash", add_script, name, domain],
            capture_output=True, text=True, cwd="/opt/hermeshotel"
        )
        if proc.returncode != 0:
            self.message_screen("Add Hermes", [f"Script failed (code {proc.returncode})", proc.stderr[:300]])
            return
        # Reload instances
        global AGENTS
        AGENTS = get_agents()
        self.message_screen("Add Hermes", [f"✔ hermes-{name} added!", f"Domain: {domain}", "", proc.stdout[:400]])

    def remove_instance(self):
        """Remove or deactivate an instance from instances.json."""
        instances = load_instances()
        if not instances:
            self.message_screen("Remove Instance", ["No instances configured."])
            return
        selected = 0
        while True:
            self.stdscr.erase()
            h, w = self.stdscr.getmaxyx()
            draw_text(self.stdscr, 1, 2, " REMOVE INSTANCE ", curses.color_pair(6) | curses.A_BOLD)
            draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
            draw_text(self.stdscr, 4, 2, "Enter removes from TUI list only. It does not delete Docker volumes or profiles.", curses.color_pair(3), max_len=w - 4)
            for idx, inst in enumerate(instances[: h - 8]):
                marker = "▶" if idx == selected else " "
                active = "active" if inst.get("active", True) else "inactive"
                line = f"{marker} {idx + 1}. {inst.get('name')}  {inst.get('domain')}  {active}"
                draw_text(self.stdscr, 6 + idx, 2, line, curses.color_pair(2) if idx == selected else 0, max_len=w - 4)
            draw_text(self.stdscr, h - 2, 2, "↑↓ move | Enter remove | d deactivate | q cancel", curses.color_pair(6), max_len=w - 4)
            self.stdscr.refresh()
            key = self.stdscr.getch()
            if key in (ord('q'), ord('Q'), 27):
                return
            if key == curses.KEY_DOWN:
                selected = min(len(instances) - 1, selected + 1)
            elif key == curses.KEY_UP:
                selected = max(0, selected - 1)
            elif key in (ord('d'), ord('D')):
                instances[selected]["active"] = False
                save_instances(instances)
                global AGENTS
                AGENTS = get_agents()
                self.message_screen("Remove Instance", [f"Deactivated {instances[selected].get('name')}"])
                return
            elif key in (curses.KEY_ENTER, 10, 13):
                removed = instances.pop(selected)
                save_instances(instances)
                AGENTS = get_agents()
                self.message_screen("Remove Instance", [f"Removed {removed.get('name')} from {INSTANCES_FILE}"])
                return

    def chat_agent(self):
        """Chat with the Hermes operator agent via CLI."""
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        if h < 15 or w < 60:
            draw_text(self.stdscr, 2, 2, "Terminal too small.", curses.color_pair(5))
            self.stdscr.refresh()
            self.stdscr.getch()
            return

        draw_text(self.stdscr, 1, 2, " CHAT WITH OPERATOR AGENT ", curses.color_pair(6) | curses.A_BOLD)
        draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
        draw_text(self.stdscr, 4, 2, "Type your message (or 'q' to quit):", curses.color_pair(6))

        curses.echo()
        curses.curs_set(1)

        try:
            while True:
                draw_text(self.stdscr, 5, 2, "> " + " " * (w - 5), 0)
                draw_text(self.stdscr, 5, 4, "", 0)
                self.stdscr.refresh()

                try:
                    input_bytes = self.stdscr.getstr(5, 4, w - 10)
                    user_input = input_bytes.decode().strip()
                except Exception:
                    break

                if not user_input:
                    continue
                if user_input.lower() in ('q', 'quit'):
                    break

                # Show "thinking" indicator
                draw_text(self.stdscr, 7, 2, "Agent is thinking...", curses.color_pair(3) | curses.A_BOLD)
                self.stdscr.refresh()

                # Call the Hermes CLI
                inner_cmd = ". /opt/hermes/.venv/bin/activate && hermes -z " + shlex.quote(user_input)
                cmd = "docker exec hermes-operator /bin/sh -lc " + shlex.quote(inner_cmd)
                rc, out, err = run(cmd, timeout=60)

                # Clear thinking and show response
                self.stdscr.erase()
                draw_text(self.stdscr, 1, 2, " CHAT WITH OPERATOR AGENT ", curses.color_pair(6) | curses.A_BOLD)
                draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
                draw_text(self.stdscr, 4, 2, f"You: {user_input}", curses.color_pair(2))
                draw_text(self.stdscr, 6, 2, "Agent:", curses.color_pair(3) | curses.A_BOLD)

                response = out.strip() or err.strip() or "No response received."
                # Word wrap the response
                y = 6
                words = response.split()
                line = "  "
                for word in words:
                    if len(line) + len(word) + 1 > w - 4:
                        draw_text(self.stdscr, y, 2, line, max_len=w - 3)
                        y += 1
                        line = "  " + word
                    else:
                        line += " " + word if line.strip() else word
                if line.strip():
                    draw_text(self.stdscr, y, 2, line, max_len=w - 3)
                    y += 1

                draw_text(self.stdscr, h - 3, 2, "Press any key to continue chatting...", curses.color_pair(6))
                self.stdscr.refresh()
                self.stdscr.getch()

                # Clear screen for next message
                self.stdscr.erase()
                draw_text(self.stdscr, 1, 2, " CHAT WITH OPERATOR AGENT ", curses.color_pair(6) | curses.A_BOLD)
                draw_arcane_box(self.stdscr, 0, 0, 3, w - 1, curses.color_pair(6))
                draw_text(self.stdscr, 4, 2, "Type your message (or 'q' to quit):", curses.color_pair(6))

        finally:
            curses.noecho()
            curses.curs_set(0)


def main(stdscr):
    tui = HermesTUI(stdscr)
    tui.run()


if __name__ == "__main__":
    # Parse CLI args
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--env-file" and i + 1 < len(sys.argv):
            ENV_FILE = sys.argv[i + 1]
            i += 2
        elif arg == "--compose" and i + 1 < len(sys.argv):
            COMPOSE_FILE = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    curses.wrapper(main)
