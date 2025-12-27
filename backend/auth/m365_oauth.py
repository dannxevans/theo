"""
Microsoft 365 OAuth 2.0 Device Code Flow Implementation

This module handles authentication with Microsoft 365 using the OAuth 2.0
Device Code Flow, which is ideal for devices without a browser or with
limited input capabilities.

Flow:
1. Request device code from Microsoft
2. Display user code and verification URL to user
3. User authenticates in browser on another device
4. Poll Microsoft token endpoint until user completes authentication
5. Receive and store access + refresh tokens

Reference: https://learn.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-device-code
"""

import requests
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging
import os

class M365OAuth:
    """
    Microsoft 365 OAuth 2.0 Device Code Flow handler.

    Configuration required in .env:
    - M365_CLIENT_ID: Azure AD application client ID
    - M365_TENANT_ID: Azure AD tenant ID (or 'common' for multi-tenant)
    """

    # Azure AD app credentials (loaded from environment)
    CLIENT_ID = os.getenv("M365_CLIENT_ID", "")
    TENANT_ID = os.getenv("M365_TENANT_ID", "common")

    # OAuth scopes required for calendar and email access
    SCOPES = [
        "https://graph.microsoft.com/Calendars.ReadWrite",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/Mail.Send",
        "https://graph.microsoft.com/User.Read",
        "offline_access"  # Required for refresh tokens
    ]

    # Microsoft identity platform endpoints
    AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
    DEVICE_CODE_URL = f"{AUTHORITY}/oauth2/v2.0/devicecode"
    TOKEN_URL = f"{AUTHORITY}/oauth2/v2.0/token"

    @classmethod
    def initiate_device_flow(cls) -> Dict:
        """
        Step 1: Initiate device code flow.

        Returns device code information to display to user:
        {
            "user_code": "ABCD1234",
            "device_code": "...",
            "verification_url": "https://microsoft.com/devicelogin",
            "expires_in": 900,
            "interval": 5,
            "message": "To sign in, use a web browser to open..."
        }

        Raises:
            ValueError: If CLIENT_ID is not configured
            requests.RequestException: If API call fails
        """
        if not cls.CLIENT_ID:
            raise ValueError(
                "M365_CLIENT_ID not configured. "
                "Please set M365_CLIENT_ID in your .env file. "
                "See docs for Azure AD app setup instructions."
            )

        payload = {
            "client_id": cls.CLIENT_ID,
            "scope": " ".join(cls.SCOPES)
        }

        logging.info("[M365_OAUTH] Initiating device code flow...")

        try:
            response = requests.post(cls.DEVICE_CODE_URL, data=payload, timeout=10)
            response.raise_for_status()

            data = response.json()

            logging.info(f"[M365_OAUTH] Device code received: {data.get('user_code')}")

            return {
                "user_code": data["user_code"],
                "device_code": data["device_code"],
                "verification_url": data["verification_uri"],
                "expires_in": data["expires_in"],
                "interval": data["interval"],
                "message": data["message"]
            }

        except requests.RequestException as e:
            logging.error(f"[M365_OAUTH] Failed to initiate device flow: {e}")
            raise

    @classmethod
    def poll_for_token(cls, device_code: str, interval: int = 5,
                       max_attempts: int = 60) -> Optional[Dict]:
        """
        Step 2: Poll for access token after user authenticates.

        This method polls the Microsoft token endpoint at regular intervals
        until the user completes authentication in their browser.

        Args:
            device_code: Device code from initiate_device_flow()
            interval: Polling interval in seconds (from device flow response)
            max_attempts: Maximum number of polling attempts (default: 60 = 5 minutes)

        Returns:
            Token data if successful:
            {
                "access_token": "...",
                "refresh_token": "...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": "...",
                "expires_at": datetime object
            }

            None if:
            - User declined authorization
            - Device code expired
            - Polling timeout reached

        Raises:
            ValueError: If CLIENT_ID is not configured
        """
        if not cls.CLIENT_ID:
            raise ValueError("M365_CLIENT_ID not configured")

        import time

        payload = {
            "client_id": cls.CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code
        }

        logging.info("[M365_OAUTH] Starting token polling...")
        attempts = 0

        while attempts < max_attempts:
            try:
                response = requests.post(cls.TOKEN_URL, data=payload, timeout=10)

                if response.status_code == 200:
                    # Success! User completed authentication
                    data = response.json()

                    logging.info("[M365_OAUTH] ✓ Authentication successful!")

                    return {
                        "access_token": data["access_token"],
                        "refresh_token": data["refresh_token"],
                        "token_type": data["token_type"],
                        "expires_in": data["expires_in"],
                        "scope": data["scope"],
                        "expires_at": datetime.utcnow() + timedelta(seconds=data["expires_in"])
                    }

                # Check error response
                error_data = response.json()
                error = error_data.get("error")

                if error == "authorization_pending":
                    # User hasn't completed auth yet, keep polling
                    logging.debug(f"[M365_OAUTH] Polling attempt {attempts + 1}/{max_attempts}...")
                    time.sleep(interval)
                    attempts += 1
                    continue

                elif error == "authorization_declined":
                    logging.warning("[M365_OAUTH] User declined authorization")
                    return None

                elif error == "expired_token":
                    logging.warning("[M365_OAUTH] Device code expired")
                    return None

                elif error == "invalid_grant":
                    logging.error("[M365_OAUTH] Invalid grant - device code may be invalid")
                    return None

                else:
                    logging.error(f"[M365_OAUTH] Unexpected error: {error}")
                    error_description = error_data.get("error_description", "")
                    logging.error(f"[M365_OAUTH] Error description: {error_description}")
                    return None

            except requests.RequestException as e:
                logging.error(f"[M365_OAUTH] Polling request failed: {e}")
                time.sleep(interval)
                attempts += 1
                continue

        logging.warning("[M365_OAUTH] Polling timeout reached")
        return None

    @classmethod
    def refresh_access_token(cls, refresh_token: str) -> Optional[Dict]:
        """
        Refresh an expired access token using refresh token.

        This should be called when the access token expires (typically after 1 hour).
        The refresh token is long-lived and can be used multiple times.

        Args:
            refresh_token: Refresh token from previous authentication

        Returns:
            New token data if successful:
            {
                "access_token": "...",
                "refresh_token": "..." (may be same or rotated),
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": datetime object
            }

            None if refresh fails (user needs to re-authenticate)

        Raises:
            ValueError: If CLIENT_ID is not configured
        """
        if not cls.CLIENT_ID:
            raise ValueError("M365_CLIENT_ID not configured")

        payload = {
            "client_id": cls.CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": " ".join(cls.SCOPES)
        }

        logging.info("[M365_OAUTH] Refreshing access token...")

        try:
            response = requests.post(cls.TOKEN_URL, data=payload, timeout=10)

            if response.status_code == 200:
                data = response.json()

                logging.info("[M365_OAUTH] ✓ Token refreshed successfully")

                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", refresh_token),  # May or may not rotate
                    "token_type": data["token_type"],
                    "expires_in": data["expires_in"],
                    "expires_at": datetime.utcnow() + timedelta(seconds=data["expires_in"])
                }
            else:
                error_data = response.json()
                error = error_data.get("error")
                error_description = error_data.get("error_description", "")

                logging.error(f"[M365_OAUTH] Token refresh failed: {error}")
                logging.error(f"[M365_OAUTH] Error description: {error_description}")

                return None

        except requests.RequestException as e:
            logging.error(f"[M365_OAUTH] Token refresh request failed: {e}")
            return None

    @classmethod
    def is_configured(cls) -> bool:
        """
        Check if M365 OAuth is properly configured.

        Returns:
            True if CLIENT_ID is set, False otherwise
        """
        return bool(cls.CLIENT_ID)

    @classmethod
    def get_configuration_instructions(cls) -> str:
        """
        Get instructions for configuring M365 OAuth.

        Returns:
            Multi-line string with setup instructions
        """
        return """
To configure Microsoft 365 integration:

1. Register an Azure AD application:
   - Go to https://portal.azure.com
   - Navigate to Azure Active Directory → App registrations
   - Click "New registration"
   - Name: "THEO Personal AI Agent"
   - Supported account types: "Accounts in any organizational directory and personal Microsoft accounts"
   - Click "Register"

2. Configure API permissions:
   - In your app, go to "API permissions"
   - Click "Add a permission" → "Microsoft Graph" → "Delegated permissions"
   - Add these permissions:
     * Calendars.ReadWrite
     * Mail.ReadWrite
     * Mail.Send
     * User.Read
     * offline_access
   - Click "Grant admin consent" (if you're an admin)

3. Get your Client ID:
   - In your app overview, copy the "Application (client) ID"
   - Add to your .env file:
     M365_CLIENT_ID=your-client-id-here
     M365_TENANT_ID=common

4. Configure platform:
   - Go to "Authentication" → "Add a platform" → "Mobile and desktop applications"
   - Check "https://login.microsoftonline.com/common/oauth2/nativeclient"
   - Save

That's it! THEO can now connect to your M365 account.
"""


