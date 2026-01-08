"""
WHOOP Integration Operations.

Handles WHOOP OAuth credentials, settings, and data tracking storage.
"""

from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, insert

from .base import BaseMemoryOperations


class WHOOPOperations(BaseMemoryOperations):
    """WHOOP integration management operations."""

    def _get_user_preferences(self, user_id):
        """
        Get all user preferences (for OAuth config lookup).

        Args:
            user_id: User ID

        Returns:
            dict: User preferences
        """
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.preferences)
                .where(self.preferences.c.user_id == str(user_id))
            ).fetchall()
            return {row.key: row.value for row in rows} if rows else {}

    def store_whoop_credentials(self, user_id, access_token, refresh_token,
                                 expires_at, whoop_user_id, token_type="Bearer"):
        """
        Store WHOOP OAuth credentials.

        Args:
            user_id: User ID
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_at: Token expiration datetime
            whoop_user_id: WHOOP's internal user ID
            token_type: Token type (default: Bearer)
        """
        with self.engine.begin() as conn:
            # Try to update first
            result = conn.execute(
                update(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
                .values(
                    access_token=access_token,
                    refresh_token=refresh_token,
                    expires_at=expires_at,
                    whoop_user_id=whoop_user_id,
                    token_type=token_type,
                    is_valid=True,
                    last_refreshed_at=datetime.utcnow(),
                    last_error=None,
                    updated_at=datetime.utcnow()
                )
            )

            # If no rows affected, insert instead
            if result.rowcount == 0:
                conn.execute(
                    insert(self.whoop_credentials).values(
                        user_id=user_id,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_at=expires_at,
                        whoop_user_id=whoop_user_id,
                        token_type=token_type,
                        is_valid=True,
                        last_refreshed_at=datetime.utcnow()
                    )
                )

    def get_whoop_credentials(self, user_id):
        """
        Get WHOOP credentials for a user.

        Args:
            user_id: User ID

        Returns:
            dict: Credentials or None
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                select(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
            ).fetchone()

            if not result:
                return None

            return {
                'user_id': result.user_id,
                'access_token': result.access_token,
                'refresh_token': result.refresh_token,
                'expires_at': result.expires_at,
                'token_type': result.token_type,
                'whoop_user_id': result.whoop_user_id,
                'is_valid': bool(result.is_valid),
                'last_refreshed_at': result.last_refreshed_at,
                'last_error': result.last_error
            }

    def update_whoop_token(self, user_id, access_token, expires_at, refresh_token=None):
        """
        Update WHOOP access token (after refresh).

        Args:
            user_id: User ID
            access_token: New access token
            expires_at: New expiration datetime
            refresh_token: New refresh token (if rotated), optional
        """
        with self.engine.begin() as conn:
            values = {
                'access_token': access_token,
                'expires_at': expires_at,
                'is_valid': True,
                'last_refreshed_at': datetime.utcnow(),
                'last_error': None,
                'updated_at': datetime.utcnow()
            }

            # Update refresh token if provided (token rotation)
            if refresh_token:
                values['refresh_token'] = refresh_token

            conn.execute(
                update(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
                .values(**values)
            )

    def invalidate_whoop_credentials(self, user_id, error_message):
        """
        Mark WHOOP credentials as invalid.

        Args:
            user_id: User ID
            error_message: Error message to store
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
                .values(
                    is_valid=False,
                    last_error=error_message,
                    updated_at=datetime.utcnow()
                )
            )

    def delete_whoop_credentials(self, user_id):
        """
        Delete WHOOP credentials for a user.

        Args:
            user_id: User ID
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
            )

    # Thread-safe token refresh with database locking
    _refresh_lock_cache = {}  # In-memory lock per user_id

    def refresh_whoop_token_if_needed(self, user_id):
        """
        Check if WHOOP token is expired and refresh if needed.

        Uses an in-memory lock to prevent concurrent refresh attempts
        from the same process, which would cause WHOOP API errors
        (refresh tokens can only be used once).

        Args:
            user_id: User ID

        Returns:
            dict: Current credentials (refreshed if needed) or None
        """
        from auth.whoop_oauth import WHOOPOAuth
        import logging
        import threading

        logger = logging.getLogger(__name__)

        # Get or create lock for this user
        if user_id not in self._refresh_lock_cache:
            self._refresh_lock_cache[user_id] = threading.Lock()

        lock = self._refresh_lock_cache[user_id]

        # Acquire lock to prevent concurrent refreshes for same user
        with lock:
            credentials = self.get_whoop_credentials(user_id)
            if not credentials or not credentials.get('is_valid'):
                return None

            # Check if token is expired or will expire in next 5 minutes
            expires_at = credentials.get('expires_at')
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)

            buffer_time = timedelta(minutes=5)
            if datetime.utcnow() + buffer_time < expires_at:
                # Token still valid
                return credentials

            # Token expired or about to expire - refresh it
            refresh_token = credentials.get('refresh_token')
            if not refresh_token:
                logger.warning(f"[WHOOP_MEMORY] No refresh token for user {user_id}, cannot refresh")
                self.invalidate_whoop_credentials(user_id, "No refresh token available")
                return None

            logger.info(f"[WHOOP_MEMORY] Refreshing expired token for user {user_id}")

            # Create a minimal wrapper that provides get_all() method for OAuth config lookup
            class PreferenceWrapper:
                def __init__(self, prefs):
                    self._prefs = prefs
                def get_all(self, user_id):
                    return self._prefs

            # Get user preferences for OAuth config
            prefs = self._get_user_preferences(user_id)
            wrapper = PreferenceWrapper(prefs)

            # Attempt token refresh
            new_tokens = WHOOPOAuth.refresh_access_token(refresh_token, user_id, wrapper)
            if not new_tokens:
                logger.error(f"[WHOOP_MEMORY] Token refresh failed for user {user_id}")
                self.invalidate_whoop_credentials(user_id, "Token refresh failed")
                return None

            # Update stored credentials
            self.update_whoop_token(
                user_id,
                new_tokens['access_token'],
                new_tokens['expires_at'],
                new_tokens.get('refresh_token')  # May be rotated
            )

            logger.info(f"[WHOOP_MEMORY] ✓ Token refreshed successfully for user {user_id}")

            # Return updated credentials
            return self.get_whoop_credentials(user_id)

    # =============================
    # WHOOP Settings
    # =============================

    def get_whoop_settings(self, user_id):
        """
        Get WHOOP notification settings for a user.

        Args:
            user_id: User ID

        Returns:
            dict: Settings with defaults if not set
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                select(self.whoop_settings)
                .where(self.whoop_settings.c.user_id == user_id)
            ).fetchone()

            if not result:
                # Return defaults
                return {
                    'sleep_notifications_enabled': True,
                    'workout_notifications_enabled': True,
                    'stress_notifications_enabled': True,
                    'stress_notification_time': '14:00',
                    'check_frequency_minutes': 30,
                    'quiet_hours_enabled': False,
                    'quiet_hours_start': None,
                    'quiet_hours_end': None
                }

            return {
                'sleep_notifications_enabled': bool(result.sleep_notifications_enabled),
                'workout_notifications_enabled': bool(result.workout_notifications_enabled),
                'stress_notifications_enabled': bool(result.stress_notifications_enabled),
                'stress_notification_time': result.stress_notification_time,
                'check_frequency_minutes': result.check_frequency_minutes,
                'quiet_hours_enabled': bool(result.quiet_hours_enabled),
                'quiet_hours_start': result.quiet_hours_start,
                'quiet_hours_end': result.quiet_hours_end
            }

    def update_whoop_settings(self, user_id, **settings):
        """
        Update WHOOP notification settings.

        Args:
            user_id: User ID
            **settings: Settings to update (must be whitelisted)
        """
        # Whitelist of allowed settings
        allowed_fields = {
            'sleep_notifications_enabled',
            'workout_notifications_enabled',
            'stress_notifications_enabled',
            'stress_notification_time',
            'check_frequency_minutes',
            'quiet_hours_enabled',
            'quiet_hours_start',
            'quiet_hours_end'
        }

        # Filter to only allowed fields
        filtered_settings = {k: v for k, v in settings.items() if k in allowed_fields}

        if not filtered_settings:
            return

        with self.engine.begin() as conn:
            # Try to update first
            result = conn.execute(
                update(self.whoop_settings)
                .where(self.whoop_settings.c.user_id == user_id)
                .values(updated_at=datetime.utcnow(), **filtered_settings)
            )

            # If no rows affected, insert with defaults + updates
            if result.rowcount == 0:
                defaults = {
                    'user_id': user_id,
                    'sleep_notifications_enabled': True,
                    'workout_notifications_enabled': True,
                    'stress_notifications_enabled': True,
                    'stress_notification_time': '14:00',
                    'check_frequency_minutes': 30,
                    'quiet_hours_enabled': False
                }
                defaults.update(filtered_settings)
                conn.execute(insert(self.whoop_settings).values(**defaults))

    # =============================
    # WHOOP Data Tracking
    # =============================

    def track_whoop_data(self, user_id, data_type, whoop_id):
        """
        Track that a WHOOP data item has been processed.

        Args:
            user_id: User ID
            data_type: Type (sleep, workout, recovery)
            whoop_id: WHOOP's ID for this data item
        """
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.whoop_data_tracking).values(
                    user_id=user_id,
                    data_type=data_type,
                    whoop_id=whoop_id,
                    notified_at=datetime.utcnow()
                )
            )

    def is_whoop_data_tracked(self, whoop_id):
        """
        Check if a WHOOP data item has already been tracked.

        Args:
            whoop_id: WHOOP's ID

        Returns:
            bool: True if already tracked
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                select(self.whoop_data_tracking)
                .where(self.whoop_data_tracking.c.whoop_id == whoop_id)
            ).fetchone()

            return result is not None

    def get_tracked_whoop_data(self, user_id, data_type, since_date=None):
        """
        Get tracked WHOOP data IDs.

        Args:
            user_id: User ID
            data_type: Type (sleep, workout, recovery)
            since_date: Optional cutoff date

        Returns:
            list: WHOOP IDs
        """
        with self.engine.begin() as conn:
            query = (
                select(self.whoop_data_tracking.c.whoop_id)
                .where(self.whoop_data_tracking.c.user_id == user_id)
                .where(self.whoop_data_tracking.c.data_type == data_type)
            )

            if since_date:
                query = query.where(self.whoop_data_tracking.c.notified_at >= since_date)

            result = conn.execute(query).fetchall()
            return [row[0] for row in result]

    def cleanup_old_whoop_tracking(self, days=7):
        """
        Delete tracking records older than N days (privacy retention).

        Args:
            days: Number of days to keep (default: 7)
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with self.engine.begin() as conn:
            result = conn.execute(
                delete(self.whoop_data_tracking)
                .where(self.whoop_data_tracking.c.created_at < cutoff_date)
            )

            return result.rowcount

    def delete_all_whoop_data(self, user_id):
        """
        Delete all WHOOP data for a user (on disconnect).

        Args:
            user_id: User ID
        """
        with self.engine.begin() as conn:
            # Delete credentials
            conn.execute(
                delete(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
            )

            # Delete settings
            conn.execute(
                delete(self.whoop_settings)
                .where(self.whoop_settings.c.user_id == user_id)
            )

            # Delete tracking data
            conn.execute(
                delete(self.whoop_data_tracking)
                .where(self.whoop_data_tracking.c.user_id == user_id)
            )
