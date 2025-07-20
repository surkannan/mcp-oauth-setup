"""
Okta Token Verifier for MCP Server
Validates JWT tokens issued by Okta using token introspection.
"""

import os
import logging
from typing import Optional, Any, Dict
import httpx
from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class OktaTokenVerifier(TokenVerifier):
    """Token verifier that validates tokens using Okta's introspection endpoint."""
    
    def __init__(self) -> None:
        self.okta_domain = os.getenv('OKTA_DOMAIN')
        self.okta_issuer = os.getenv('OKTA_ISSUER')
        self.client_id = os.getenv('OKTA_CLIENT_ID')
        self.client_secret = os.getenv('OKTA_CLIENT_SECRET')
        
        if not self.okta_domain:
            raise ValueError("OKTA_DOMAIN environment variable is required")
            
        self.introspection_url = f"{self.okta_issuer}/v1/introspect"
        
        if not all([self.okta_domain, self.okta_issuer, self.client_id, self.client_secret]):
            raise ValueError("Missing required Okta environment variables")
    
    async def verify_token(self, token: str) -> Optional[AccessToken]:
        """Verify token using Okta's introspection endpoint."""
        
        async with httpx.AsyncClient() as client:
            try:
                # Call Okta introspection endpoint
                if not self.client_id or not self.client_secret:
                    logger.error("Missing client credentials for token introspection")
                    return None
                    
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
                
                token_data: Dict[str, Any] = response.json()
                
                # Check if token is active
                if not token_data.get("active", False):
                    logger.debug("Token is not active")
                    return None
                
                # Extract token information
                scope_str = token_data.get("scope", "")
                scopes = scope_str.split() if isinstance(scope_str, str) else []
                client_id = token_data.get("client_id", "unknown")
                expires_at = token_data.get("exp")
                username = token_data.get("username") or token_data.get("sub")
                
                logger.info(f"Token verified for user: {username}, client: {client_id}")
                logger.info(f"Token scopes: {scopes}")
                logger.info(f"Full token data: {token_data}")
                
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
