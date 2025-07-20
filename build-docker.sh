#!/bin/bash

# Build script for MCP OAuth Docker images

set -e

echo "🐳 Building MCP OAuth Docker images..."

# Build server
echo "📦 Building MCP Server..."
cd mcp-okta-server
docker build -t mcp-okta-server:latest .
echo "✅ Server build complete"
cd ..

# Build client  
echo "📦 Building MCP Client..."
cd mcp-okta-client
docker build -t mcp-okta-client:latest .
echo "✅ Client build complete"
cd ..

echo "🎉 All Docker images built successfully!"

# Show images
echo "📋 Built images:"
docker images | grep mcp-okta

echo ""
echo "🚀 To run with Docker Compose:"
echo "   docker-compose up mcp-server"
echo ""
echo "🚀 To run server directly:"
echo "   docker run -d --name mcp-server -p 8001:8001 --env-file mcp-okta-server/.env -e MCP_SERVER_HOST=0.0.0.0 mcp-okta-server:latest"