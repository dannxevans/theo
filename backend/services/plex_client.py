"""
Plex Media Server API Client

This module provides a wrapper around the Plex Media Server HTTP API for querying
media library data, watch history, and currently playing sessions.

API Reference: https://github.com/Arcanemagus/plex-api/wiki
"""

import requests
from typing import Dict, List, Optional
import logging
from datetime import datetime
import xml.etree.ElementTree as ET

logger = logging.getLogger(__name__)


class PlexClient:
    """
    Client for interacting with Plex Media Server API.

    Note: Plex API returns XML by default. We request JSON where possible,
    but some endpoints only support XML.
    """

    def __init__(self, auth_token: str, server_url: str):
        """
        Initialize Plex client.

        Args:
            auth_token: Plex authentication token
            server_url: Plex Media Server URL (e.g., http://192.168.1.100:32400)
        """
        self.auth_token = auth_token
        self.server_url = server_url.rstrip("/")

    def _get_headers(self) -> Dict[str, str]:
        """Generate headers for Plex API requests."""
        return {
            "X-Plex-Token": self.auth_token,
            "Accept": "application/json",
        }

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Make authenticated request to Plex server.

        Args:
            endpoint: API endpoint (e.g., "/library/sections")
            params: Optional query parameters

        Returns:
            dict: JSON response or None on error
        """
        try:
            url = f"{self.server_url}{endpoint}"

            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=15,
            )

            if response.status_code == 401:
                logger.error("[PLEX] Unauthorized - invalid token")
                return None

            if response.status_code != 200:
                logger.error(
                    f"[PLEX] API request failed: {response.status_code} - {response.text}"
                )
                return None

            # Plex returns JSON with MediaContainer wrapper
            data = response.json()
            return data.get("MediaContainer", {})

        except requests.exceptions.RequestException as e:
            logger.error(f"[PLEX] Network error: {e}")
            return None
        except Exception as e:
            logger.error(f"[PLEX] Unexpected error: {e}")
            return None

    def get_library_sections(self) -> List[Dict]:
        """
        Get all library sections (Movies, TV Shows, Music, etc.).

        Returns:
            list: [{
                'key': Section ID,
                'title': Section name,
                'type': 'movie', 'show', 'artist', etc.
            }]
        """
        try:
            data = self._make_request("/library/sections")

            if not data:
                return []

            directories = data.get("Directory", [])

            sections = []
            for directory in directories:
                sections.append({
                    "key": directory.get("key"),
                    "title": directory.get("title"),
                    "type": directory.get("type"),
                })

            logger.info(f"[PLEX] Found {len(sections)} library sections")
            return sections

        except Exception as e:
            logger.error(f"[PLEX] Error fetching library sections: {e}")
            return []

    def get_recently_watched(self, limit: int = 10) -> List[Dict]:
        """
        Get recently watched items across all libraries.

        Returns:
            list: [{
                'title': Item title,
                'type': 'episode', 'movie', etc.,
                'rating_key': Unique item ID,
                'viewed_at': Unix timestamp,
                'show_title': Show name (for episodes),
                'season': Season number (for episodes),
                'episode': Episode number (for episodes),
                'thumb': Thumbnail URL,
                'year': Release year
            }]
        """
        try:
            data = self._make_request(
                "/status/sessions/history/all",
                params={
                    "sort": "viewedAt:desc",
                }
            )

            if not data:
                return []

            metadata = data.get("Metadata", [])

            items = []
            for item in metadata[:limit]:
                item_data = {
                    "title": item.get("title", ""),
                    "type": item.get("type", ""),
                    "rating_key": item.get("ratingKey", ""),
                    "viewed_at": item.get("viewedAt", 0),
                    "thumb": item.get("thumb", ""),
                    "year": item.get("year"),
                }

                # Add episode-specific fields
                if item.get("type") == "episode":
                    item_data.update({
                        "show_title": item.get("grandparentTitle", ""),
                        "season": item.get("parentIndex", 0),
                        "episode": item.get("index", 0),
                    })

                items.append(item_data)

            logger.info(f"[PLEX] Found {len(items)} recently watched items")
            return items

        except Exception as e:
            logger.error(f"[PLEX] Error fetching recently watched: {e}")
            return []

    def get_on_deck(self) -> List[Dict]:
        """
        Get "On Deck" items (next episodes/movies to watch).

        Returns:
            list: [{
                'title': Item title,
                'type': 'episode', 'movie', etc.,
                'rating_key': Unique item ID,
                'show_title': Show name (for episodes),
                'season': Season number (for episodes),
                'episode': Episode number (for episodes),
                'thumb': Thumbnail URL,
                'summary': Description
            }]
        """
        try:
            data = self._make_request("/library/onDeck")

            if not data:
                return []

            metadata = data.get("Metadata", [])

            items = []
            for item in metadata:
                item_data = {
                    "title": item.get("title", ""),
                    "type": item.get("type", ""),
                    "rating_key": item.get("ratingKey", ""),
                    "thumb": item.get("thumb", ""),
                    "summary": item.get("summary", ""),
                }

                # Add episode-specific fields
                if item.get("type") == "episode":
                    item_data.update({
                        "show_title": item.get("grandparentTitle", ""),
                        "season": item.get("parentIndex", 0),
                        "episode": item.get("index", 0),
                    })

                items.append(item_data)

            logger.info(f"[PLEX] Found {len(items)} On Deck items")
            return items

        except Exception as e:
            logger.error(f"[PLEX] Error fetching On Deck: {e}")
            return []

    def get_recently_added(self, section_key: Optional[str] = None, limit: int = 10) -> List[Dict]:
        """
        Get recently added items in a library section.

        Args:
            section_key: Library section ID (if None, searches all TV sections)
            limit: Maximum items to return

        Returns:
            list: [{
                'title': Item title,
                'type': 'episode', 'season', 'movie', etc.,
                'rating_key': Unique item ID,
                'key': Item key for API calls,
                'show_title': Show name (for episodes),
                'season': Season number (for episodes),
                'episode': Episode number (for episodes),
                'added_at': Unix timestamp,
                'thumb': Thumbnail URL
            }]
        """
        try:
            items = []

            # If no section specified, get all TV show sections
            if not section_key:
                sections = self.get_library_sections()
                tv_sections = [s for s in sections if s.get("type") == "show"]

                # Query each TV section
                for section in tv_sections:
                    section_items = self.get_recently_added(
                        section_key=section.get("key"),
                        limit=limit
                    )
                    items.extend(section_items)

                # Sort by added_at and limit
                items.sort(key=lambda x: x.get("added_at", 0), reverse=True)
                return items[:limit]

            # Query specific section
            data = self._make_request(
                f"/library/sections/{section_key}/recentlyAdded"
            )

            if not data:
                return []

            metadata = data.get("Metadata", [])

            for item in metadata[:limit]:
                item_data = {
                    "title": item.get("title", ""),
                    "type": item.get("type", ""),
                    "rating_key": item.get("ratingKey", ""),
                    "key": item.get("key", ""),
                    "added_at": item.get("addedAt", 0),
                    "thumb": item.get("thumb", ""),
                }

                # Add episode-specific fields
                if item.get("type") == "episode":
                    item_data.update({
                        "show_title": item.get("grandparentTitle", ""),
                        "season": item.get("parentIndex", 0),
                        "episode": item.get("index", 0),
                    })
                # Add season-specific fields
                elif item.get("type") == "season":
                    item_data.update({
                        "show_title": item.get("parentTitle", ""),
                        "season": item.get("index", 0),
                    })

                items.append(item_data)

            logger.info(f"[PLEX] Found {len(items)} recently added items in section {section_key}")
            return items

        except Exception as e:
            logger.error(f"[PLEX] Error fetching recently added: {e}")
            return []

    def get_currently_playing(self) -> List[Dict]:
        """
        Get currently playing sessions (active streams).

        Returns:
            list: [{
                'title': Item title,
                'type': 'episode', 'movie', etc.,
                'user': Username playing,
                'player': Player name/device,
                'state': 'playing', 'paused', 'buffering',
                'show_title': Show name (for episodes),
                'season': Season number (for episodes),
                'episode': Episode number (for episodes),
                'progress_ms': Playback position in milliseconds,
                'duration_ms': Total duration in milliseconds
            }]
        """
        try:
            data = self._make_request("/status/sessions")

            if not data:
                return []

            metadata = data.get("Metadata", [])

            sessions = []
            for item in metadata:
                # Get player and user info
                player = item.get("Player", {})
                user = item.get("User", {})

                session_data = {
                    "title": item.get("title", ""),
                    "type": item.get("type", ""),
                    "user": user.get("title", ""),
                    "player": player.get("title", ""),
                    "state": player.get("state", ""),
                    "progress_ms": item.get("viewOffset", 0),
                    "duration_ms": item.get("duration", 0),
                }

                # Add episode-specific fields
                if item.get("type") == "episode":
                    session_data.update({
                        "show_title": item.get("grandparentTitle", ""),
                        "season": item.get("parentIndex", 0),
                        "episode": item.get("index", 0),
                    })

                sessions.append(session_data)

            logger.info(f"[PLEX] Found {len(sessions)} active sessions")
            return sessions

        except Exception as e:
            logger.error(f"[PLEX] Error fetching currently playing: {e}")
            return []

    def get_item_details(self, rating_key: str) -> Optional[Dict]:
        """
        Get detailed metadata for a specific item.

        Args:
            rating_key: Item's rating key (unique ID)

        Returns:
            dict: Item metadata including summary, cast, ratings, etc.
            None on error
        """
        try:
            data = self._make_request(f"/library/metadata/{rating_key}")

            if not data:
                return None

            metadata = data.get("Metadata", [])
            if not metadata:
                return None

            item = metadata[0]

            details = {
                "title": item.get("title", ""),
                "type": item.get("type", ""),
                "rating_key": item.get("ratingKey", ""),
                "summary": item.get("summary", ""),
                "rating": item.get("rating"),
                "year": item.get("year"),
                "duration_ms": item.get("duration", 0),
                "thumb": item.get("thumb", ""),
            }

            # Add episode-specific fields
            if item.get("type") == "episode":
                details.update({
                    "show_title": item.get("grandparentTitle", ""),
                    "season": item.get("parentIndex", 0),
                    "episode": item.get("index", 0),
                })

            return details

        except Exception as e:
            logger.error(f"[PLEX] Error fetching item details: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Test connection to Plex server.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            data = self._make_request("/")
            return data is not None

        except Exception as e:
            logger.error(f"[PLEX] Connection test failed: {e}")
            return False