# Helper function for testing
def test_oauth_flow():
    """
    Test the OAuth flow interactively.
    Run with: python3 -m auth.m365_oauth
    """
    import time

    print("=" * 60)
    print("M365 OAuth Device Flow Test")
    print("=" * 60)

    if not M365OAuth.is_configured():
        print("\n❌ M365 OAuth not configured!")
        print(M365OAuth.get_configuration_instructions())
        return

    print("\n✓ M365 OAuth is configured")
    print(f"  Client ID: {M365OAuth.CLIENT_ID[:8]}...")
    print(f"  Tenant ID: {M365OAuth.TENANT_ID}")

    # Step 1: Initiate device flow
    print("\n[Step 1] Initiating device flow...")
    try:
        device_info = M365OAuth.initiate_device_flow()
    except Exception as e:
        print(f"❌ Failed: {e}")
        return

    print(f"\n✓ Device flow initiated!")
    print(f"\n{device_info['message']}\n")
    print(f"User Code: {device_info['user_code']}")
    print(f"Verification URL: {device_info['verification_url']}")
    print(f"Expires in: {device_info['expires_in']} seconds")
    print(f"\nWaiting for authentication...")

    # Step 2: Poll for token
    print(f"\n[Step 2] Polling for token (checking every {device_info['interval']} seconds)...")

    token_data = M365OAuth.poll_for_token(
        device_code=device_info["device_code"],
        interval=device_info["interval"]
    )

    if token_data:
        print("\n✓ Authentication successful!")
        print(f"  Access token: {token_data['access_token'][:20]}...")
        print(f"  Refresh token: {token_data['refresh_token'][:20]}...")
        print(f"  Expires at: {token_data['expires_at']}")
        print(f"  Scopes: {token_data['scope']}")

        # Test refresh
        print("\n[Step 3] Testing token refresh...")
        time.sleep(2)

        refreshed = M365OAuth.refresh_access_token(token_data["refresh_token"])

        if refreshed:
            print("✓ Token refresh successful!")
            print(f"  New access token: {refreshed['access_token'][:20]}...")
        else:
            print("❌ Token refresh failed")
    else:
        print("\n❌ Authentication failed or was declined")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    test_oauth_flow()
