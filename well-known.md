# MCP Server .well-known Endpoints

## Overview

This document details the `.well-known` endpoints exposed by the FastMCP server with Okta OAuth authentication implementation.

## Server Configuration

The MCP server is configured as an **OAuth 2.0 Resource Server** (not an Authorization Server), which determines what endpoints it exposes.

- **Authorization Server**: Okta (`https://dev-77377857.okta.com/oauth2/auspgx6ebo33Ebh3k5d7`)
- **Resource Server**: MCP Server (`http://localhost:8001`)
- **Protected Resources**: MCP tools requiring `mcp:access` scope

## Supported .well-known Endpoints

### ✅ `/.well-known/oauth-protected-resource` (RFC 9728)

**Endpoint**: `http://localhost:8001/.well-known/oauth-protected-resource`

**Purpose**: Provides metadata about the protected resource server per RFC 9728 (OAuth 2.0 Protected Resource Metadata).

**Test Command**:
```bash
curl -H "MCP-Protocol-Version: 2025-06-18" \
     http://localhost:8001/.well-known/oauth-protected-resource
```

**Response**:
```json
{
  "resource": "http://localhost:8001/mcp",
  "authorization_servers": ["https://dev-77377857.okta.com/oauth2/auspgx6ebo33Ebh3k5d7"],
  "scopes_supported": ["mcp:access"],
  "bearer_methods_supported": ["header"]
}
```

**Response Fields**:
- `resource`: The URI identifying this protected resource
- `authorization_servers`: Array of authorization servers that can issue tokens for this resource
- `scopes_supported`: OAuth scopes supported by this resource server
- `bearer_methods_supported`: Methods for presenting bearer tokens (header, body, query)

### ❌ `/.well-known/oauth-authorization-server` (RFC 8414)

**Status**: **404 Not Found**

**Why**: This endpoint is **not exposed** because the MCP server is configured as a Resource Server, not an Authorization Server.

**Authorization Server Metadata**: Available at Okta instead:
```
https://dev-77377857.okta.com/oauth2/auspgx6ebo33Ebh3k5d7/.well-known/oauth-authorization-server
```

## Standards Compliance

The implementation follows these OAuth 2.0 specifications:

### RFC 9728 - OAuth 2.0 Protected Resource Metadata
- ✅ Exposes protected resource metadata
- ✅ Indicates supported authorization servers
- ✅ Lists supported scopes and bearer token methods

### RFC 8707 - OAuth 2.0 Resource Indicators
- ✅ Supports resource-specific access tokens
- ✅ Enables fine-grained access control per resource server
- ✅ Validates resource parameter in token requests

### RFC 7636 - PKCE (Client-side)
- ✅ Client implements PKCE flow for security
- ✅ Uses SHA256 code challenge method
- ✅ Prevents authorization code interception attacks

### RFC 6750 - Bearer Token Usage
- ✅ Accepts bearer tokens in Authorization header
- ✅ Validates token format and presence
- ✅ Returns appropriate error responses for invalid tokens

## Security Features

### Token Validation
- **Introspection**: Validates tokens using Okta's introspection endpoint
- **Scope Validation**: Ensures tokens contain required `mcp:access` scope
- **Expiration Checking**: Validates token expiration times
- **Active Status**: Confirms tokens are active in the authorization server

### Authentication Flow
1. Client redirects user to Okta authorization endpoint
2. User authenticates with Okta
3. Okta redirects back with authorization code
4. Client exchanges code for access token using PKCE
5. Client presents bearer token to MCP server
6. Server validates token via Okta introspection
7. Server grants access to protected MCP tools

## Configuration Details

### Environment Variables
```bash
# Okta Configuration
OKTA_DOMAIN=https://dev-77377857.okta.com
OKTA_CLIENT_ID=0oapgjoe6pBUp7mmP5d7
OKTA_CLIENT_SECRET=your_client_secret
OKTA_AUDIENCE=api://mcp
OKTA_ISSUER=https://dev-77377857.okta.com/oauth2/auspgx6ebo33Ebh3k5d7

# Server Configuration
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8001
MCP_SERVER_URL=http://localhost:8001
MCP_REQUIRED_SCOPES=mcp:access
```

### AuthSettings Configuration
```python
auth_settings = AuthSettings(
    issuer_url=AnyHttpUrl(okta_issuer),
    required_scopes=required_scopes,
    resource_server_url=AnyHttpUrl(server_url),
)
```

## Testing and Verification

### Test Protected Resource Metadata
```bash
# Should return metadata JSON
curl -H "MCP-Protocol-Version: 2025-06-18" \
     http://localhost:8001/.well-known/oauth-protected-resource
```

### Test Authorization Server Metadata (at Okta)
```bash
# Should return Okta's authorization server metadata
curl https://dev-77377857.okta.com/oauth2/auspgx6ebo33Ebh3k5d7/.well-known/oauth-authorization-server
```

### Test Protected Tool Access
```bash
# Should require valid bearer token
curl -H "Authorization: Bearer your_access_token" \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_current_time","arguments":{}}}' \
     http://localhost:8001/mcp
```

## Troubleshooting

### Common Issues

1. **404 on /.well-known/oauth-authorization-server**
   - **Expected**: MCP server is a resource server, not an authorization server
   - **Solution**: Use Okta's authorization server endpoint instead

2. **401/403 on MCP tool calls**
   - **Check**: Token validity and scope presence
   - **Verify**: Token contains `mcp:access` scope
   - **Debug**: Check server logs for token validation details

3. **Token validation failures**
   - **Verify**: Client credentials for introspection are correct
   - **Check**: Network connectivity to Okta introspection endpoint
   - **Confirm**: Token is active and not expired

### Debug Logging
The server includes detailed logging for token verification:
```
INFO:okta_token_verifier:Token verified for user: user@example.com, client: 0oapgjoe6pBUp7mmP5d7
INFO:okta_token_verifier:Token scopes: ['openid', 'profile', 'mcp:access']
```

## Architecture Summary

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Client    │◄──►│ Okta (OAuth AS) │◄──►│  MCP Server     │
│                 │    │                 │    │ (Resource Server│
│ - PKCE flow     │    │ - Issues tokens │    │ - Validates     │
│ - Bearer tokens │    │ - User auth     │    │   tokens        │
│ - Tool calls    │    │ - .well-known/  │    │ - .well-known/  │
│                 │    │   oauth-authz   │    │   protected-res │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

This implementation provides enterprise-grade OAuth 2.0 authentication for MCP servers with proper standards compliance and security best practices.