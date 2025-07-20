from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import requests
import json
from typing import Dict, Any
from dotenv import load_dotenv
import os

app = FastAPI(title="Okta JWT Validator")
security = HTTPBearer()
load_dotenv()

# Configuration - set these environment variables
OKTA_DOMAIN = os.getenv("OKTA_DOMAIN")  # e.g., "your-domain.okta.com"
OKTA_AUDIENCE = os.getenv("OKTA_AUDIENCE", "api://default")


def get_okta_public_key(kid: str) -> str:
    """Fetch Okta's public key for JWT verification"""
    jwks_url = f"https://{OKTA_DOMAIN}/oauth2/default/v1/keys"
    response = requests.get(jwks_url)
    jwks = response.json()

    for key in jwks["keys"]:
        if key["kid"] == kid:
            # Convert JWK to PEM format
            from jwt.algorithms import RSAAlgorithm

            return str(RSAAlgorithm.from_jwk(key))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find appropriate key",
    )


def verify_jwt_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """Verify and decode the JWT token"""
    token = credentials.credentials

    try:
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]

        # Get public key
        public_key = get_okta_public_key(kid)

        # Verify and decode token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=OKTA_AUDIENCE,
            issuer=f"https://{OKTA_DOMAIN}/oauth2/default",
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}"
        )


@app.get("/")
async def validate_token(jwt_payload: Dict[str, Any] = Depends(verify_jwt_token)):
    """Validate JWT and return payload"""

    # Print JWT information to stdout
    print("=" * 50)
    print("JWT TOKEN INFORMATION:")
    print("=" * 50)
    print(json.dumps(jwt_payload, indent=2, default=str))
    print("=" * 50)

    # Return the same information in response with 200 status
    return jwt_payload


if __name__ == "__main__":
    import uvicorn

    # Check required environment variables
    if not OKTA_DOMAIN:
        print("ERROR: OKTA_DOMAIN environment variable is required")
        exit(1)

    print(f"Starting JWT validator with Okta domain: {OKTA_DOMAIN}")
    print("Send requests with: Authorization: Bearer <your-jwt-token>")

    uvicorn.run(app, host="0.0.0.0", port=8000)
