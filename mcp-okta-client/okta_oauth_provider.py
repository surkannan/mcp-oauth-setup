"""
Okta OAuth Client Provider for MCP
Handles OAuth flow with Okta authorization server.
"""

import os
import httpx
from mcp.client.auth import OAuthClientProvider, TokenStorage
from mcp.shared.auth import OAuthToken


class OktaOAuthProvider(OAuthClientProvider):
    """OAuth provider for Okta integration."""

    def __init__(self, storage: TokenStorage) -> None:
        self.storage = storage
        self.okta_domain = os.getenv("OKTA_DOMAIN")
        self.client_id = os.getenv("OKTA_CLIENT_ID")
        self.client_secret = os.getenv("OKTA_CLIENT_SECRET")
        self.okta_issuer = os.getenv("OKTA_ISSUER")
        self.mcp_scope = (
            f"openid profile offline_access {os.getenv('MCP_REQUIRED_SCOPES', '')}".strip()
        )
        self.redirect_uri = "http://localhost:3030/oauth/callback"

        if not all([self.okta_domain, self.client_id]):
            raise ValueError("Missing required Okta environment variables")

        if not self.okta_issuer:
            raise ValueError("OKTA_ISSUER environment variable is required")

    async def get_authorization_url(self, state: str, code_challenge: str) -> str:
        """Generate Okta authorization URL."""
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "response_type": "code",
            "scope": self.mcp_scope,
            "redirect_uri": self.redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        # Use OKTA_ISSUER environment variable to construct authorization URL
        auth_url = f"{self.okta_issuer}/v1/authorize"
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])

        # DEBUG: Log the complete authorization URL
        print(f"🔍 DEBUG: Using OKTA_ISSUER: {self.okta_issuer}")
        print(f"🔍 DEBUG: Using MCP_REQUIRED_SCOPES: {self.mcp_scope}")
        print(f"🔍 DEBUG: Generated authorization URL: {auth_url}?{query_string}")
        print(f"🔍 DEBUG: Authorization parameters: {params}")

        return f"{auth_url}?{query_string}"

    async def exchange_code_for_tokens(
        self, code: str, code_verifier: str
    ) -> OAuthToken:
        """Exchange authorization code for tokens."""

        # Use OKTA_ISSUER environment variable to construct token URL
        token_url = f"{self.okta_issuer}/v1/token"

        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "code_verifier": code_verifier,
        }

        print(f"🔍 Debug: Token URL: {token_url}")
        print(f"🔍 Debug: Request data: {data}")

        # Try without Basic Auth first, using client credentials in body
        if self.client_id:
            data["client_id"] = self.client_id
        if self.client_secret:
            data["client_secret"] = self.client_secret

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            print(f"🔍 Debug: Response status: {response.status_code}")
            print(f"🔍 Debug: Response headers: {dict(response.headers)}")
            print(f"🔍 Debug: Response text: {response.text}")

            if response.status_code != 200:
                raise Exception(
                    f"Token exchange failed: {response.status_code} {response.text}"
                )

            token_data = response.json()

            return OAuthToken(
                access_token=token_data["access_token"],
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                refresh_token=token_data.get("refresh_token"),
                scope=token_data.get("scope", ""),
            )
