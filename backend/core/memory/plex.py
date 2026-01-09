"""
Plex Integration Operations.

Handles Plex OAuth credentials, settings, and notification tracking storage.
"""

from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, insert

from .base import BaseMemoryOperations


class PlexOperations(BaseMemoryOperations):
    """Plex integration management operations."""

    # =============================
    # Credentials
    # =============================

    def store_plex_credentials(
        self,
        user_id: int,
        access_token: str,
        plex_user_id: str,
        plex_username: str,
        server_url: str,
        server_name: str = None,
        server_version: str = None,
    ):
        """
        Store Plex OAuth credentials.

        Note: Plex tokens are permanent and do not expire.

        Args:
            user_id: User ID
            access_token: Plex authentication token
            plex_user_id: Plex's internal user ID
            plex_username: Plex username
            server_url: Primary server URL
            server_name: Server name (optional)
            server_version: Server version (optional)
        """
        with self.engine.begin() as conn:
            # Try to update first
            result = conn.execute(
                update(self.plex_credentials)
                .where(self.plex_credentials.c.user_id == user_id)
                .values(
                    access_token=access_token,
                    plex_user_id=plex_user_id,
                    plex_username=plex_username,
                    server_url=server_url,
                    server_name=server_name,
                    server_version=server_version,
                    is_valid=True,
                    last_error=None,
                    updated_at=datetime.utcnow(),
                )
            )

            # If no rows affected, insert instead
            if result.rowcount == 0:
                conn.execute(
                    insert(self.plex_credentials).values(
                        user_id=user_id,
                        access_token=access_token,
                        plex_user_id=plex_user_id,
                        plex_username=plex_username,
                        server_url=server_url,
                        server_name=server_name,
                        server_version=server_version,
                        is_valid=True,
                    )
                )

    def get_plex_credentials(self, user_id: int):
        """
        Get Plex credentials for a user.

        Args:
            user_id: User ID

        Returns:
            dict: Credentials or None
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                select(self.plex_credentials).where(
                    self.plex_credentials.c.user_id == user_id
                )
            ).fetchone()

            if not result:
                return None

            return {
                "user_id": result.user_id,
                "access_token": result.access_token,
                "plex_user_id": result.plex_user_id,
                "plex_username": result.plex_username,
                "server_url": result.server_url,
                "server_name": result.server_name,
                "server_version": result.server_version,
                "is_valid": bool(result.is_valid),
                "last_error": result.last_error,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            }

    def update_plex_credentials(self, user_id: int, **kwargs):
        """
        Update Plex credentials (partial update).

        Args:
            user_id: User ID
            **kwargs: Fields to update (access_token, server_url, etc.)
        """
        if not kwargs:
            return

        with self.engine.begin() as conn:
            kwargs["updated_at"] = datetime.utcnow()

            conn.execute(
                update(self.plex_credentials)
                .where(self.plex_credentials.c.user_id == user_id)
                .values(**kwargs)
            )

    def invalidate_plex_credentials(self, user_id: int, error_message: str):
        """
        Mark Plex credentials as invalid.

        Args:
            user_id: User ID
            error_message: Error message to store
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.plex_credentials)
                .where(self.plex_credentials.c.user_id == user_id)
                .values(
                    is_valid=False,
                    last_error=error_message,
                    updated_at=datetime.utcnow(),
                )
            )

    def delete_plex_credentials(self, user_id: int):
        """
        Delete Plex credentials for a user.

        Args:
            user_id: User ID
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.plex_credentials).where(
                    self.plex_credentials.c.user_id == user_id
                )
            )

    # =============================
    # Settings
    # =============================

    def get_plex_settings(self, user_id: int):
        """
        Get Plex notification settings for a user.

        Returns default settings if none exist.

        Args:
            user_id: User ID

        Returns:
            dict: Settings with defaults
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                select(self.plex_settings).where(
                    self.plex_settings.c.user_id == user_id
                )
            ).fetchone()

            if not result:
                # Return defaults (all notifications disabled per user request)
                return {
                    "user_id": user_id,
                    "new_episode_notifications_enabled": False,
                    "new_season_notifications_enabled": False,
                    "new_movie_notifications_enabled": False,
                    "check_frequency_minutes": 15,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                }

            return {
                "user_id": result.user_id,
                "new_episode_notifications_enabled": bool(
                    result.new_episode_notifications_enabled
                ),
                "new_season_notifications_enabled": bool(
                    result.new_season_notifications_enabled
                ),
                "new_movie_notifications_enabled": bool(
                    result.new_movie_notifications_enabled
                ),
                "check_frequency_minutes": result.check_frequency_minutes,
                "quiet_hours_start": result.quiet_hours_start,
                "quiet_hours_end": result.quiet_hours_end,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
            }

    def update_plex_settings(self, user_id: int, **kwargs):
        """
        Update Plex notification settings.

        Creates settings entry if it doesn't exist.

        Args:
            user_id: User ID
            **kwargs: Settings to update
        """
        with self.engine.begin() as conn:
            # Try to update first
            result = conn.execute(
                update(self.plex_settings)
                .where(self.plex_settings.c.user_id == user_id)
                .values(updated_at=datetime.utcnow(), **kwargs)
            )

            # If no rows affected, insert with defaults + provided values
            if result.rowcount == 0:
                values = {
                    "user_id": user_id,
                    "new_episode_notifications_enabled": kwargs.get(
                        "new_episode_notifications_enabled", False
                    ),
                    "new_season_notifications_enabled": kwargs.get(
                        "new_season_notifications_enabled", False
                    ),
                    "new_movie_notifications_enabled": kwargs.get(
                        "new_movie_notifications_enabled", False
                    ),
                    "check_frequency_minutes": kwargs.get("check_frequency_minutes", 15),
                    "quiet_hours_start": kwargs.get("quiet_hours_start"),
                    "quiet_hours_end": kwargs.get("quiet_hours_end"),
                }
                conn.execute(insert(self.plex_settings).values(**values))

    def delete_plex_settings(self, user_id: int):
        """
        Delete Plex settings for a user.

        Args:
            user_id: User ID
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.plex_settings).where(
                    self.plex_settings.c.user_id == user_id
                )
            )

    # =============================
    # Notification Tracking
    # =============================

    def is_plex_item_notified(self, user_id: int, plex_item_key: str) -> bool:
        """
        Check if user has been notified about a Plex item.

        Args:
            user_id: User ID
            plex_item_key: Plex item key (e.g., "/library/metadata/12345")

        Returns:
            bool: True if already notified
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                select(self.plex_notification_tracking).where(
                    self.plex_notification_tracking.c.user_id == user_id,
                    self.plex_notification_tracking.c.plex_item_key == plex_item_key,
                )
            ).fetchone()

            return result is not None

    def track_plex_notification(
        self, user_id: int, plex_item_key: str, plex_item_type: str
    ):
        """
        Track that user was notified about a Plex item.

        Args:
            user_id: User ID
            plex_item_key: Plex item key
            plex_item_type: Item type (episode, season, movie)
        """
        with self.engine.begin() as conn:
            # Use INSERT OR IGNORE to handle race conditions
            try:
                conn.execute(
                    insert(self.plex_notification_tracking).values(
                        user_id=user_id,
                        plex_item_key=plex_item_key,
                        plex_item_type=plex_item_type,
                        notified_at=datetime.utcnow(),
                    )
                )
            except Exception:
                # Duplicate entry - already tracked
                pass

    def cleanup_old_plex_tracking(self, days: int = 7):
        """
        Delete notification tracking entries older than N days (privacy).

        Args:
            days: Number of days to retain (default: 7)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.plex_notification_tracking).where(
                    self.plex_notification_tracking.c.created_at < cutoff_date
                )
            )

            deleted_count = result.rowcount
            if deleted_count > 0:
                print(
                    f"[PLEX] Cleaned up {deleted_count} old notification tracking entries"
                )

    def delete_all_plex_tracking(self, user_id: int):
        """
        Delete all notification tracking for a user.

        Called during disconnect flow.

        Args:
            user_id: User ID
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.plex_notification_tracking).where(
                    self.plex_notification_tracking.c.user_id == user_id
                )
            )
