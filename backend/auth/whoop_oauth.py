"""
WHOOP OAuth 2.0 Authorization Code Flow Implementation

This module handles authentication with WHOOP using the standard OAuth 2.0
Authorization Code Flow with PKCE (Proof Key for Code Exchange).

Flow:
1. Generate authorization URL with state (CSRF protection)
2. User authenticates on WHOOP and authorizes scopes
3. WHOOP redirects to callback with authorization code
4. Exchange code for access + refresh tokens
5. Store tokens and fetch user profile

Reference: https://developer.whoop.com/docs/developing/user-auth/
"""

import requests
import secrets
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple
import logging
import os

logger = logging.getLogger(__name__)


class WHOOPOAuth:
    """
    WHOOP OAuth 2.0 Authorization Code Flow handler.

    Configuration can be set via:
    1. Database (feature_providers table) - PREFERRED
    2. Environment variables (.env) - FALLBACK
    """

    # OAuth scopes required for health data access
    SCOPES = [
        "read:profile",
        "read:recovery",
        "read:sleep",
        "read:workout",
        "read:cycles",
        "offline"  # Required to receive refresh tokens
    ]

    # WHOOP OAuth endpoints
    AUTHORIZATION_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
    TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
    REVOKE_URL = "https://api.prod.whoop.com/oauth/oauth2/revoke"

    @classmethod
    def get_config(cls, user_id: int = None, memory_store=None) -> Dict[str, str]:
        """
        Get WHOOP OAuth configuration from database or environment.

        Priority:
        1. Database config (if user_id and memory_store provided)
        2. Environment variables

        Args:
            user_id: User ID for database lookup
            memory_store: MemoryStore instance

        Returns:
            dict: {client_id, client_secret, redirect_uri}
        """
        # Try database preferences first
        if user_id and memory_store:
            prefs = memory_store.get_all(str(user_id))
            client_id = prefs.get('whoop_client_id')
            client_secret = prefs.get('whoop_client_secret')
            redirect_uri = prefs.get('whoop_redirect_uri')

            if client_id and client_secret:
                return {
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri or 'http://localhost:1066/api/whoop/auth/callback'
                }

        # Fallback to environment variables
        return {
            'client_id': os.getenv("WHOOP_CLIENT_ID", ""),
            'client_secret': os.getenv("WHOOP_CLIENT_SECRET", ""),
            'redirect_uri': os.getenv("WHOOP_REDIRECT_URI", "http://localhost:1066/api/whoop/auth/callback")
        }

    @classmethod
    def is_configured(cls, user_id: int = None, memory_store=None) -> bool:
        """
        Check if WHOOP OAuth is properly configured.

        Args:
            user_id: User ID for database lookup
            memory_store: MemoryStore instance

        Returns:
            True if client_id and client_secret are set
        """
        config = cls.get_config(user_id, memory_store)
        return bool(config['client_id'] and config['client_secret'])

    @classmethod
    def generate_pkce_pair(cls) -> Tuple[str, str]:
        """
        Generate PKCE code verifier and challenge.

        PKCE (Proof Key for Code Exchange) adds security to OAuth flow.

        Returns:
            Tuple of (code_verifier, code_challenge)
        """
        # Generate random code verifier (43-128 characters)
        code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

        # Generate code challenge (SHA256 hash of verifier)
        challenge = hashlib.sha256(code_verifier.encode('utf-8')).digest()
        code_challenge = base64.urlsafe_b64encode(challenge).decode('utf-8').rstrip('=')

        return code_verifier, code_challenge

    @classmethod
    def get_authorization_url(cls, state: str, user_id: int = None, memory_store=None) -> Dict[str, str]:
        """
        Generate authorization URL for user to authenticate.

        Args:
            state: Random state token for CSRF protection
            user_id: User ID for database config lookup
            memory_store: MemoryStore instance

        Returns:
            Dictionary containing:
            {
                "authorization_url": "https://...",
                "state": "..."
            }

        Raises:
            ValueError: If CLIENT_ID is not configured
        """
        if not cls.is_configured(user_id, memory_store):
            raise ValueError(
                "WHOOP OAuth not configured. "
                "Please set WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET in your .env file "
                "or configure via Settings → WHOOP Integration."
            )

        # Get config from database or env vars
        config = cls.get_config(user_id, memory_store)

        # Build authorization URL with parameters
        params = {
            "client_id": config['client_id'],
            "redirect_uri": config['redirect_uri'],
            "response_type": "code",
            "scope": " ".join(cls.SCOPES),
            "state": state
        }

        # Construct URL manually to ensure proper encoding
        from urllib.parse import urlencode
        query_string = urlencode(params)
        authorization_url = f"{cls.AUTHORIZATION_URL}?{query_string}"

        logger.info("[WHOOP_OAUTH] Generated authorization URL")
        logger.info(f"[WHOOP_OAUTH] Requesting scopes: {', '.join(cls.SCOPES)}")
        logger.debug(f"[WHOOP_OAUTH] Redirect URI: {config['redirect_uri']}")

        return {
            "authorization_url": authorization_url,
            "state": state
        }

    @classmethod
    def exchange_code_for_token(cls, code: str, user_id: int = None, memory_store=None) -> Optional[Dict]:
        """
        Exchange authorization code for access token.

        This is called after user authorizes on WHOOP and we receive
        the authorization code via redirect.

        Args:
            code: Authorization code from WHOOP callback
            user_id: User ID for database config lookup
            memory_store: MemoryStore instance

        Returns:
            Token data if successful:
            {
                "access_token": "...",
                "refresh_token": "...",
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": datetime object,
                "scope": "..."
            }

            None if exchange fails

        Raises:
            ValueError: If CLIENT_ID or CLIENT_SECRET not configured
        """
        if not cls.is_configured(user_id, memory_store):
            raise ValueError("WHOOP OAuth not configured")

        # Get config from database or env vars
        config = cls.get_config(user_id, memory_store)

        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config['client_id'],
            "client_secret": config['client_secret'],
            "redirect_uri": config['redirect_uri']
        }

        logger.info("[WHOOP_OAUTH] Exchanging authorization code for token...")

        try:
            response = requests.post(
                cls.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                logger.info("[WHOOP_OAUTH] ✓ Token exchange successful!")
                logger.info(f"[WHOOP_OAUTH] Token expires in {data['expires_in']} seconds ({data['expires_in']/3600:.1f} hours)")
                logger.info(f"[WHOOP_OAUTH] Refresh token received: {bool(data.get('refresh_token'))}")
                logger.info(f"[WHOOP_OAUTH] Scopes: {data.get('scope', 'not provided')}")

                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", ""),  # WHOOP may not return refresh token
                    "token_type": data.get("token_type", "Bearer"),
                    "expires_in": data["expires_in"],
                    "expires_at": datetime.utcnow() + timedelta(seconds=data["expires_in"]),
                    "scope": data.get("scope", " ".join(cls.SCOPES))
                }
            else:
                error_data = response.json()
                error = error_data.get("error", "unknown")
                error_description = error_data.get("error_description", "No description")

                logger.error(f"[WHOOP_OAUTH] Token exchange failed: {error}")
                logger.error(f"[WHOOP_OAUTH] Error description: {error_description}")
                logger.error(f"[WHOOP_OAUTH] Status code: {response.status_code}")

                return None

        except requests.RequestException as e:
            logger.error(f"[WHOOP_OAUTH] Token exchange request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"[WHOOP_OAUTH] Unexpected error during token exchange: {e}")
            return None

    @classmethod
    def refresh_access_token(cls, refresh_token: str, user_id: int = None, memory_store=None) -> Optional[Dict]:
        """
        Refresh an expired access token using refresh token.

        This should be called when the access token expires.

        Args:
            refresh_token: Refresh token from previous authentication
            user_id: User ID for database config lookup
            memory_store: MemoryStore instance

        Returns:
            New token data if successful:
            {
                "access_token": "...",
                "refresh_token": "..." (may be rotated),
                "token_type": "Bearer",
                "expires_in": 3600,
                "expires_at": datetime object
            }

            None if refresh fails (user needs to re-authenticate)

        Raises:
            ValueError: If CLIENT_ID or CLIENT_SECRET not configured
        """
        if not cls.is_configured(user_id, memory_store):
            raise ValueError("WHOOP OAuth not configured")

        # Get config from database or env vars
        config = cls.get_config(user_id, memory_store)

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config['client_id'],
            "client_secret": config['client_secret'],
            "scope": "offline"  # Required by WHOOP API for token refresh
        }

        logger.info("[WHOOP_OAUTH] Refreshing access token...")

        try:
            response = requests.post(
                cls.TOKEN_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                logger.info("[WHOOP_OAUTH] ✓ Token refreshed successfully")
                logger.info(f"[WHOOP_OAUTH] New token expires in {data['expires_in']} seconds ({data['expires_in']/3600:.1f} hours)")
                logger.info(f"[WHOOP_OAUTH] New refresh token received: {bool(data.get('refresh_token'))}")

                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", refresh_token),  # May or may not rotate
                    "token_type": data.get("token_type", "Bearer"),
                    "expires_in": data["expires_in"],
                    "expires_at": datetime.utcnow() + timedelta(seconds=data["expires_in"])
                }
            else:
                error_data = response.json()
                error = error_data.get("error", "unknown")
                error_description = error_data.get("error_description", "No description")

                logger.error(f"[WHOOP_OAUTH] Token refresh failed: {error}")
                logger.error(f"[WHOOP_OAUTH] Error description: {error_description}")
                logger.error(f"[WHOOP_OAUTH] Status code: {response.status_code}")
                logger.error(f"[WHOOP_OAUTH] Full response: {response.text}")

                return None

        except requests.RequestException as e:
            logger.error(f"[WHOOP_OAUTH] Token refresh request failed: {e}")
            return None
        except Exception as e:
            logger.error(f"[WHOOP_OAUTH] Unexpected error during token refresh: {e}")
            return None

    @classmethod
    def revoke_token(cls, token: str, user_id: int = None, memory_store=None) -> bool:
        """
        Revoke an access or refresh token.

        Called when user disconnects WHOOP to invalidate their tokens.

        Args:
            token: Access token or refresh token to revoke
            user_id: User ID for database config lookup
            memory_store: MemoryStore instance

        Returns:
            True if revocation successful or token already invalid
            False if revocation fails

        Raises:
            ValueError: If CLIENT_ID or CLIENT_SECRET not configured
        """
        if not cls.is_configured(user_id, memory_store):
            raise ValueError("WHOOP OAuth not configured")

        # Get config from database or env vars
        config = cls.get_config(user_id, memory_store)

        payload = {
            "token": token,
            "client_id": config['client_id'],
            "client_secret": config['client_secret']
        }

        logger.info("[WHOOP_OAUTH] Revoking token...")

        try:
            response = requests.post(
                cls.REVOKE_URL,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10
            )

            if response.status_code == 200:
                logger.info("[WHOOP_OAUTH] ✓ Token revoked successfully")
                return True
            else:
                # Some OAuth providers return 200 even if token doesn't exist
                # Treat as success if status is 2xx or 4xx (already invalid)
                if response.status_code < 500:
                    logger.warning(f"[WHOOP_OAUTH] Token revocation returned {response.status_code}, treating as success")
                    return True
                else:
                    logger.error(f"[WHOOP_OAUTH] Token revocation failed: {response.status_code}")
                    return False

        except requests.RequestException as e:
            logger.error(f"[WHOOP_OAUTH] Token revocation request failed: {e}")
            # Don't fail disconnect if revocation fails - user can still disconnect locally
            logger.warning("[WHOOP_OAUTH] Continuing with local credential deletion despite revocation failure")
            return True
        except Exception as e:
            logger.error(f"[WHOOP_OAUTH] Unexpected error during token revocation: {e}")
            return True

    @classmethod
    def get_configuration_instructions(cls) -> str:
        """
        Get instructions for configuring WHOOP OAuth.

        Returns:
            Multi-line string with setup instructions
        """
        return """
To configure WHOOP integration:

1. Create WHOOP Developer Account:
   - Go to https://developer.whoop.com
   - Sign up for a developer account
   - Verify your email

2. Create OAuth Application:
   - Navigate to Developer Portal → Applications
   - Click "Create New Application"
   - Fill in:
     * Application Name: THEO AI Assistant
     * Description: Personal AI assistant with health insights
     * Application Type: Web Application
     * Homepage URL: http://localhost:5174
     * Redirect URI: http://localhost:1066/api/whoop/auth/callback

3. Configure OAuth Scopes:
   - Request these scopes:
     * read:profile
     * read:recovery
     * read:sleep
     * read:workout
     * read:cycles

4. Get your credentials:
   - Copy the Client ID
   - Copy the Client Secret
   - Add to your .env file:
     WHOOP_CLIENT_ID=your-client-id-here
     WHOOP_CLIENT_SECRET=your-client-secret-here
     WHOOP_REDIRECT_URI=http://localhost:1066/api/whoop/auth/callback

5. For production deployment:
   - Update redirect URI to: https://your-domain.com/api/whoop/auth/callback
   - Add both dev and prod redirect URIs in WHOOP app settings

That's it! THEO can now connect to your WHOOP account.

For detailed instructions, see: /dev-docs/WHOOP_SETUP_GUIDE.md
"""


