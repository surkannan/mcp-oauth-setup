# Dockerfile for MCP Okta Server
FROM python:3.12.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./

# Install dependencies using uv (generate lock file if needed)
RUN uv sync

# Copy source code after dependencies are installed
COPY *.py ./

# Create non-root user with home directory
RUN groupadd -r mcpserver && useradd -r -g mcpserver -m -d /home/mcpserver mcpserver
RUN chown -R mcpserver:mcpserver /app
RUN mkdir -p /home/mcpserver/.cache && chown -R mcpserver:mcpserver /home/mcpserver

USER mcpserver

# Set uv cache directory to writable location
ENV UV_CACHE_DIR=/tmp/uv-cache
RUN mkdir -p /tmp/uv-cache && chown mcpserver:mcpserver /tmp/uv-cache

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f -H "MCP-Protocol-Version: 2025-06-18" \
        http://localhost:${MCP_SERVER_PORT:-8001}/.well-known/oauth-protected-resource || exit 1

# Run the server
CMD ["uv", "run", "python", "mcp_server.py"]