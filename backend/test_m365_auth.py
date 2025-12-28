#!/usr/bin/env python3
"""
Test M365 OAuth Device Code Flow
This script tests the authentication flow to diagnose issues.
"""

import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

CLIENT_ID = os.getenv("M365_CLIENT_ID", "")
TENANT_ID = os.getenv("M365_TENANT_ID", "common")

SCOPES = [
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/Mail.ReadWrite",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/User.Read",
    "offline_access"
]

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
DEVICE_CODE_URL = f"{AUTHORITY}/oauth2/v2.0/devicecode"
TOKEN_URL = f"{AUTHORITY}/oauth2/v2.0/token"

print("=" * 60)
print("M365 OAuth Device Code Flow Test")
print("=" * 60)
print(f"CLIENT_ID: {CLIENT_ID}")
print(f"TENANT_ID: {TENANT_ID}")
print(f"DEVICE_CODE_URL: {DEVICE_CODE_URL}")
print(f"TOKEN_URL: {TOKEN_URL}")
print()

# Step 1: Request device code
print("Step 1: Requesting device code...")
payload = {
    "client_id": CLIENT_ID,
    "scope": " ".join(SCOPES)
}

try:
    response = requests.post(DEVICE_CODE_URL, data=payload, timeout=10)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        data = response.json()
        print("✓ Device code received!")
        print(f"  User code: {data.get('user_code')}")
        print(f"  Verification URL: {data.get('verification_uri')}")
        print(f"  Device code: {data.get('device_code')[:20]}...")
        print()

        # Step 2: Test token request (will fail with authorization_pending)
        print("Step 2: Testing token request...")
        token_payload = {
            "client_id": CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": data.get("device_code")
        }

        token_response = requests.post(TOKEN_URL, data=token_payload, timeout=10)
        print(f"Status: {token_response.status_code}")

        token_data = token_response.json()
        print(f"Response: {json.dumps(token_data, indent=2)}")

        error = token_data.get("error")
        if error == "authorization_pending":
            print("\n✓ Token endpoint working correctly (authorization_pending is expected)")
        elif error == "invalid_client":
            print("\n✗ ERROR: invalid_client")
            print("This means:")
            print("  1. App may not be configured as a public client")
            print("  2. Client ID may not match the tenant")
            print("  3. 'Allow public client flows' may be disabled")
            print(f"\nFull error: {token_data.get('error_description')}")
        else:
            print(f"\n? Unexpected error: {error}")

    else:
        print(f"✗ Device code request failed!")
        print(f"Response: {response.text}")

except Exception as e:
    print(f"✗ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
