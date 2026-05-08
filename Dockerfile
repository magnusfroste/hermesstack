# Hermes Agent - Easypanel Deployment
# Based on NousResearch/hermes-agent with patches for reverse proxy support

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast Python package management
RUN pip install uv

# Clone Hermes Agent
RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /app/hermes

WORKDIR /app/hermes

# Build web frontend first
WORKDIR /app/hermes/web
RUN npm ci && npm run build

WORKDIR /app/hermes

# Install Hermes with web extras using uv
RUN uv pip install --system -e ".[web,messaging,cron,cli,mcp]"

# Create Hermes home directory
RUN mkdir -p /root/.hermes

# Patch web_server.py to allow external origins (for Traefik/Easypanel)
RUN sed -i 's/allow_origin_regex=r"^https?:\/\/(localhost|127\\.0\\.0\\.1)(:\\d+)?$"/allow_origins=["*"]/g' hermes_cli/web_server.py

# Expose the port
EXPOSE 3000

# Start command - bind to 0.0.0.0 for container, use --insecure for external access
CMD ["python", "-m", "hermes_cli.main", "dashboard", "--host", "0.0.0.0", "--port", "3000", "--insecure", "--no-browser"]
