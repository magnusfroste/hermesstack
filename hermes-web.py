#!/usr/bin/env python3
"""Lightweight HermesHotel status web UI.

This intentionally avoids third-party dependencies so it can run from a tiny
Python container. It reads Docker status through the mounted Docker socket and
checks the internal Hermes dashboard endpoints over the compose network.
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import time
import urllib.request
import http.server
from pathlib import Path

PORT = int(os.environ.get("HERMESHOTEL_WEB_PORT", "3099"))
DOCKER_SOCKET = os.environ.get("DOCKER_SOCKET", "/var/run/docker.sock")
REFRESH_SECONDS = int(os.environ.get("HERMESHOTEL_REFRESH_SECONDS", "5"))
ROOT = Path(os.path.dirname(os.path.abspath(__file__)))

def load_agents() -> list[dict[str, Any]]:
    try:
        with open(ROOT / "instances.json") as f:
            data = json.load(f)
            instances = data.get("instances", [])
    except Exception:
        instances = []
    agents = []
    for inst in instances:
        name = inst.get("name", "unknown")
        container = inst.get("container", f"hermes-{name}")
        domain = inst.get("domain", f"{name}.froste.eu")
        agents.append({
            "name": name,
            "label": inst.get("label", name.capitalize() + " Agent"),
            "container": container,
            "domain": domain,
            "internal_url": f"http://{container}:3000/",
            "public_url": f"https://{domain}/",
            "accent": inst.get("accent", "#67e8f9"),
        })
    return agents

AGENTS = load_agents()


class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str):
        super().__init__("localhost")
        self.socket_path = socket_path

    def connect(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.connect(self.socket_path)


def docker_get(path: str) -> Any:
    conn = UnixHTTPConnection(DOCKER_SOCKET)
    try:
        conn.request("GET", path)
        resp = conn.getresponse()
        body = resp.read()
        if resp.status >= 400:
            raise RuntimeError(f"Docker API {resp.status}: {body[:200]!r}")
        if not body:
            return None
        return json.loads(body.decode("utf-8"))
    finally:
        conn.close()


def check_http(url: str, timeout: float = 2.0) -> tuple[bool, int | None, str]:
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, resp.status, "ok"
    except Exception as exc:  # noqa: BLE001 - status endpoint should never crash page
        return False, None, str(exc)[:120]


def pct(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f}%"


def bytes_human(value: int | float | None) -> str:
    if value is None:
        return "-"
    units = ["B", "KB", "MB", "GB", "TB"]
    v = float(value)
    for unit in units:
        if v < 1024 or unit == units[-1]:
            return f"{v:.1f}{unit}" if unit != "B" else f"{int(v)}B"
        v /= 1024
    return f"{v:.1f}TB"


def compute_cpu(stats: dict[str, Any]) -> float | None:
    try:
        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - stats["precpu_stats"]["system_cpu_usage"]
        online = stats["cpu_stats"].get("online_cpus") or len(stats["cpu_stats"]["cpu_usage"].get("percpu_usage", [])) or 1
        if system_delta > 0 and cpu_delta > 0:
            return (cpu_delta / system_delta) * online * 100
    except Exception:
        return None
    return None


def collect_status() -> dict[str, Any]:
    started = time.time()
    containers = docker_get("/containers/json?all=1") or []
    by_name: dict[str, dict[str, Any]] = {}
    for item in containers:
        names = [n.lstrip("/") for n in item.get("Names", [])]
        for name in names:
            by_name[name] = item

    image = None
    try:
        img = docker_get("/images/nousresearch/hermes-agent:latest/json")
        image = {
            "id": (img.get("Id") or "").replace("sha256:", "")[:12],
            "created": img.get("Created"),
            "tags": img.get("RepoTags") or [],
        }
    except Exception as exc:
        image = {"error": str(exc)[:120]}

    agents = []
    for spec in AGENTS:
        item = by_name.get(spec["container"], {})
        running = item.get("State") == "running"
        health = item.get("Status", "missing")
        ok, code, err = check_http(spec["internal_url"])
        stats_summary = {"cpu": None, "mem_usage": None, "mem_limit": None, "mem_pct": None}
        if item.get("Id") and running:
            try:
                stats = docker_get(f"/containers/{item['Id']}/stats?stream=false")
                mem_usage = stats.get("memory_stats", {}).get("usage")
                mem_limit = stats.get("memory_stats", {}).get("limit")
                stats_summary = {
                    "cpu": compute_cpu(stats),
                    "mem_usage": mem_usage,
                    "mem_limit": mem_limit,
                    "mem_pct": (mem_usage / mem_limit * 100) if mem_usage and mem_limit else None,
                }
            except Exception:
                pass
        agents.append(
            {
                **spec,
                "running": running,
                "docker_status": health,
                "http_ok": ok,
                "http_code": code,
                "http_error": None if ok else err,
                "stats": stats_summary,
            }
        )

    redis = by_name.get("hermes-redis", {})
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "latency_ms": int((time.time() - started) * 1000),
        "image": image,
        "agents": agents,
        "redis": {"running": redis.get("State") == "running", "status": redis.get("Status", "missing")},
        "summary": {
            "total": len(agents),
            "running": sum(1 for a in agents if a["running"]),
            "http_ok": sum(1 for a in agents if a["http_ok"]),
        },
    }


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>HermesHotel Light Panel</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🏨</text></svg>">
  <style>
    :root {
      --ink: #f7f2e8;
      --muted: #b7aa96;
      --bg: #15120e;
      --panel: rgba(39, 31, 23, .74);
      --line: rgba(247, 242, 232, .14);
      --good: #84cc16;
      --bad: #ef4444;
      --warn: #f59e0b;
      --cyan: #67e8f9;
      --shadow: 0 24px 80px rgba(0,0,0,.42);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: ui-serif, Georgia, Cambria, "Times New Roman", serif;
      background:
        radial-gradient(circle at 15% 15%, rgba(251,191,36,.18), transparent 30rem),
        radial-gradient(circle at 85% 0%, rgba(94,234,212,.16), transparent 28rem),
        linear-gradient(135deg, #110f0b 0%, #24190f 48%, #111827 100%);
    }
    .grain { position: fixed; inset: 0; pointer-events: none; opacity: .18; background-image: linear-gradient(90deg, rgba(255,255,255,.05) 1px, transparent 1px), linear-gradient(rgba(255,255,255,.04) 1px, transparent 1px); background-size: 42px 42px; }
    main { width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 34px 0 48px; }
    header { display: flex; justify-content: space-between; gap: 20px; align-items: end; margin-bottom: 24px; }
    h1 { font-size: clamp(2.3rem, 7vw, 5.8rem); letter-spacing: -.07em; line-height: .9; margin: 0; }
    .subtitle { color: var(--muted); font-size: 1.08rem; max-width: 620px; margin-top: 14px; }
    .pill { border: 1px solid var(--line); background: rgba(255,255,255,.06); border-radius: 999px; padding: 10px 14px; color: var(--muted); white-space: nowrap; }
    .grid { display: grid; grid-template-columns: 1.1fr .9fr; gap: 18px; }
    .panel { border: 1px solid var(--line); background: var(--panel); border-radius: 28px; box-shadow: var(--shadow); backdrop-filter: blur(18px); }
    .panel h2 { margin: 0; padding: 22px 22px 0; font-size: 1.1rem; color: var(--muted); font-weight: 500; }
    .summary { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 18px; }
    .metric { border: 1px solid var(--line); border-radius: 22px; padding: 18px; background: rgba(255,255,255,.04); }
    .metric b { font-size: 2.4rem; display: block; letter-spacing: -.04em; }
    .metric span { color: var(--muted); }
    .agents { display: grid; gap: 14px; padding: 18px; }
    .agent { border: 1px solid var(--line); border-radius: 24px; padding: 18px; background: linear-gradient(135deg, rgba(255,255,255,.07), rgba(255,255,255,.025)); position: relative; overflow: hidden; }
    .agent:before { content: ""; position: absolute; inset: 0 auto 0 0; width: 5px; background: var(--accent, var(--cyan)); }
    .agent-top { display: flex; justify-content: space-between; gap: 14px; align-items: start; }
    .agent h3 { margin: 0 0 6px; font-size: 1.45rem; }
    .agent a { color: var(--ink); text-decoration: none; }
    .agent a:hover { color: var(--accent, var(--cyan)); }
    .domain { color: var(--muted); font-size: .95rem; }
    .status { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; border-radius: 999px; padding: 7px 10px; font-size: .8rem; }
    .ok { background: rgba(132,204,22,.16); color: #bef264; }
    .fail { background: rgba(239,68,68,.15); color: #fecaca; }
    .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 16px; }
    .stat { color: var(--muted); font-size: .88rem; }
    .stat strong { color: var(--ink); display: block; font-size: 1rem; margin-top: 4px; }
    .side { padding: 18px; display: grid; gap: 14px; }
    .button-row { display: grid; gap: 10px; }
    .button-row a { border: 1px solid var(--line); color: var(--ink); text-decoration: none; border-radius: 18px; padding: 14px 16px; background: rgba(255,255,255,.04); transition: .18s ease; }
    .button-row a:hover { transform: translateY(-1px); background: rgba(255,255,255,.08); }
    code { color: #fde68a; }
    .small { color: var(--muted); font-size: .94rem; line-height: 1.55; }
    .pulse { display:inline-block; width:10px; height:10px; border-radius:50%; background:var(--good); box-shadow:0 0 0 0 rgba(132,204,22,.7); animation:pulse 1.8s infinite; margin-right:8px; }
    @keyframes pulse { 70% { box-shadow:0 0 0 12px rgba(132,204,22,0); } 100% { box-shadow:0 0 0 0 rgba(132,204,22,0); } }
    @media (max-width: 860px) { header, .grid { grid-template-columns: 1fr; display: grid; } .summary, .stats { grid-template-columns: 1fr; } .pill { white-space: normal; } }
  </style>
</head>
<body>
  <div class="grain"></div>
  <main>
    <header>
      <div>
        <h1>HermesHotel</h1>
        <div class="subtitle">Lightweight EasyPanel for the containerized Hermes fleet. Official Hermes UI remains the control surface; this page shows what is alive.</div>
      </div>
      <div class="pill"><span class="pulse"></span><span id="stamp">loading...</span></div>
    </header>
    <section class="grid">
      <div class="panel">
        <h2>Fleet</h2>
        <div class="summary">
          <div class="metric"><b id="running">-</b><span>containers running</span></div>
          <div class="metric"><b id="httpok">-</b><span>dashboards responding</span></div>
          <div class="metric"><b id="latency">-</b><span>status latency</span></div>
        </div>
        <div class="agents" id="agents"></div>
      </div>
      <aside class="panel side">
        <div>
          <h2 style="padding:0 0 12px">Quick Links</h2>
          <div class="button-row">
            <a href="https://operator.froste.eu/">Open Operator Dashboard</a>
            <a href="https://customer.froste.eu/">Open Customer Dashboard</a>
            <a href="https://supplier.froste.eu/">Open Supplier Dashboard</a>
          </div>
        </div>
        <div class="small">
          <h2 style="padding:0 0 12px">Runtime</h2>
          <p>Image: <code id="image">-</code></p>
          <p>Redis: <code id="redis">-</code></p>
          <p>Refresh: <code>{{REFRESH_SECONDS}}s</code></p>
        </div>
        <div class="small">
          <h2 style="padding:0 0 12px">Control Plane</h2>
           <p>Use <code>python3 hermes-tui.py</code> for editing configs, pulling images, recreating services, and future MCP orchestration.</p>
        </div>
      </aside>
    </section>
  </main>
  <script>
    const agentsEl = document.getElementById('agents');
    const fmtPct = n => n === null || n === undefined ? '-' : `${Number(n).toFixed(1)}%`;
    const fmtBytes = n => {
      if (!n) return '-';
      const units = ['B','KB','MB','GB','TB']; let v = Number(n); let i = 0;
      while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
      return `${v.toFixed(i ? 1 : 0)}${units[i]}`;
    };
    async function refresh() {
      const res = await fetch('/api/status', { cache: 'no-store' });
      const data = await res.json();
      document.getElementById('stamp').textContent = data.generated_at;
      document.getElementById('running').textContent = `${data.summary.running}/${data.summary.total}`;
      document.getElementById('httpok').textContent = `${data.summary.http_ok}/${data.summary.total}`;
      document.getElementById('latency').textContent = `${data.latency_ms}ms`;
      document.getElementById('image').textContent = data.image?.id ? `${data.image.id} ${data.image.created || ''}` : (data.image?.error || '-');
      document.getElementById('redis').textContent = data.redis.running ? data.redis.status : 'not running';
      agentsEl.innerHTML = data.agents.map(a => {
        const ok = a.running && a.http_ok;
        return `<article class="agent" style="--accent:${a.accent}">
          <div class="agent-top">
            <div><h3><a href="${a.public_url}">${a.label}</a></h3><div class="domain">${a.domain} · ${a.container}</div></div>
            <div class="status ${ok ? 'ok' : 'fail'}">${ok ? 'ONLINE' : 'CHECK'}</div>
          </div>
          <div class="stats">
            <div class="stat">Docker<strong>${a.docker_status}</strong></div>
            <div class="stat">CPU<strong>${fmtPct(a.stats.cpu)}</strong></div>
            <div class="stat">Memory<strong>${fmtBytes(a.stats.mem_usage)} · ${fmtPct(a.stats.mem_pct)}</strong></div>
          </div>
        </article>`;
      }).join('');
    }
    refresh().catch(err => { agentsEl.innerHTML = `<article class="agent"><h3>Status error</h3><p>${err}</p></article>`; });
    setInterval(refresh, {{REFRESH_MS}});
  </script>
</body>
</html>
"""


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "HermesHotelLight/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - - [%s] %s" % (self.client_address[0], self.log_date_time_string(), fmt % args), flush=True)

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/" or self.path.startswith("/?"):
            html = HTML.replace("{{REFRESH_SECONDS}}", str(REFRESH_SECONDS)).replace("{{REFRESH_MS}}", str(REFRESH_SECONDS * 1000))
            self._send(200, "text/html; charset=utf-8", html.encode("utf-8"))
            return
        if self.path == "/api/status":
            try:
                body = json.dumps(collect_status(), ensure_ascii=False).encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
            except Exception as exc:  # noqa: BLE001 - return JSON error instead of crashing
                body = json.dumps({"error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self._send(500, "application/json; charset=utf-8", body)
            return
        self._send(404, "text/plain; charset=utf-8", b"not found")


def main() -> None:
    server = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"HermesHotel light web listening on 0.0.0.0:{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
