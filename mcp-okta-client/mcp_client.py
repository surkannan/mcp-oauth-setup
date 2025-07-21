"""
MCP Client with Okta OAuth Integration
Connects to MCP server using Okta authentication.
"""

import os
import asyncio
import secrets
import hashlib
import base64
import logging
from datetime import timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time
from typing import Optional, Tuple, Any
import httpx
from dotenv import load_dotenv

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.auth import OAuthToken, OAuthClientInformationFull
from okta_oauth_provider import OktaOAuthProvider

# Load environment
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)


def create_httpx_client_factory(
    verify_ssl: bool = True, ca_bundle_path: Optional[str] = None
):
    """Create HTTPX client factory with configurable SSL verification and CA bundle."""

    def client_factory(
        headers: dict[str, str] | None = None,
        timeout: httpx.Timeout | None = None,
        auth: httpx.Auth | None = None,
    ) -> httpx.AsyncClient:
        """Create HTTPX AsyncClient with optional SSL verification and CA bundle."""

        # Determine SSL verification setting
        if ca_bundle_path:
            # Use custom CA bundle for self-signed certificates
            verify_value = ca_bundle_path
            logger.info(f"🔒 Using custom CA bundle: {ca_bundle_path}")
        elif verify_ssl:
            # Use default SSL verification
            verify_value = True
        else:
            # Disable SSL verification entirely
            verify_value = False
            logger.warning(
                "🚨 SSL verification is disabled. This is insecure and should only be used in testing environments."
            )

        kwargs = {
            "follow_redirects": True,
            "verify": verify_value,  # Can be True, False, or path to CA bundle
        }

        if timeout is None:
            kwargs["timeout"] = httpx.Timeout(30.0)
        else:
            kwargs["timeout"] = timeout

        if headers is not None:
            kwargs["headers"] = headers

        if auth is not None:
            kwargs["auth"] = auth

        return httpx.AsyncClient(**kwargs)

    return client_factory


class CallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def do_GET(self) -> None:
        """Handle OAuth callback."""
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # DEBUG: Log all callback URL details
        print(f"🔍 DEBUG: Full callback URL: {self.path}")
        print(f"🔍 DEBUG: Parsed URL: {parsed_url}")
        print(f"🔍 DEBUG: Query string: {parsed_url.query}")
        print(f"🔍 DEBUG: All query parameters: {query_params}")
        print(f"🔍 DEBUG: Available keys: {list(query_params.keys())}")

        # DEBUG: Check for specific OAuth parameters
        print(f"🔍 DEBUG: Looking for 'code' parameter...")
        print(f"🔍 DEBUG: 'code' present: {'code' in query_params}")
        if "code" in query_params:
            print(f"🔍 DEBUG: Authorization code: {query_params['code'][0]}")
        if "state" in query_params:
            print(f"🔍 DEBUG: State parameter: {query_params['state'][0]}")
        if "error" in query_params:
            print(f"🔍 DEBUG: Error parameter: {query_params['error'][0]}")
            if "error_description" in query_params:
                print(
                    f"🔍 DEBUG: Error description: {query_params['error_description'][0]}"
                )

        if "code" in query_params:
            self.server.auth_code = query_params["code"][0]  # type: ignore
            self.server.state = query_params.get("state", [None])[0]  # type: ignore

            self.send_response(200)
            self.send_header("Content-type", "text/html")
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
            # DEBUG: Log when callback doesn't contain expected parameters
            print(f"🔍 DEBUG: No 'code' parameter found in callback")
            print(f"🔍 DEBUG: Available parameters: {list(query_params.keys())}")
            if query_params:
                for key, values in query_params.items():
                    print(f"🔍 DEBUG: {key} = {values}")

            self.send_response(400)
            self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress logging."""
        pass


class InMemoryTokenStorage:
    """Simple in-memory token storage."""

    def __init__(self) -> None:
        self._tokens: Optional[OAuthToken] = None
        self._client_info: Optional[OAuthClientInformationFull] = None

    async def get_tokens(self) -> Optional[OAuthToken]:
        return self._tokens

    async def set_tokens(self, tokens: OAuthToken) -> None:
        self._tokens = tokens

    async def get_client_info(self) -> Optional[OAuthClientInformationFull]:
        return self._client_info

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        self._client_info = client_info


def generate_pkce_pair() -> Tuple[str, str]:
    """Generate PKCE code verifier and challenge."""
    code_verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    )
    code_challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode("utf-8")).digest())
        .decode("utf-8")
        .rstrip("=")
    )
    return code_verifier, code_challenge


async def start_callback_server(port: int = 3030) -> HTTPServer:
    """Start HTTP server for OAuth callback."""
    server = HTTPServer(("localhost", port), CallbackHandler)
    server.auth_code = None  # type: ignore
    server.state = None  # type: ignore

    # Run server in background thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    return server


async def wait_for_callback(server: HTTPServer, timeout: int = 300) -> Tuple[str, str]:
    """Wait for OAuth callback."""
    start_time = time.time()
    print(f"🔍 DEBUG: Starting to wait for callback...")

    while time.time() - start_time < timeout:
        # DEBUG: Log waiting status
        if hasattr(server, "auth_code"):
            # print(f"🔍 DEBUG: Checking for auth_code... Current value: {getattr(server, 'auth_code', 'NOT_SET')}")
            pass

        if hasattr(server, "auth_code") and server.auth_code:  # type: ignore
            print(f"🔍 DEBUG: Auth code received: {server.auth_code}")
            print(f"🔍 DEBUG: State received: {getattr(server, 'state', 'NOT_SET')}")
            return server.auth_code, server.state  # type: ignore
        await asyncio.sleep(0.1)

    raise TimeoutError("Timeout waiting for OAuth callback")


async def authenticate_with_okta() -> OAuthToken:
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

        # DEBUG: Log OAuth flow parameters
        print(f"🔍 DEBUG: Generated state: {state}")
        print(f"🔍 DEBUG: Generated code_verifier: {code_verifier}")
        print(f"🔍 DEBUG: Generated code_challenge: {code_challenge}")
        print(f"🔍 DEBUG: Callback server listening on: http://localhost:3030")

        print(f"🌐 Opening browser for authentication...")
        print(f"📋 If browser doesn't open, visit: {auth_url}")

        # Import webbrowser here to avoid unused import
        import webbrowser

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


async def main() -> None:
    """Main client application."""
    print("🚀 MCP Client with Okta OAuth")

    # Server configuration
    server_url = os.getenv("MCP_SERVER_URL", "http://localhost:8001/mcp")
    verify_ssl = os.getenv("VERIFY_SSL", "true").lower() != "false"
    ca_bundle_path = os.getenv(
        "CA_BUNDLE_PATH"
    )  # Path to custom CA bundle for self-signed certificates

    try:
        # Authenticate with Okta
        tokens = await authenticate_with_okta()

        print(f"🔗 Connecting to MCP server: {server_url}")
        if ca_bundle_path:
            print(f"🔒 Using CA bundle: {ca_bundle_path}")
        elif not verify_ssl:
            print("🚨 SSL verification is disabled")

        # Create authenticated HTTP client
        headers = {"Authorization": f"Bearer {tokens.access_token}"}

        # Connect to MCP server with SSL configuration
        async with streamablehttp_client(
            url=server_url,
            headers=headers,
            timeout=timedelta(seconds=30),
            httpx_client_factory=create_httpx_client_factory(
                verify_ssl=verify_ssl, ca_bundle_path=ca_bundle_path
            ),
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
                if time_result.content and hasattr(time_result.content[0], "text"):
                    print(f"   Result: {time_result.content[0].text}")  # type: ignore
                else:
                    print(f"   Result: {time_result.content}")

                # Test calculate_square
                print("🔢 Calculating square of 7...")
                square_result = await session.call_tool(
                    "calculate_square", {"number": 7}
                )
                if square_result.content and hasattr(square_result.content[0], "text"):
                    print(f"   Result: {square_result.content[0].text}")  # type: ignore
                else:
                    print(f"   Result: {square_result.content}")

                # Test call_third_party_api
                print("\n📞 Calling third-party API...")
                api_result = await session.call_tool("call_third_party_api", {})
                if api_result.content and hasattr(api_result.content[0], "text"):
                    print(f"   Result: {api_result.content[0].text}")
                else:
                    print(f"   Result: {api_result.content}")

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
