"""
Plex OAuth 2.0 PIN-based Authentication Implementation

This module handles authentication with Plex using their PIN-based OAuth flow.
Unlike traditional Authorization Code Flow, Plex uses a simpler approach:
1. Request a PIN from Plex
2. User visits plex.tv/auth with the PIN
3. Poll Plex API to check if user authorized
4. Receive auth token upon authorization

Flow:
1. Request PIN from Plex API
2. Generate auth URL with client ID and PIN
3. User authenticates on app.plex.tv
4. Poll PIN status endpoint
5. Receive permanent auth token (no refresh needed)
6. Fetch user profile and server info

Reference: https://forums.plex.tv/t/authenticating-with-plex/609370
"""

import requests
import uuid
import time
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class PlexOAuth:
    """
    Plex PIN-based OAuth handler.

    Plex tokens are permanent and do not require refresh tokens.
    """

    # Plex OAuth endpoints
    PIN_REQUEST_URL = "https://plex.tv/api/v2/pins"
    PIN_STATUS_URL = "https://plex.tv/api/v2/pins/{pin_id}"
    USER_INFO_URL = "https://plex.tv/api/v2/user"
    RESOURCES_URL = "https://plex.tv/api/v2/resources"
    AUTH_WEB_URL = "https://app.plex.tv/auth#"

    # Generate a unique client identifier for this installation
    # This persists across requests and identifies our app to Plex
    CLIENT_IDENTIFIER = str(uuid.uuid4())

    @classmethod
    def get_headers(cls, auth_token: Optional[str] = None) -> Dict[str, str]:
        """
        Generate standard Plex API headers.

        Args:
            auth_token: Optional auth token for authenticated requests

        Returns:
            dict: Headers for Plex API requests
        """
        headers = {
            "X-Plex-Product": "THEO",
            "X-Plex-Version": "1.0",
            "X-Plex-Client-Identifier": cls.CLIENT_IDENTIFIER,
            "X-Plex-Platform": "Web",
            "X-Plex-Device": "THEO AI Assistant",
            "Accept": "application/json",
        }

        if auth_token:
            headers["X-Plex-Token"] = auth_token

        return headers

    @classmethod
    def request_pin(cls) -> Optional[Dict]:
        """
        Request a PIN from Plex for user authentication.

        Returns:
            dict: {
                'id': pin_id (int),
                'code': 4-digit PIN (str),
                'auth_url': Full URL for user to visit
            }
            None if request fails
        """
        try:
            logger.info("[PLEX] Requesting PIN from Plex API")

            response = requests.post(
                cls.PIN_REQUEST_URL,
                headers=cls.get_headers(),
                json={"strong": True},  # Request 4-digit PIN
                timeout=10,
            )

            if response.status_code != 201:
                logger.error(
                    f"[PLEX] PIN request failed: {response.status_code} - {response.text}"
                )
                return None

            data = response.json()
            pin_id = data.get("id")
            pin_code = data.get("code")

            if not pin_id or not pin_code:
                logger.error(f"[PLEX] Invalid PIN response: {data}")
                return None

            # Generate auth URL for user
            auth_url = f"{cls.AUTH_WEB_URL}?clientID={cls.CLIENT_IDENTIFIER}&code={pin_code}"

            logger.info(f"[PLEX] PIN generated successfully: {pin_code}")

            return {
                "id": pin_id,
                "code": pin_code,
                "auth_url": auth_url,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"[PLEX] Network error requesting PIN: {e}")
            return None
        except Exception as e:
            logger.error(f"[PLEX] Unexpected error requesting PIN: {e}")
            return None

    @classmethod
    def check_pin_status(cls, pin_id: int) -> Optional[str]:
        """
        Check if user has authorized the PIN.

        Args:
            pin_id: PIN ID from request_pin()

        Returns:
            str: Auth token if authorized
            None if not yet authorized or error
        """
        try:
            url = cls.PIN_STATUS_URL.format(pin_id=pin_id)

            response = requests.get(
                url,
                headers=cls.get_headers(),
                timeout=10,
            )

            if response.status_code != 200:
                logger.error(
                    f"[PLEX] PIN status check failed: {response.status_code} - {response.text}"
                )
                return None

            data = response.json()
            auth_token = data.get("authToken")

            if auth_token:
                logger.info(f"[PLEX] PIN {pin_id} authorized successfully")
                return auth_token
            else:
                # Not yet authorized (expected during polling)
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"[PLEX] Network error checking PIN status: {e}")
            return None
        except Exception as e:
            logger.error(f"[PLEX] Unexpected error checking PIN status: {e}")
            return None

    @classmethod
    def get_user_info(cls, auth_token: str) -> Optional[Dict]:
        """
        Fetch user profile from Plex.

        Args:
            auth_token: Plex authentication token

        Returns:
            dict: {
                'id': Plex user ID,
                'username': Username,
                'email': Email address,
                'thumb': Profile picture URL
            }
            None if request fails
        """
        try:
            logger.info("[PLEX] Fetching user profile")

            response = requests.get(
                cls.USER_INFO_URL,
                headers=cls.get_headers(auth_token),
                timeout=10,
            )

            if response.status_code != 200:
                logger.error(
                    f"[PLEX] User info request failed: {response.status_code} - {response.text}"
                )
                return None

            data = response.json()

            user_info = {
                "id": str(data.get("id", "")),
                "username": data.get("username", ""),
                "email": data.get("email", ""),
                "thumb": data.get("thumb", ""),
            }

            logger.info(f"[PLEX] User profile fetched: {user_info['username']}")

            return user_info

        except requests.exceptions.RequestException as e:
            logger.error(f"[PLEX] Network error fetching user info: {e}")
            return None
        except Exception as e:
            logger.error(f"[PLEX] Unexpected error fetching user info: {e}")
            return None

    @classmethod
    def get_primary_server(cls, auth_token: str) -> Optional[Dict]:
        """
        Get user's primary Plex Media Server.

        Prioritizes:
        1. Owned servers over shared servers
        2. First available server if multiple owned servers

        Args:
            auth_token: Plex authentication token

        Returns:
            dict: {
                'name': Server name,
                'url': Server URL,
                'version': Server version,
                'machine_identifier': Unique server ID,
                'owned': True if user owns server
            }
            None if no servers found or error
        """
        try:
            logger.info("[PLEX] Fetching server list")

            response = requests.get(
                cls.RESOURCES_URL,
                headers=cls.get_headers(auth_token),
                params={
                    "includeHttps": 1,
                    "includeRelay": 1,
                },
                timeout=10,
            )

            if response.status_code != 200:
                logger.error(
                    f"[PLEX] Server list request failed: {response.status_code} - {response.text}"
                )
                return None

            resources = response.json()

            # Filter to only servers (not players)
            servers = [
                r for r in resources
                if r.get("provides") == "server" and r.get("presence")
            ]

            if not servers:
                logger.warning("[PLEX] No servers found for user")
                return None

            # Prioritize owned servers
            owned_servers = [s for s in servers if s.get("owned")]
            server = owned_servers[0] if owned_servers else servers[0]

            # Get best connection URL
            connections = server.get("connections", [])
            if not connections:
                logger.error(f"[PLEX] No connections for server: {server.get('name')}")
                return None

            # Prefer local connections (marked as local=True or direct IP addresses)
            # Avoid .plex.direct relay URLs if possible as they may not resolve on all networks
            local_conn = next((c for c in connections if c.get("local")), None)

            # If no local connection found, prefer direct IP addresses over relay URLs
            if not local_conn:
                direct_ip_conn = next(
                    (c for c in connections
                     if ".plex.direct" not in c.get("uri", "") and
                     (c.get("uri", "").startswith("http://") or c.get("uri", "").startswith("https://"))),
                    None
                )
                if direct_ip_conn:
                    local_conn = direct_ip_conn

            # Fallback to HTTPS or first available
            https_conn = next((c for c in connections if c.get("uri", "").startswith("https")), None)
            best_conn = local_conn or https_conn or connections[0]

            logger.info(f"[PLEX] Selected connection: {best_conn.get('uri')} (local: {best_conn.get('local', False)})")

            server_info = {
                "name": server.get("name", ""),
                "url": best_conn.get("uri", ""),
                "version": server.get("productVersion", ""),
                "machine_identifier": server.get("clientIdentifier", ""),
                "owned": server.get("owned", False),
            }

            logger.info(
                f"[PLEX] Primary server selected: {server_info['name']} "
                f"(owned: {server_info['owned']})"
            )

            return server_info

        except requests.exceptions.RequestException as e:
            logger.error(f"[PLEX] Network error fetching servers: {e}")
            return None
        except Exception as e:
            logger.error(f"[PLEX] Unexpected error fetching servers: {e}")
            return None

    @classmethod
    def validate_token(cls, auth_token: str) -> bool:
        """
        Validate that an auth token is still valid.

        Args:
            auth_token: Plex authentication token

        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            response = requests.get(
                cls.USER_INFO_URL,
                headers=cls.get_headers(auth_token),
                timeout=10,
            )

            return response.status_code == 200

        except Exception as e:
            logger.error(f"[PLEX] Error validating token: {e}")
            return False