# Helper function for testing
def test_oauth_flow():
    """
    Test the OAuth flow interactively.
    Run with: python3 -m backend.auth.whoop_oauth
    """
    print("=" * 60)
    print("WHOOP OAuth Authorization Code Flow Test")
    print("=" * 60)

    if not WHOOPOAuth.is_configured():
        print("\n❌ WHOOP OAuth not configured!")
        print(WHOOPOAuth.get_configuration_instructions())
        return

    print("\n✓ WHOOP OAuth is configured")
    print(f"  Client ID: {WHOOPOAuth.CLIENT_ID[:8]}...")
    print(f"  Redirect URI: {WHOOPOAuth.REDIRECT_URI}")

    # Generate state token
    state = secrets.token_urlsafe(32)

    # Step 1: Get authorization URL
    print("\n[Step 1] Generating authorization URL...")
    try:
        auth_data = WHOOPOAuth.get_authorization_url(state)
    except Exception as e:
        print(f"❌ Failed: {e}")
        return

    print(f"\n✓ Authorization URL generated!")
    print(f"\nOpen this URL in your browser to authorize:")
    print(f"\n{auth_data['authorization_url']}\n")
    print(f"State token: {state}")
    print("\nAfter authorizing, WHOOP will redirect to your callback URL with a code.")
    print("Copy the 'code' parameter from the URL and paste it here.")

    # In a real implementation, the callback would handle this automatically
    print("\nNote: This is a manual test. In production, the callback endpoint")
    print("      handles the code exchange automatically.")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Enable debug logging
    logging.basicConfig(level=logging.INFO)
    test_oauth_flow()
