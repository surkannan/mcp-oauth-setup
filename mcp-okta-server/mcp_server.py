"""
MCP Server with Okta OAuth Integration
A FastMCP server that uses Okta for OAuth authentication.
"""

import os
import logging
import datetime
from typing import Any, Dict, List
from dotenv import load_dotenv
import requests
import time
from jose import jwt
from jose.constants import ALGORITHMS
import base64
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from mcp.server.fastmcp.server import FastMCP, Context
from mcp.server.auth.settings import AuthSettings
from okta_token_verifier import OktaTokenVerifier
from mcp.server.auth.middleware.auth_context import get_access_token as get_auth_access_token
from pydantic import AnyHttpUrl

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with Okta authentication."""

    # Get configuration from environment
    host = os.getenv("MCP_SERVER_HOST", "localhost")
    port_str = os.getenv("MCP_SERVER_PORT", "8001")
    port = int(port_str)
    server_url = os.getenv("MCP_SERVER_URL", f"http://{host}:{port}")
    okta_issuer = os.getenv("OKTA_ISSUER")
    required_scopes_str = os.getenv("MCP_REQUIRED_SCOPES", "mcp:access")
    required_scopes: List[str] = (
        required_scopes_str.split() if required_scopes_str else []
    )

    if not okta_issuer:
        raise ValueError("OKTA_ISSUER environment variable is required")

    # Create Okta token verifier
    token_verifier = OktaTokenVerifier()

    # Configure authentication settings
    auth_settings = AuthSettings(
        issuer_url=AnyHttpUrl(okta_issuer),
        required_scopes=required_scopes,
        resource_server_url=AnyHttpUrl(server_url),
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
    async def get_current_time() -> Dict[str, Any]:
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
            "message": "Hello from authenticated MCP server!",
        }

    @app.tool()
    async def calculate_square(number: float) -> Dict[str, Any]:
        """
        Calculate the square of a number.

        Args:
            number: The number to square

        Returns:
            Dictionary with the original number and its square
        """
        result = number**2
        return {
            "input": number,
            "square": result,
            "calculation": f"{number}² = {result}",
        }

    @app.tool()
    async def call_third_party_api() -> Dict[str, Any]:
        """
        Call a third-party API with an exchanged token.
        """
        # Get the access token from the context
        access_token_obj = get_auth_access_token()
        logger.info(f"Type of access_token_obj: {type(access_token_obj)}")
        logger.info(f"dir(access_token_obj): {dir(access_token_obj)}")
        if not access_token_obj:
            raise Exception("Access token not found in context")
        access_token = access_token_obj.token

        # Exchange the token
        logger.info(f"Received access token for exchange: {access_token}")
        exchanged_token = await exchange_token(access_token)

        # Call the third-party API
        api_url = os.getenv("THIRD_PARTY_API_URL")
        if not api_url:
            raise Exception("THIRD_PARTY_API_URL not set")

        headers = {"Authorization": f"Bearer {exchanged_token}"}
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()

        return response.json()

    # @app.resource("user-info")
    # async def get_user_info() -> str:
    #     """Get information about the authenticated user."""
    #     # In a real implementation, you would extract user info from the token
    #     return "User information would be extracted from the Okta token"

    return app


def get_access_token(request: Any) -> str:
    access_token = request.state.token.get("access_token")
    if not access_token:
        raise Exception("Access token not found in request state")
    return access_token


async def exchange_token(access_token: str) -> str:
    """Exchange the access token for a new token."""
    token_url = f"{os.getenv('OKTA_ISSUER')}/v1/token"

    client_id = os.getenv("OKTA_CLIENT_ID")
    if not client_id:
        raise Exception("OKTA_CLIENT_ID not set")

    client_secret = os.getenv("OKTA_CLIENT_SECRET")
    if not client_secret:
        raise Exception("OKTA_CLIENT_SECRET not set")

    thirdparty_scope = os.getenv("THIRDPARTY_OAUTH_SCOPE", "api:read")
    thirdparty_audience = os.getenv("THIRDPARTY_OAUTH_AUDIENCE")
    if not thirdparty_audience:
        raise Exception("THIRDPARTY_OAUTH_AUDIENCE not set")

    # Generate DPoP key
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    def urlsafe_b64encode_no_padding(data):
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')

    jwk = {
        "kty": "RSA",
        "n": urlsafe_b64encode_no_padding(public_numbers.n.to_bytes((public_numbers.n.bit_length() + 7) // 8, 'big')),
        "e": urlsafe_b64encode_no_padding(public_numbers.e.to_bytes((public_numbers.e.bit_length() + 7) // 8, 'big')),
    }

    def create_dpop_proof(nonce: str | None = None) -> str:
        dpop_header = {
            "typ": "dpop+jwt",
            "alg": ALGORITHMS.RS256,
            "jwk": jwk,
        }
        dpop_claims = {
            "jti": os.urandom(16).hex(),
            "htm": "POST",
            "htu": token_url,
            "iat": int(time.time()),
        }
        if nonce:
            dpop_claims["nonce"] = nonce
        return jwt.encode(dpop_claims, private_key, algorithm=ALGORITHMS.RS256, headers=dpop_header)

    headers = {"DPoP": create_dpop_proof()}

    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "subject_token": access_token,
        "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "scope": thirdparty_scope,
        "audience": thirdparty_audience,
    }

    response = requests.post(token_url, headers=headers, data=data, auth=(client_id, client_secret))

    if response.status_code == 400 and response.json().get("error") == "use_dpop_nonce":
        nonce = response.headers.get("DPoP-Nonce")
        if not nonce:
            raise Exception("DPoP nonce not found in response")
        headers["DPoP"] = create_dpop_proof(nonce)
        response = requests.post(token_url, headers=headers, data=data, auth=(client_id, client_secret))

    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Token exchange failed: {e}")
        logger.error(f"Response body: {response.text}")
        raise

    return response.json()["access_token"]


def main() -> None:
    """Main entry point for the MCP server."""
    try:
        server = create_mcp_server()

        host = os.getenv("MCP_SERVER_HOST", "localhost")
        port_str = os.getenv("MCP_SERVER_PORT", "8001")
        port = int(port_str)

        logger.info(f"🚀 MCP Server with Okta Auth starting on {host}:{port}")
        logger.info(f"🔑 Using Okta issuer: {os.getenv('OKTA_ISSUER')}")
        scope_env = os.getenv("MCP_REQUIRED_SCOPES", "mcp:access")
        logger.info(f"📋 Required scopes: {scope_env}")

        # Run the server
        server.run(transport="streamable-http")

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


if __name__ == "__main__":
    main()
