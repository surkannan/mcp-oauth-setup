# Dockerfile for MCP Okta Client
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
RUN groupadd -r mcpclient && useradd -r -g mcpclient -m -d /home/mcpclient mcpclient
RUN chown -R mcpclient:mcpclient /app
RUN mkdir -p /home/mcpclient/.cache && chown -R mcpclient:mcpclient /home/mcpclient

USER mcpclient

# Set uv cache directory to writable location
ENV UV_CACHE_DIR=/tmp/uv-cache
RUN mkdir -p /tmp/uv-cache && chown mcpclient:mcpclient /tmp/uv-cache

# Note: Client runs interactively and opens browser
# In container environments, this would need adaptation for headless operation
# or running as a service with API endpoints

# Run the client
CMD ["uv", "run", "python", "mcp_client.py"]