#!/usr/bin/env python3
"""
Simple test to check if token exchange works with minimal configuration
"""
import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

async def test_token_exchange():
    """Test token exchange with manual authorization code"""
    
    # You'll need to get this manually from browser
    auth_code = input("Enter authorization code from browser: ")
    code_verifier = input("Enter code verifier: ")
    
    okta_domain = os.getenv('OKTA_DOMAIN')
    client_id = os.getenv('OKTA_CLIENT_ID')
    client_secret = os.getenv('OKTA_CLIENT_SECRET')
    
    token_url = f"{okta_domain}/oauth2/default/v1/token"
    
    # Try different approaches
    approaches = [
        # Approach 1: Basic auth, minimal data
        {
            "data": {
                "grant_type": "authorization_code",
                "code": auth_code,
                "redirect_uri": "http://localhost:3030/oauth/callback",
                "code_verifier": code_verifier
            },
            "auth": (client_id, client_secret),
            "name": "Basic Auth"
        },
        # Approach 2: Client credentials in body
        {
            "data": {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "code": auth_code,
                "redirect_uri": "http://localhost:3030/oauth/callback",
                "code_verifier": code_verifier
            },
            "auth": None,
            "name": "Client Credentials in Body"
        },
        # Approach 3: Both basic auth and client_id in body
        {
            "data": {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": auth_code,
                "redirect_uri": "http://localhost:3030/oauth/callback",
                "code_verifier": code_verifier
            },
            "auth": (client_id, client_secret),
            "name": "Both Basic Auth and Client ID"
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for approach in approaches:
            print(f"\n🧪 Testing {approach['name']}...")
            
            response = await client.post(
                token_url,
                data=approach["data"],
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                auth=approach["auth"]
            )
            
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
            
            if response.status_code == 200:
                print("✅ SUCCESS!")
                return
            else:
                print("❌ FAILED")

if __name__ == "__main__":
    asyncio.run(test_token_exchange())