# MCP OAuth Setup Guide: Using Okta as Authorization Server

A comprehensive guide for junior developers to set up an end-to-end Model Context Protocol (MCP) system with Okta OAuth authentication.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Okta Configuration](#okta-configuration)
4. [MCP Server Setup](#mcp-server-setup)
5. [MCP Client Setup](#mcp-client-setup)
6. [Testing the Complete Flow](#testing-the-complete-flow)
7. [Code Examples](#code-examples)
8. [Troubleshooting](#troubleshooting)
9. [Security Best Practices](#security-best-practices)

## Overview

This guide will help you set up:
- **Okta** as your OAuth 2.0 Authorization Server
- **MCP HTTP Server** as a Resource Server that validates tokens via Okta
- **MCP Client** that authenticates users and calls protected MCP tools

### Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │◄──►│ Okta (OAuth AS) │◄──►│  MCP Server     │
│                 │    │                 │    │ (Resource Server│
│ - Requests auth │    │ - Issues tokens │    │ - Validates     │
│ - Calls tools   │    │ - User login    │    │   tokens        │
│ - Handles PKCE  │    │ - Token refresh │    │ - Serves tools  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Prerequisites

### Required Software
- **Python 3.9+** with pip or uv
- **Node.js 18+** (for some tools)
- **Git**
- **Okta Developer Account** (free)

### Required Knowledge
- Basic Python programming
- Understanding of OAuth 2.0 concepts
- Command line familiarity
- JSON configuration

### Install MCP Python SDK
```bash
# Using uv (recommended)
uv add @modelcontextprotocol/sdk

# Or using pip
pip install mcp
```

## Okta Configuration

### Step 1: Create Okta Developer Account

1. Go to [developer.okta.com](https://developer.okta.com)
2. Sign up for a free developer account
3. Verify your email and complete setup
4. Note your **Okta domain** (e.g., `https://dev-12345.okta.com`)

### Step 2: Create OAuth Application

1. **Login to Okta Admin Console**
   - Go to your Okta domain admin panel
   - Navigate to **Applications > Applications**

2. **Create New App Integration**
   - Click **Create App Integration**
   - Choose **OIDC - OpenID Connect**
   - Choose **Web Application**

3. **Configure Application Settings**
   ```
   App integration name: MCP Server App
   Grant types: 
     ☑ Authorization Code
     ☑ Refresh Token
   Sign-in redirect URIs:
     - http://localhost:8001/oauth/callback
     - http://localhost:3030/oauth/callback
   Sign-out redirect URIs: (leave empty)
   Controlled access: Allow everyone in your organization to access
   ```

4. **Save and Note Credentials**
   - **Client ID**: `0oa4xyz123...` (copy this)
   - **Client Secret**: `abc123xyz...` (copy this)
   - **Okta Domain**: `https://dev-12345.okta.com`

### Step 3: Configure Authorization Server

1. **Navigate to Security > API**
2. **Select "default" Authorization Server** (or create a custom one)
3. **Configure Scopes**
   - Go to **Scopes** tab
   - Add custom scope: `mcp:access` with description "Access to MCP tools"
4. **Note the Issuer URI**: `https://dev-12345.okta.com/oauth2/default`

### Step 4: Create Test User (Optional)

1. Go to **Directory > People**
2. Add a test user or use your admin account
3. Ensure user is activated

## MCP Server Setup

### Step 1: Create MCP Server Project

```bash
# Create project directory
mkdir mcp-okta-server
cd mcp-okta-server

# Initialize Python project
uv init
# or
pip install mcp fastapi uvicorn httpx python-jose[cryptography]
```

### Step 2: Create Environment Configuration

Create `.env` file:
```bash
# Okta Configuration
OKTA_DOMAIN=https://dev-12345.okta.com
OKTA_CLIENT_ID=0oa4xyz123...
OKTA_CLIENT_SECRET=abc123xyz...
OKTA_AUDIENCE=api://default
OKTA_ISSUER=https://dev-12345.okta.com/oauth2/default

# Server Configuration
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8001
MCP_SERVER_URL=http://localhost:8001

# Required scopes
MCP_REQUIRED_SCOPES=mcp:access
```

### Step 3: Create Okta Token Verifier

Create `okta_token_verifier.py`:

```python
"""
Okta Token Verifier for MCP Server
Validates JWT tokens issued by Okta using token introspection.
"""

import os
import logging
from typing import Optional
import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class OktaTokenVerifier(TokenVerifier):
    """Token verifier that validates tokens using Okta's introspection endpoint."""
    
    def __init__(self):
        self.okta_domain = os.getenv('OKTA_DOMAIN')
        self.client_id = os.getenv('OKTA_CLIENT_ID')
        self.client_secret = os.getenv('OKTA_CLIENT_SECRET')
        self.introspection_url = f"{self.okta_domain}/oauth2/default/v1/introspect"
        
        if not all([self.okta_domain, self.client_id, self.client_secret]):
            raise ValueError("Missing required Okta environment variables")
    
    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Verify token using Okta's introspection endpoint."""
        
        async with httpx.AsyncClient() as client:
            try:
                # Call Okta introspection endpoint
                response = await client.post(
                    self.introspection_url,
                    auth=(self.client_id, self.client_secret),
                    data={"token": token, "token_type_hint": "access_token"},
                    headers={"Accept": "application/json"},
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Token introspection failed: {response.status_code}")
                    return None
                
                token_data = response.json()
                
                # Check if token is active
                if not token_data.get("active", False):
                    logger.debug("Token is not active")
                    return None
                
                # Extract token information
                scopes = token_data.get("scope", "").split()
                client_id = token_data.get("client_id", "unknown")
                expires_at = token_data.get("exp")
                username = token_data.get("username") or token_data.get("sub")
                
                logger.info(f"Token verified for user: {username}, client: {client_id}")
                
                return AccessToken(
                    token=token,
                    client_id=client_id,
                    scopes=scopes,
                    expires_at=expires_at,
                    resource=None  # Okta doesn't use RFC 8707 resource parameter
                )
                
            except Exception as e:
                logger.error(f"Error verifying token: {e}")
                return None
```

### Step 4: Create MCP Server with Okta Integration

Create `mcp_server.py`:

```python
"""
MCP Server with Okta OAuth Integration
A FastMCP server that uses Okta for OAuth authentication.
"""

import os
import logging
import datetime
from typing import Any
from dotenv import load_dotenv

from mcp.server.fastmcp.server import FastMCP
from mcp.server.auth.settings import AuthSettings
from okta_token_verifier import OktaTokenVerifier

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with Okta authentication."""
    
    # Get configuration from environment
    host = os.getenv('MCP_SERVER_HOST', 'localhost')
    port = int(os.getenv('MCP_SERVER_PORT', '8001'))
    server_url = os.getenv('MCP_SERVER_URL', f'http://{host}:{port}')
    okta_issuer = os.getenv('OKTA_ISSUER')
    required_scopes = os.getenv('MCP_REQUIRED_SCOPES', 'mcp:access').split()
    
    if not okta_issuer:
        raise ValueError("OKTA_ISSUER environment variable is required")
    
    # Create Okta token verifier
    token_verifier = OktaTokenVerifier()
    
    # Configure authentication settings
    auth_settings = AuthSettings(
        issuer_url=okta_issuer,
        required_scopes=required_scopes,
        resource_server_url=server_url,
    )
    
    # Create FastMCP server as Resource Server
    app = FastMCP(
        name="MCP Server with Okta Auth",
        instructions="MCP Server that uses Okta for OAuth authentication",
        host=host,
        port=port,
        debug=True,
        token_verifier=token_verifier,
        auth=auth_settings,
    )
    
    # Define protected tools
    @app.tool()
    async def get_current_time() -> dict[str, Any]:
        """
        Get the current server time.
        
        This tool is protected by Okta OAuth authentication.
        User must have valid token with 'mcp:access' scope.
        """
        now = datetime.datetime.now()
        return {
            "current_time": now.isoformat(),
            "timezone": "UTC",
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            "message": "Hello from authenticated MCP server!"
        }
    
    @app.tool()
    async def calculate_square(number: float) -> dict[str, Any]:
        """
        Calculate the square of a number.
        
        Args:
            number: The number to square
            
        Returns:
            Dictionary with the original number and its square
        """
        result = number ** 2
        return {
            "input": number,
            "square": result,
            "calculation": f"{number}² = {result}"
        }
    
    @app.resource("user-info")
    async def get_user_info() -> str:
        """Get information about the authenticated user."""
        # In a real implementation, you would extract user info from the token
        return "User information would be extracted from the Okta token"
    
    return app


def main():
    """Main entry point for the MCP server."""
    try:
        server = create_mcp_server()
        
        host = os.getenv('MCP_SERVER_HOST', 'localhost')
        port = int(os.getenv('MCP_SERVER_PORT', '8001'))
        
        logger.info(f"🚀 MCP Server with Okta Auth starting on {host}:{port}")
        logger.info(f"🔑 Using Okta issuer: {os.getenv('OKTA_ISSUER')}")
        logger.info(f"📋 Required scopes: {os.getenv('MCP_REQUIRED_SCOPES')}")
        
        # Run the server
        server.run(transport="streamable-http")
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


if __name__ == "__main__":
    main()
```

### Step 5: Add Dependencies

Create `pyproject.toml`:

```toml
[project]
name = "mcp-okta-server"
version = "0.1.0"
description = "MCP Server with Okta OAuth authentication"
dependencies = [
    "mcp>=1.0.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
    "httpx>=0.25.0",
    "python-dotenv>=1.0.0",
    "python-jose[cryptography]>=3.3.0"
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

## MCP Client Setup

### Step 1: Create Client Project

```bash
# Create client directory
mkdir mcp-okta-client
cd mcp-okta-client

# Initialize project
uv init
```

### Step 2: Create Okta OAuth Client Provider

Create `okta_oauth_provider.py`:

```python
"""
Okta OAuth Client Provider for MCP
Handles OAuth flow with Okta authorization server.
"""

import os
import webbrowser
from typing import Optional
import httpx
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthClientInformationFull, OAuthClientMetadata, OAuthToken

class OktaOAuthProvider(OAuthClientProvider):
    """OAuth provider for Okta integration."""
    
    def __init__(self, storage: TokenStorage):
        self.storage = storage
        self.okta_domain = os.getenv('OKTA_DOMAIN')
        self.client_id = os.getenv('OKTA_CLIENT_ID')
        self.client_secret = os.getenv('OKTA_CLIENT_SECRET')
        self.redirect_uri = "http://localhost:3030/oauth/callback"
        
        if not all([self.okta_domain, self.client_id]):
            raise ValueError("Missing required Okta environment variables")
    
    async def get_authorization_url(self, state: str, code_challenge: str) -> str:
        """Generate Okta authorization URL."""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid profile mcp:access",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256"
        }
        
        auth_url = f"{self.okta_domain}/oauth2/default/v1/authorize"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{auth_url}?{query_string}"
    
    async def exchange_code_for_tokens(self, code: str, code_verifier: str) -> OAuthToken:
        """Exchange authorization code for tokens."""
        
        token_url = f"{self.okta_domain}/oauth2/default/v1/token"
        
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code != 200:
                raise Exception(f"Token exchange failed: {response.status_code} {response.text}")
            
            token_data = response.json()
            
            return OAuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token"),
                scope=token_data.get("scope", "")
            )
```

### Step 3: Create MCP Client Application

Create `mcp_client.py`:

```python
"""
MCP Client with Okta OAuth Integration
Connects to MCP server using Okta authentication.
"""

import os
import asyncio
import secrets
import hashlib
import base64
import webbrowser
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time
from dotenv import load_dotenv

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthToken
from okta_oauth_provider import OktaOAuthProvider

# Load environment
load_dotenv()

class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""
    
    def do_GET(self):
        """Handle OAuth callback."""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)
        
        if 'code' in query_params:
            self.server.auth_code = query_params['code'][0]
            self.server.state = query_params.get('state', [None])[0]
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            self.wfile.write(b"""
            <html>
                <body>
                    <h1>Authorization Successful!</h1>
                    <p>You can close this window and return to the application.</p>
                    <script>setTimeout(() => window.close(), 2000);</script>
                </body>
            </html>
            """)
        else:
            self.send_response(400)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress logging."""
        pass

class InMemoryTokenStorage:
    """Simple in-memory token storage."""
    
    def __init__(self):
        self._tokens: Optional[OAuthToken] = None
    
    async def get_tokens(self) -> Optional[OAuthToken]:
        return self._tokens
    
    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

def generate_pkce_pair():
    """Generate PKCE code verifier and challenge."""
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge

async def start_callback_server(port=3030):
    """Start HTTP server for OAuth callback."""
    server = HTTPServer(('localhost', port), CallbackHandler)
    server.auth_code = None
    server.state = None
    
    # Run server in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    return server

async def wait_for_callback(server, timeout=300):
    """Wait for OAuth callback."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if server.auth_code:
            return server.auth_code, server.state
        await asyncio.sleep(0.1)
    
    raise TimeoutError("Timeout waiting for OAuth callback")

async def authenticate_with_okta():
    """Perform OAuth authentication with Okta."""
    print("🔐 Starting Okta OAuth authentication...")
    
    # Generate PKCE parameters
    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)
    
    # Start callback server
    callback_server = await start_callback_server()
    
    # Create OAuth provider
    storage = InMemoryTokenStorage()
    oauth_provider = OktaOAuthProvider(storage)
    
    try:
        # Generate authorization URL
        auth_url = await oauth_provider.get_authorization_url(state, code_challenge)
        
        print(f"🌐 Opening browser for authentication...")
        print(f"📋 If browser doesn't open, visit: {auth_url}")
        
        # Open browser
        webbrowser.open(auth_url)
        
        # Wait for callback
        print("⏳ Waiting for authentication...")
        auth_code, received_state = await wait_for_callback(callback_server)
        
        if received_state != state:
            raise ValueError("Invalid state parameter - possible CSRF attack")
        
        print("✅ Authorization code received!")
        
        # Exchange code for tokens
        print("🔄 Exchanging code for tokens...")
        tokens = await oauth_provider.exchange_code_for_tokens(auth_code, code_verifier)
        
        print("🎉 Authentication successful!")
        return tokens
        
    finally:
        callback_server.shutdown()

async def main():
    """Main client application."""
    print("🚀 MCP Client with Okta OAuth")
    
    # Server configuration
    server_url = os.getenv('MCP_SERVER_URL', 'http://localhost:8001/mcp')
    
    try:
        # Authenticate with Okta
        tokens = await authenticate_with_okta()
        
        print(f"🔗 Connecting to MCP server: {server_url}")
        
        # Create authenticated HTTP client
        headers = {
            "Authorization": f"Bearer {tokens.access_token}"
        }
        
        # Connect to MCP server
        async with streamablehttp_client(
            url=server_url,
            headers=headers,
            timeout=timedelta(seconds=30)
        ) as (read_stream, write_stream, get_session_id):
            
            print("🤝 Initializing MCP session...")
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                session_id = get_session_id()
                print(f"✨ Connected! Session ID: {session_id}")
                
                # List available tools
                print("\n📋 Available tools:")
                tools_result = await session.list_tools()
                for i, tool in enumerate(tools_result.tools, 1):
                    print(f"  {i}. {tool.name}: {tool.description}")
                
                # Call some tools
                print("\n🔧 Testing tools:")
                
                # Test get_current_time
                print("⏰ Getting current time...")
                time_result = await session.call_tool("get_current_time", {})
                print(f"   Result: {time_result.content[0].text}")
                
                # Test calculate_square
                print("🔢 Calculating square of 7...")
                square_result = await session.call_tool("calculate_square", {"number": 7})
                print(f"   Result: {square_result.content[0].text}")
                
                # List resources
                print("\n📁 Available resources:")
                resources_result = await session.list_resources()
                for resource in resources_result.resources:
                    print(f"  - {resource.name}: {resource.description}")
                
                print("\n✅ All tests completed successfully!")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
```

### Step 4: Client Dependencies

Create `pyproject.toml`:

```toml
[project]
name = "mcp-okta-client"
version = "0.1.0"
description = "MCP Client with Okta OAuth authentication"
dependencies = [
    "mcp>=1.0.0",
    "httpx>=0.25.0",
    "python-dotenv>=1.0.0"
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### Step 5: Client Environment

Create `.env` for client:

```bash
# Okta Configuration (same as server)
OKTA_DOMAIN=https://dev-12345.okta.com
OKTA_CLIENT_ID=0oa4xyz123...
OKTA_CLIENT_SECRET=abc123xyz...

# MCP Server URL
MCP_SERVER_URL=http://localhost:8001/mcp
```

## Testing the Complete Flow

### Step 1: Start the MCP Server

```bash
cd mcp-okta-server

# Install dependencies
uv sync
# or pip install -r requirements.txt

# Start the server
uv run python mcp_server.py
# or python mcp_server.py
```

Expected output:
```
🚀 MCP Server with Okta Auth starting on localhost:8001
🔑 Using Okta issuer: https://dev-12345.okta.com/oauth2/default
📋 Required scopes: mcp:access
INFO:     Started server process
INFO:     Uvicorn running on http://localhost:8001
```

### Step 2: Test Server Endpoints

```bash
# Test OAuth metadata discovery
curl http://localhost:8001/.well-known/oauth-protected-resource

# Expected response:
{
  "resource": "http://localhost:8001",
  "authorization_servers": ["https://dev-12345.okta.com/oauth2/default"]
}
```

### Step 3: Run the MCP Client

```bash
cd mcp-okta-client

# Install dependencies
uv sync

# Run the client
uv run python mcp_client.py
```

Expected flow:
1. Browser opens for Okta login
2. User logs in with Okta credentials
3. Client receives authorization code
4. Client exchanges code for access token
5. Client connects to MCP server with token
6. Client calls protected tools successfully

### Step 4: Verify Authentication

Check server logs for successful token validation:
```
INFO:okta_token_verifier:Token verified for user: john.doe@example.com, client: 0oa4xyz123...
INFO:mcp_server:Tool 'get_current_time' called by authenticated user
```

## Code Examples

### Custom Tool with User Context

```python
@app.tool()
async def get_user_profile(context: AuthContext) -> dict[str, Any]:
    """Get the authenticated user's profile information."""
    
    # Extract user info from token (in real implementation)
    user_info = {
        "user_id": context.user_id,
        "username": context.username,
        "scopes": context.scopes,
        "client_id": context.client_id
    }
    
    return {
        "profile": user_info,
        "server_time": datetime.datetime.now().isoformat(),
        "authentication_method": "Okta OAuth 2.0"
    }
```

### Token Refresh Example

```python
async def refresh_token_if_needed(oauth_provider, tokens):
    """Refresh access token if it's close to expiring."""
    
    if tokens.expires_in and tokens.expires_in < 300:  # Less than 5 minutes
        print("🔄 Refreshing access token...")
        
        new_tokens = await oauth_provider.refresh_access_token(tokens.refresh_token)
        await oauth_provider.storage.set_tokens(new_tokens)
        
        print("✅ Token refreshed successfully!")
        return new_tokens
    
    return tokens
```

### Error Handling Example

```python
async def call_tool_with_retry(session, tool_name, args, oauth_provider, tokens):
    """Call MCP tool with automatic token refresh on 401."""
    
    try:
        return await session.call_tool(tool_name, args)
    
    except UnauthorizedError:
        print("🔄 Token expired, refreshing...")
        
        # Refresh token
        new_tokens = await oauth_provider.refresh_access_token(tokens.refresh_token)
        
        # Update session headers
        session.update_headers({
            "Authorization": f"Bearer {new_tokens.access_token}"
        })
        
        # Retry the call
        return await session.call_tool(tool_name, args)
```

## Troubleshooting

### Common Issues

#### 1. "Invalid Client" Error
**Problem**: Client ID or secret is incorrect
**Solution**: 
- Verify client credentials in Okta admin console
- Check environment variables are set correctly
- Ensure client secret is not expired

#### 2. "Invalid Scope" Error
**Problem**: Requested scope doesn't exist in Okta
**Solution**:
- Create `mcp:access` scope in Okta authorization server
- Ensure scope is added to your application's allowed scopes

#### 3. Token Validation Fails
**Problem**: Server can't validate tokens from Okta
**Solution**:
- Check Okta domain and issuer URL
- Verify introspection endpoint is accessible
- Ensure server has correct client credentials for introspection

#### 4. CORS Issues
**Problem**: Browser blocks OAuth redirect
**Solution**:
- Ensure redirect URI matches exactly in Okta app config
- Use `http://localhost` (not `127.0.0.1`) for local development

#### 5. Connection Timeouts
**Problem**: Slow network or server issues
**Solution**:
- Increase timeout values in HTTP clients
- Check firewall settings
- Verify server is accessible from client

### Debug Steps

#### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

#### Test Okta Connectivity
```bash
# Test Okta auth server metadata
curl https://dev-12345.okta.com/oauth2/default/.well-known/oauth-authorization-server

# Test token introspection endpoint (with valid credentials)
curl -X POST https://dev-12345.okta.com/oauth2/default/v1/introspect \
  -u "client_id:client_secret" \
  -d "token=ACCESS_TOKEN"
```

#### Test MCP Server Without Auth
```python
# Temporarily disable auth to test basic functionality
app = FastMCP(
    name="Test Server",
    # auth=None,  # Comment out auth for testing
    # token_verifier=None
)
```

### Environment Variables Checklist

Server `.env`:
```bash
✓ OKTA_DOMAIN=https://dev-12345.okta.com
✓ OKTA_CLIENT_ID=0oa4xyz123...
✓ OKTA_CLIENT_SECRET=abc123xyz...
✓ OKTA_AUDIENCE=api://default
✓ OKTA_ISSUER=https://dev-12345.okta.com/oauth2/default
✓ MCP_SERVER_HOST=localhost
✓ MCP_SERVER_PORT=8001
✓ MCP_SERVER_URL=http://localhost:8001
✓ MCP_REQUIRED_SCOPES=mcp:access
```

Client `.env`:
```bash
✓ OKTA_DOMAIN=https://dev-12345.okta.com
✓ OKTA_CLIENT_ID=0oa4xyz123...
✓ OKTA_CLIENT_SECRET=abc123xyz...
✓ MCP_SERVER_URL=http://localhost:8001/mcp
```

## Security Best Practices

### 1. Environment Security
- **Never commit secrets**: Use `.env` files and add them to `.gitignore`
- **Rotate credentials**: Regularly rotate client secrets in Okta
- **Use HTTPS**: Always use HTTPS in production (never HTTP)

### 2. Token Security
- **Short-lived tokens**: Configure short access token lifetimes (15-60 minutes)
- **Refresh tokens**: Use refresh tokens for longer sessions
- **Secure storage**: Store tokens securely (encrypted at rest)

### 3. Scope Management
- **Principle of least privilege**: Only request necessary scopes
- **Fine-grained scopes**: Create specific scopes for different tool categories
- **Scope validation**: Always validate scopes on the server side

### 4. Network Security
- **TLS encryption**: Use TLS 1.2+ for all communications
- **Certificate validation**: Never disable certificate verification
- **Network isolation**: Use firewalls and network segmentation

### 5. Logging and Monitoring
- **Audit logs**: Log all authentication events
- **Token monitoring**: Monitor for suspicious token usage
- **Error tracking**: Track and alert on authentication failures

### 6. Production Considerations
```python
# Production server configuration
app = FastMCP(
    name="Production MCP Server",
    debug=False,  # Disable debug mode
    # Use environment-specific settings
    auth=AuthSettings(
        issuer_url=os.getenv('OKTA_ISSUER'),
        required_scopes=os.getenv('MCP_REQUIRED_SCOPES').split(),
        # Enable strict validation
        strict_validation=True
    )
)
```

### 7. Rate Limiting
```python
# Add rate limiting to prevent abuse
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.tool()
@limiter.limit("10/minute")  # 10 calls per minute
async def rate_limited_tool():
    """Tool with rate limiting."""
    pass
```

## Next Steps

After completing this setup:

1. **Production Deployment**:
   - Deploy server to cloud platform (AWS, Azure, GCP)
   - Configure proper DNS and SSL certificates
   - Set up monitoring and logging

2. **Advanced Features**:
   - Implement user-specific data access
   - Add role-based access control (RBAC)
   - Create custom scopes for different tool categories

3. **Integration**:
   - Connect to existing enterprise systems
   - Implement single sign-on (SSO) with corporate identity
   - Add multi-tenant support

4. **Monitoring**:
   - Set up application performance monitoring
   - Implement health checks and alerts
   - Add usage analytics and reporting

5. **Documentation**:
   - Create API documentation
   - Write user guides
   - Document deployment procedures

---

**🎉 Congratulations!** You now have a complete MCP system with Okta OAuth authentication. This setup provides a secure, production-ready foundation for building Model Context Protocol applications with enterprise-grade authentication.