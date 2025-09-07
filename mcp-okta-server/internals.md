# Internals: OAuth Verification and Token Delegation Flow

This document provides a detailed technical explanation of how OAuth verification and token delegation work within the MCP Okta server.

## Architecture Overview

The server operates as an OAuth 2.0 Resource Server with the following key components:

- **FastMCP Framework**: Provides the MCP protocol implementation with OAuth middleware
- **OktaTokenVerifier**: Custom token verifier using Okta's introspection endpoint
- **Token Exchange Engine**: Implements RFC 8693 token exchange with DPoP (RFC 9449)

## Complete Request Flow

### 1. Client Request with OAuth Token

```
Client → MCP Server
POST /tools/invoke
Headers:
  Authorization: Bearer <okta_access_token>
  MCP-Protocol-Version: 2025-06-18
Body: { tool: "get_current_time", arguments: {} }
```

### 2. Authentication Middleware Flow

The FastMCP framework intercepts the request before it reaches any tool:

#### Step 2a: Token Extraction
- FastMCP extracts Bearer token from `Authorization` header
- Token is passed to the configured `token_verifier` (OktaTokenVerifier instance)

#### Step 2b: Token Verification (okta_token_verifier.py:32-82)
```python
async def verify_token(self, token: str) -> Optional[AccessToken]:
```

**Verification Process:**
1. **Okta Introspection Call**: POST to `{OKTA_ISSUER}/v1/introspect`
   - Uses client credentials authentication (`OKTA_CLIENT_ID` + `OKTA_CLIENT_SECRET`)
   - Sends token with `token_type_hint: "access_token"`

2. **Response Processing**:
   - Checks `active: true` in response
   - Extracts scopes, client_id, expiration, username/subject
   - Returns `AccessToken` object or `None` if invalid

3. **Scope Validation**: FastMCP validates required scopes against `MCP_REQUIRED_SCOPES`

#### Step 2c: Context Setup
If verification succeeds:
- FastMCP stores `AccessToken` in request context
- Token becomes available via `get_auth_access_token()` in tool implementations

### 3. Tool Execution

For simple tools like `get_current_time()` and `calculate_square()`:
- Direct execution with authenticated context
- No additional token operations needed

## Token Exchange Flow (Third-Party API Calls)

For the `call_third_party_api()` tool, a more complex flow occurs:

### Step 1: Original Token Retrieval
```python
access_token_obj = get_auth_access_token()  # mcp_server.py:113
access_token = access_token_obj.token
```

### Step 2: Token Exchange (RFC 8693) - mcp_server.py:151-225

The exchange implements OAuth 2.0 Token Exchange with DPoP:

#### 2a: DPoP Key Generation
```python
# Generate ephemeral RSA key pair
private_key = rsa.generate_private_key(
    public_exponent=65537, 
    key_size=2048, 
    backend=default_backend()
)
```

#### 2b: JWK Creation
Creates JSON Web Key from public key components:
```python
jwk = {
    "kty": "RSA",
    "n": urlsafe_b64encode_no_padding(public_key_modulus),
    "e": urlsafe_b64encode_no_padding(public_key_exponent),
}
```

#### 2c: DPoP Proof Generation
```python
def create_dpop_proof(nonce: str | None = None) -> str:
    dpop_header = {
        "typ": "dpop+jwt",
        "alg": "RS256",
        "jwk": jwk,  # Embed public key
    }
    dpop_claims = {
        "jti": os.urandom(16).hex(),  # Unique identifier
        "htm": "POST",                 # HTTP method
        "htu": token_url,             # Target URL
        "iat": int(time.time()),      # Issued at
        # "nonce": nonce (if provided by server)
    }
```

#### 2d: Token Exchange Request
```
POST {OKTA_ISSUER}/v1/token
Headers:
  Authorization: Basic {client_credentials}
  DPoP: {dpop_proof_jwt}
Body:
  grant_type: urn:ietf:params:oauth:grant-type:token-exchange
  subject_token_type: urn:ietf:params:oauth:token-type:access_token
  subject_token: {original_okta_token}
  requested_token_type: urn:ietf:params:oauth:token-type:access_token
  scope: {THIRDPARTY_OAUTH_SCOPE}
  audience: {THIRDPARTY_OAUTH_AUDIENCE}
```

#### 2e: DPoP Nonce Handling
If server responds with `use_dpop_nonce` error:
1. Extract nonce from `DPoP-Nonce` response header
2. Regenerate DPoP proof with nonce included
3. Retry the token exchange request

### Step 3: Third-Party API Call
```python
headers = {"Authorization": f"Bearer {exchanged_token}"}
response = requests.get(api_url, headers=headers)
```

## Security Features

### Token Introspection Benefits
- **Real-time validation**: Always checks current token status with Okta
- **Revocation awareness**: Immediately detects revoked tokens
- **Scope verification**: Validates fine-grained permissions

### DPoP (Demonstration of Proof-of-Possession)
- **Replay protection**: Each proof JWT has unique `jti` and timestamp
- **Key binding**: Exchanged token is bound to the ephemeral key pair
- **Nonce support**: Handles server-provided nonces for additional security

### Token Exchange Security
- **Limited scope**: Exchanged tokens have restricted `THIRDPARTY_OAUTH_SCOPE`
- **Audience restriction**: Tokens are bound to specific `THIRDPARTY_OAUTH_AUDIENCE`
- **Ephemeral keys**: Fresh key pair per exchange operation

## Error Handling

### Token Verification Failures
- Invalid/expired tokens → HTTP 401 Unauthorized
- Insufficient scopes → HTTP 403 Forbidden
- Network errors → Logged and treated as invalid token

### Token Exchange Failures
- Missing environment variables → Exception raised
- DPoP nonce errors → Automatic retry with nonce
- HTTP errors → Detailed logging with response body

## Key Classes and Methods

### OktaTokenVerifier
- `verify_token(token: str) -> Optional[AccessToken]`
- Uses async httpx client for Okta introspection
- Returns structured AccessToken with scopes and metadata

### FastMCP Integration Points
- `token_verifier`: Custom verifier instance
- `auth`: AuthSettings with issuer URL and required scopes
- `get_auth_access_token()`: Context access to verified token

### Token Exchange Functions
- `exchange_token(access_token: str) -> str`: Main exchange logic
- `create_dpop_proof(nonce)`: DPoP proof generation
- `urlsafe_b64encode_no_padding()`: JWK encoding helper

## Configuration Dependencies

The system requires careful environment configuration:

**Okta Integration:**
- `OKTA_DOMAIN`, `OKTA_ISSUER`: Okta tenant configuration
- `OKTA_CLIENT_ID`, `OKTA_CLIENT_SECRET`: Service client credentials

**Server Configuration:**
- `MCP_SERVER_URL`: Resource server identifier
- `MCP_REQUIRED_SCOPES`: Token scope requirements

**Token Exchange:**
- `THIRDPARTY_OAUTH_SCOPE`: Restricted scope for exchanged tokens  
- `THIRDPARTY_OAUTH_AUDIENCE`: Target audience for exchanged tokens
- `THIRD_PARTY_API_URL`: Protected third-party endpoint

This architecture provides a secure, standards-compliant OAuth 2.0 integration with comprehensive token validation and delegation capabilities.