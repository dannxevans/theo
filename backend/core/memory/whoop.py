"""
WHOOP Integration Operations.

Handles WHOOP OAuth credentials, settings, and data tracking storage.
"""

from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, insert

from .base import BaseMemoryOperations


class WHOOPOperations(BaseMemoryOperations):
    """WHOOP integration management operations."""

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
            # Check if exists
            existing = conn.execute(
                select(self.whoop_credentials.c.id)
                .where(self.whoop_credentials.c.user_id == user_id)
            ).fetchone()

            if existing:
                # Update
                conn.execute(
                    update(self.whoop_credentials)
                    .where(self.whoop_credentials.c.user_id == user_id)
                    .values(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_type=token_type,
                        expires_at=expires_at,
                        whoop_user_id=whoop_user_id,
                        is_valid=True,
                        last_refreshed_at=datetime.utcnow(),
                        last_error=None,
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                # Insert
                conn.execute(
                    insert(self.whoop_credentials).values(
                        user_id=user_id,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        token_type=token_type,
                        expires_at=expires_at,
                        whoop_user_id=whoop_user_id,
                        is_valid=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )

    def get_whoop_credentials(self, user_id):
        """
        Get WHOOP credentials for a user.

        Args:
            user_id: User ID

        Returns:
            dict: WHOOP credentials or None if not found
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def update_whoop_token(self, user_id, access_token, expires_at):
        """
        Update WHOOP access token after refresh.

        Args:
            user_id: User ID
            access_token: New access token
            expires_at: New expiration datetime
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
                .values(
                    access_token=access_token,
                    expires_at=expires_at,
                    is_valid=True,
                    last_refreshed_at=datetime.utcnow(),
                    last_error=None,
                    updated_at=datetime.utcnow()
                )
            )

    def invalidate_whoop_credentials(self, user_id, error=None):
        """
        Mark WHOOP credentials as invalid.

        Args:
            user_id: User ID
            error: Optional error message
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.whoop_credentials)
                .where(self.whoop_credentials.c.user_id == user_id)
                .values(
                    is_valid=False,
                    last_error=error,
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

    # =============================
    # WHOOP Settings
    # =============================

    def get_whoop_settings(self, user_id):
        """
        Get WHOOP notification settings for a user.

        Args:
            user_id: User ID

        Returns:
            dict: WHOOP settings with defaults if not found
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.whoop_settings)
                .where(self.whoop_settings.c.user_id == user_id)
            ).fetchone()

            if row:
                return dict(row._mapping)
            else:
                # Return defaults
                return {
                    'user_id': user_id,
                    'sleep_notifications_enabled': True,
                    'workout_notifications_enabled': True,
                    'check_frequency_minutes': 30,
                    'quiet_hours_enabled': False,
                    'quiet_hours_start': None,
                    'quiet_hours_end': None
                }

    def update_whoop_settings(self, user_id, settings):
        """
        Update WHOOP notification settings.

        Args:
            user_id: User ID
            settings: Dictionary of settings to update
        """
        with self.engine.begin() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.whoop_settings.c.id)
                .where(self.whoop_settings.c.user_id == user_id)
            ).fetchone()

            if existing:
                # Update
                update_values = {**settings, 'updated_at': datetime.utcnow()}
                conn.execute(
                    update(self.whoop_settings)
                    .where(self.whoop_settings.c.user_id == user_id)
                    .values(**update_values)
                )
            else:
                # Insert with defaults
                insert_values = {
                    'user_id': user_id,
                    'sleep_notifications_enabled': settings.get('sleep_notifications_enabled', True),
                    'workout_notifications_enabled': settings.get('workout_notifications_enabled', True),
                    'check_frequency_minutes': settings.get('check_frequency_minutes', 30),
                    'quiet_hours_enabled': settings.get('quiet_hours_enabled', False),
                    'quiet_hours_start': settings.get('quiet_hours_start'),
                    'quiet_hours_end': settings.get('quiet_hours_end'),
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                }
                conn.execute(
                    insert(self.whoop_settings).values(**insert_values)
                )

    # =============================
    # WHOOP Data Tracking
    # =============================

    def track_whoop_data(self, user_id, data_type, whoop_id):
        """
        Track that we've processed a WHOOP record.

        Args:
            user_id: User ID
            data_type: Type of data ('sleep', 'workout', 'recovery')
            whoop_id: WHOOP's ID for the record

        Returns:
            bool: True if inserted, False if already exists
        """
        with self.engine.begin() as conn:
            # Check if already tracked
            existing = conn.execute(
                select(self.whoop_data_tracking.c.id)
                .where(self.whoop_data_tracking.c.whoop_id == whoop_id)
            ).fetchone()

            if existing:
                return False

            # Insert new tracking record
            conn.execute(
                insert(self.whoop_data_tracking).values(
                    user_id=user_id,
                    data_type=data_type,
                    whoop_id=whoop_id,
                    notified_at=datetime.utcnow(),
                    created_at=datetime.utcnow()
                )
            )
            return True

    def is_whoop_data_tracked(self, whoop_id):
        """
        Check if we've already processed this WHOOP record.

        Args:
            whoop_id: WHOOP's ID for the record

        Returns:
            bool: True if already tracked
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.whoop_data_tracking.c.id)
                .where(self.whoop_data_tracking.c.whoop_id == whoop_id)
            ).fetchone()
            return row is not None

    def get_tracked_whoop_data(self, user_id, data_type=None, days=7):
        """
        Get list of tracked WHOOP IDs for a user.

        Args:
            user_id: User ID
            data_type: Optional data type filter ('sleep', 'workout', 'recovery')
            days: Number of days to look back (default 7)

        Returns:
            list: List of WHOOP IDs
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)

        with self.engine.begin() as conn:
            query = select(self.whoop_data_tracking.c.whoop_id).where(
                self.whoop_data_tracking.c.user_id == user_id,
                self.whoop_data_tracking.c.created_at >= cutoff_date
            )

            if data_type:
                query = query.where(self.whoop_data_tracking.c.data_type == data_type)

            rows = conn.execute(query).fetchall()
            return [row[0] for row in rows]

    def cleanup_old_whoop_tracking(self, days=7):
        """
        Delete tracking records older than N days for privacy.

        Args:
            days: Number of days to keep (default 7)

        Returns:
            int: Number of records deleted
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
