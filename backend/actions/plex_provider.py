"""
Plex Action Provider.

Handles action execution for Plex Media Server integration.
"""

from typing import Dict, Any, Optional
from actions.base import ActionProvider
from services.plex_client import PlexClient
import logging

logger = logging.getLogger(__name__)


class PlexProvider(ActionProvider):
    """
    Action provider for Plex Media Server.

    Capabilities:
    - get_recently_watched: Get recently watched items
    - get_on_deck: Get items in On Deck
    - get_currently_playing: Get currently playing sessions
    """

    def __init__(
        self,
        access_token: str,
        server_url: str,
        user_id: int,
        memory_store=None
    ):
        """
        Initialize Plex provider.

        Args:
            access_token: Plex authentication token
            server_url: Plex server URL
            user_id: User ID
            memory_store: MemoryStore instance (optional)
        """
        self.access_token = access_token
        self.server_url = server_url
        self.user_id = user_id
        self.memory = memory_store
        self.client = PlexClient(access_token, server_url)

    def get_capabilities(self) -> list[str]:
        """Return list of supported capabilities."""
        return [
            "get_recently_watched",
            "get_on_deck",
            "get_currently_playing",
        ]

    def execute_action(
        self,
        action_type: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a Plex action.

        Args:
            action_type: Type of action to execute
            parameters: Action parameters

        Returns:
            Action result dictionary
        """
        try:
            if action_type == "get_recently_watched":
                return self._get_recently_watched(parameters)
            elif action_type == "get_on_deck":
                return self._get_on_deck(parameters)
            elif action_type == "get_currently_playing":
                return self._get_currently_playing(parameters)
            else:
                logger.warning(f"[PLEX_PROVIDER] Unknown action type: {action_type}")
                return {
                    "success": False,
                    "error": f"Unknown action type: {action_type}"
                }

        except Exception as e:
            logger.error(f"[PLEX_PROVIDER] Error executing {action_type}: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def _get_recently_watched(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get recently watched items."""
        limit = parameters.get("limit", 10)

        items = self.client.get_recently_watched(limit=limit)

        if items is None:
            return {
                "success": False,
                "error": "Failed to fetch recently watched items"
            }

        return {
            "success": True,
            "items": items,
            "count": len(items)
        }

    def _get_on_deck(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get On Deck items."""
        items = self.client.get_on_deck()

        if items is None:
            return {
                "success": False,
                "error": "Failed to fetch On Deck items"
            }

        return {
            "success": True,
            "items": items,
            "count": len(items)
        }

    def _get_currently_playing(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get currently playing sessions."""
        sessions = self.client.get_currently_playing()

        if sessions is None:
            return {
                "success": False,
                "error": "Failed to fetch currently playing sessions"
            }

        return {
            "success": True,
            "sessions": sessions,
            "count": len(sessions)
        }

    def test_connection(self) -> bool:
        """Test the Plex connection."""
        return self.client.test_connection()
