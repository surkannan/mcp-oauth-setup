# Todo

- [x] Add a new environment variable for the third-party API URL.
- [x] Implement a new tool that performs the OAuth token exchange and calls the third-party API.
- [x] The token exchange will require the `requests` library, so I'll add it to the `pyproject.toml` and install it.
- [ ] Testing: I'll add instructions on how to test the new tool.

# Review

I have added a new tool to the MCP server that calls a third-party API. This tool first exchanges the OIDC access token for a new token using OAuth token exchange, and then uses the new token to authenticate with the third-party API. I have also added the necessary environment variables and dependencies.

## Testing

To test the new tool, you will need to:

1.  Set the `THIRD_PARTY_API_URL` environment variable to the URL of the third-party API.
2.  Set the `OKTA_TOKEN_URL`, `OKTA_CLIENT_ID`, and `OKTA_CLIENT_SECRET` environment variables.
3.  Run the MCP server.
4.  Use the MCP client to call the `call_third_party_api` tool.