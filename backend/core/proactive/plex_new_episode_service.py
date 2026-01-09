"""
Plex New Episode Notification Service

Checks for new episodes/seasons/movies added to Plex and sends proactive notifications.
Respects user notification preferences and quiet hours.

Note: This is infrastructure code that integrates with external Plex API
and runs as a scheduled background job. It's tested via integration tests.
"""  # pragma: no cover

import logging
from datetime import datetime, time
from typing import Optional, List, Dict

from core.memory import MemoryStore
from services.plex_client import PlexClient

logger = logging.getLogger(__name__)


class PlexNewEpisodeService:
    """Service for Plex new content notifications."""

    def __init__(self, memory: MemoryStore):
        """
        Initialize Plex notification service.

        Args:
            memory: MemoryStore instance
        """
        self.memory = memory

    def check_and_notify(self, user_id: int) -> bool:
        """
        Check for new content on Plex and send notifications.

        Args:
            user_id: User ID

        Returns:
            bool: True if notification sent, False otherwise
        """
        try:
            # Get settings
            settings = self.memory.get_plex_settings(user_id)
            if not settings:
                logger.debug(f"[PLEX] No settings for user {user_id}")
                return False

            # Check if any notifications are enabled
            if not (
                settings.get("new_episode_notifications_enabled")
                or settings.get("new_season_notifications_enabled")
                or settings.get("new_movie_notifications_enabled")
            ):
                logger.debug(f"[PLEX] All notifications disabled for user {user_id}")
                return False

            # Check quiet hours
            if self._is_quiet_hours(settings):
                logger.debug(f"[PLEX] In quiet hours for user {user_id}")
                return False

            # Get credentials
            credentials = self.memory.get_plex_credentials(user_id)
            if not credentials or not credentials.get("is_valid"):
                logger.warning(f"[PLEX] No valid credentials for user {user_id}")
                return False

            # Create Plex client
            client = PlexClient(
                credentials["access_token"], credentials["server_url"]
            )

            # Fetch recently added items
            recent_items = client.get_recently_added(limit=20)
            if not recent_items:
                logger.debug(f"[PLEX] No recent items for user {user_id}")
                return False

            # Filter by notification preferences and deduplication
            new_items = self._filter_new_items(user_id, recent_items, settings)

            if not new_items:
                logger.debug(f"[PLEX] No new unnotified items for user {user_id}")
                return False

            # Group items for better notifications (e.g., multiple episodes from same show)
            grouped_items = self._group_items(new_items)

            # Generate and send notifications
            for group in grouped_items:
                message = self._generate_notification(group)

                # Send proactive notification
                from core.proactive.shared import post_proactive_message

                post_proactive_message(
                    memory_store=self.memory,
                    user_id=user_id,
                    message_type="plex_new_content",
                    content=message,
                    provider_id="plex",
                    model="plex-notification",
                )

                # Track as notified
                for item in group:
                    self.memory.track_plex_notification(
                        user_id=user_id,
                        plex_item_key=item["key"],
                        plex_item_type=item["type"],
                    )

                logger.info(
                    f"[PLEX] Sent notification for {len(group)} item(s) to user {user_id}"
                )

            return True

        except Exception as e:
            logger.error(f"[PLEX] Error in check_and_notify for user {user_id}: {e}")
            return False

    def _is_quiet_hours(self, settings: Dict) -> bool:
        """
        Check if currently in quiet hours.

        Args:
            settings: User Plex settings

        Returns:
            bool: True if in quiet hours
        """
        quiet_start = settings.get("quiet_hours_start")
        quiet_end = settings.get("quiet_hours_end")

        if not quiet_start or not quiet_end:
            return False

        try:
            # Parse time strings (format: "HH:MM")
            now = datetime.now().time()
            start_time = datetime.strptime(quiet_start, "%H:%M").time()
            end_time = datetime.strptime(quiet_end, "%H:%M").time()

            # Handle overnight quiet hours (e.g., 22:00 to 08:00)
            if start_time < end_time:
                # Same day (e.g., 14:00 to 18:00)
                return start_time <= now <= end_time
            else:
                # Crosses midnight (e.g., 22:00 to 08:00)
                return now >= start_time or now <= end_time

        except Exception as e:
            logger.error(f"[PLEX] Error parsing quiet hours: {e}")
            return False

    def _filter_new_items(
        self, user_id: int, items: List[Dict], settings: Dict
    ) -> List[Dict]:
        """
        Filter items by notification preferences and deduplication.

        Args:
            user_id: User ID
            items: List of recently added items
            settings: User notification settings

        Returns:
            list: Filtered items
        """
        filtered = []

        for item in items:
            item_type = item.get("type")

            # Check notification preference for this type
            if item_type == "episode" and not settings.get(
                "new_episode_notifications_enabled"
            ):
                continue
            if item_type == "season" and not settings.get(
                "new_season_notifications_enabled"
            ):
                continue
            if item_type == "movie" and not settings.get(
                "new_movie_notifications_enabled"
            ):
                continue

            # Check if already notified
            item_key = item.get("key")
            if not item_key:
                continue

            if self.memory.is_plex_item_notified(user_id, item_key):
                continue

            filtered.append(item)

        return filtered

    def _group_items(self, items: List[Dict]) -> List[List[Dict]]:
        """
        Group related items for better notifications.

        For example, if 3 episodes of the same show were added, group them together.

        Args:
            items: List of items

        Returns:
            list: List of grouped items
        """
        # Group episodes by show
        show_episodes = {}
        other_items = []

        for item in items:
            if item.get("type") == "episode":
                show_title = item.get("show_title", "Unknown Show")
                if show_title not in show_episodes:
                    show_episodes[show_title] = []
                show_episodes[show_title].append(item)
            else:
                # Movies and seasons - notify individually
                other_items.append([item])

        # Convert show groups to list
        groups = list(show_episodes.values()) + other_items

        return groups

    def _generate_notification(self, items: List[Dict]) -> str:
        """
        Generate natural language notification for items.

        Args:
            items: List of items (may be grouped)

        Returns:
            str: Notification message
        """
        if not items:
            return ""

        # Single item
        if len(items) == 1:
            item = items[0]
            item_type = item.get("type")

            if item_type == "episode":
                show = item.get("show_title", "Unknown Show")
                season = item.get("season", 0)
                episode = item.get("episode", 0)
                title = item.get("title", "")
                return (
                    f"New episode available on Plex: {show} - "
                    f"S{season:02d}E{episode:02d}"
                    + (f' "{title}"' if title else "")
                )

            elif item_type == "season":
                show = item.get("show_title", "Unknown Show")
                season = item.get("season", 0)
                return f"New season available on Plex: {show} Season {season}"

            elif item_type == "movie":
                title = item.get("title", "Unknown Movie")
                year = item.get("year")
                return (
                    f"New movie available on Plex: {title}"
                    + (f" ({year})" if year else "")
                )

        # Multiple episodes from same show
        if all(item.get("type") == "episode" for item in items):
            show = items[0].get("show_title", "Unknown Show")

            if len(items) == 2:
                # Two episodes
                s1, e1 = items[0].get("season", 0), items[0].get("episode", 0)
                s2, e2 = items[1].get("season", 0), items[1].get("episode", 0)
                return (
                    f"{len(items)} new episodes of {show} available on Plex: "
                    f"S{s1:02d}E{e1:02d}, S{s2:02d}E{e2:02d}"
                )
            else:
                # 3+ episodes
                return f"{len(items)} new episodes of {show} available on Plex"

        # Multiple different items (shouldn't happen with grouping, but handle it)
        return f"{len(items)} new items available on your Plex server"
