#!/usr/bin/env python3
"""Generate docker-compose.yml from instances.json and profiles/*.

The instance list is the source of truth for which agents to run.
"""

import json
from pathlib import Path

ROOT = Path("/opt/hermeshotel")
INSTANCES_FILE = ROOT / "instances.json"
PROFILES_DIR = ROOT / "profiles"
OUTPUT_FILE = ROOT / "docker-compose.yml"

def load_instances() -> dict:
    try:
        with open(INSTANCES_FILE) as f:
            data = json.load(f)
            return {i["name"]: i for i in data.get("instances", [])}
    except Exception:
        return {}

def agent_block(profile: str, inst: dict) -> str:
    port = inst.get("port", 3000)
    profile_upper = profile.upper()
    token_var = "HERMES_SESSION_TOKEN"

    block = [
        f"  hermes-{profile}:",
        f"    image: nousresearch/hermes-agent:latest",
        f"    container_name: hermes-{profile}",
        f"    restart: unless-stopped",
        f"    environment:",
        f"      - HERMES_HOME=/data/hermes-profiles/{profile}",
        f"      - HERMES_MODEL=${{HERMES_MODEL:-gpt-4.1}}",
        f"      - OPENAI_API_KEY=${{OPENAI_API_KEY}}",
        f"      - ANTHROPIC_API_KEY=${{ANTHROPIC_API_KEY}}",
    ]
    block += [
        f"      - PROFILE_ROLE={profile}",
        f"      - {token_var}=${{{token_var}}}",
        f"      - HERMES_DASHBOARD=1",
        f"      - HERMES_DASHBOARD_HOST=0.0.0.0",
        f"      - HERMES_DASHBOARD_PORT=3000",
        f"      - HERMES_DASHBOARD_TUI=1",
        f"    volumes:",
        f"      - {profile}-data:/data/hermes-profiles/{profile}",
        f"      - /opt/hermeshotel/profiles/{profile}/config.yaml:/data/hermes-profiles/{profile}/config.yaml",
        f"    ports:",
        f'      - "127.0.0.1:{port}:3000"',
        f'    command: ["sleep", "infinity"]',
        f"    networks:",
        f"      - hermes-network",
        f"    healthcheck:",
        f'      test: ["CMD", "curl", "-f", "http://localhost:3000/"]',
        f"      interval: 30s",
        f"      timeout: 10s",
        f"      retries: 3",
    ]
    return "\n".join(block)

def main():
    instances = load_instances()
    profile_names = sorted(instances.keys())

    lines = [
        "# HermesHotel — auto-generated docker-compose.yml",
        "# DO NOT EDIT MANUALLY — use scripts/generate-compose.py",
        "",
        "services:",
    ]

    for profile in profile_names:
        inst = instances[profile]
        lines.append("")
        lines.append(agent_block(profile, inst))

    # redis
    lines.append("")
    lines.append("  redis:")
    lines.append("    image: redis:7-alpine")
    lines.append("    container_name: hermes-redis")
    lines.append("    restart: unless-stopped")
    lines.append("    volumes:")
    lines.append("      - redis-data:/data")
    lines.append("    networks:")
    lines.append("      - hermes-network")
    lines.append("    command: redis-server --appendonly yes")

    # hermeshotel-web
    lines.append("")
    lines.append("  hermeshotel-web:")
    lines.append("    image: python:3.12-alpine")
    lines.append("    container_name: hermeshotel-web")
    lines.append("    restart: unless-stopped")
    lines.append("    working_dir: /app")
    lines.append("    environment:")
    lines.append("      - HERMESHOTEL_WEB_PORT=3099")
    lines.append("      - HERMESHOTEL_REFRESH_SECONDS=5")
    lines.append("    volumes:")
    lines.append("      - /opt/hermeshotel/hermes-web.py:/app/hermes-web.py:ro")
    lines.append("      - /opt/hermeshotel/instances.json:/app/instances.json:ro")
    lines.append("      - /var/run/docker.sock:/var/run/docker.sock:ro")
    lines.append("    ports:")
    lines.append('      - "127.0.0.1:3099:3099"')
    lines.append('    command: ["python", "/app/hermes-web.py"]')
    lines.append("    networks:")
    lines.append("      - hermes-network")
    if profile_names:
        lines.append("    depends_on:")
        for p in profile_names:
            lines.append(f"      - hermes-{p}")

    # volumes
    lines.append("")
    lines.append("volumes:")
    for profile in profile_names:
        lines.append(f"  {profile}-data:")
    lines.append("  redis-data:")

    # networks
    lines.append("")
    lines.append("networks:")
    lines.append("  hermes-network:")
    lines.append("    driver: bridge")

    content = "\n".join(lines) + "\n"
    OUTPUT_FILE.write_text(content)
    print(f"✔ Generated {OUTPUT_FILE} — {len(profile_names)} agents")

if __name__ == "__main__":
    main()
