"""
MCP Server with Okta OAuth Integration
A FastMCP server that uses Okta for OAuth authentication.
"""

import os
import logging
import datetime
from typing import Any, Dict, List
from dotenv import load_dotenv

from mcp.server.fastmcp.server import FastMCP
from mcp.server.auth.settings import AuthSettings
from okta_token_verifier import OktaTokenVerifier
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
    required_scopes: List[str] = required_scopes_str.split() if required_scopes_str else []

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

    # @app.resource("user-info")
    # async def get_user_info() -> str:
    #     """Get information about the authenticated user."""
    #     # In a real implementation, you would extract user info from the token
    #     return "User information would be extracted from the Okta token"

    return app


def main() -> None:
    """Main entry point for the MCP server."""
    try:
        server = create_mcp_server()

        host = os.getenv("MCP_SERVER_HOST", "localhost")
        port_str = os.getenv("MCP_SERVER_PORT", "8001")
        port = int(port_str)

        logger.info(f"🚀 MCP Server with Okta Auth starting on {host}:{port}")
        logger.info(f"🔑 Using Okta issuer: {os.getenv('OKTA_ISSUER')}")
        scope_env = os.getenv('MCP_REQUIRED_SCOPES', 'mcp:access')
        logger.info(f"📋 Required scopes: {scope_env}")

        # Run the server
        server.run(transport="streamable-http")

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


if __name__ == "__main__":
    main()

