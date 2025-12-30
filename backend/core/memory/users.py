"""
User and authentication operations module.

Handles:
- User CRUD operations
- Authentication session management
- Debug settings
"""

from datetime import datetime
from sqlalchemy import select, delete, insert, update

from .base import BaseMemoryOperations


class UserOperations(BaseMemoryOperations):
    """Operations for managing users and authentication."""

    # =============================
    # User Management
    # =============================

    def create_user(self, username, password_hash, is_admin=False):
        """
        Create a new user.

        Args:
            username: Unique username
            password_hash: Hashed password
            is_admin: Whether user has admin privileges

        Returns:
            Created user ID
        """
        with self._get_connection() as conn:
            result = conn.execute(
                insert(self.users).values(
                    username=username,
                    password_hash=password_hash,
                    is_admin=is_admin,
                    is_enabled=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            return result.lastrowid

    def get_user_by_username(self, username):
        """
        Get user by username.

        Args:
            username: Username to look up

        Returns:
            User dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.users)
                .where(self.users.c.username == username)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_user_by_id(self, user_id):
        """
        Get user by ID.

        Args:
            user_id: User ID to look up

        Returns:
            User dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.users)
                .where(self.users.c.id == user_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def update_user_password(self, user_id, password_hash):
        """
        Update user password.

        Args:
            user_id: User ID
            password_hash: New hashed password
        """
        with self._get_connection() as conn:
            conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(
                    password_hash=password_hash,
                    updated_at=datetime.utcnow(),
                )
            )

    def disable_user(self, user_id):
        """
        Disable a user account.

        Args:
            user_id: User ID to disable
        """
        with self._get_connection() as conn:
            conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(
                    is_enabled=False,
                    updated_at=datetime.utcnow(),
                )
            )

    # =============================
    # Authentication Sessions
    # =============================

    def create_auth_session(self, session_id, user_id, expires_at):
        """
        Create an authentication session.

        Args:
            session_id: Session identifier
            user_id: User ID
            expires_at: Session expiration datetime
        """
        with self._get_connection() as conn:
            conn.execute(
                insert(self.auth_sessions).values(
                    id=session_id,
                    user_id=user_id,
                    created_at=datetime.utcnow(),
                    expires_at=expires_at,
                )
            )

    def get_auth_session(self, session_id):
        """
        Get authentication session.

        Args:
            session_id: Session identifier

        Returns:
            Session dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.auth_sessions)
                .where(self.auth_sessions.c.id == session_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def delete_auth_session(self, session_id):
        """
        Delete authentication session (logout).

        Args:
            session_id: Session identifier to delete
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.auth_sessions)
                .where(self.auth_sessions.c.id == session_id)
            )

    def cleanup_expired_sessions(self):
        """
        Remove expired authentication sessions.

        Returns:
            Number of sessions deleted
        """
        with self._get_connection() as conn:
            result = conn.execute(
                delete(self.auth_sessions)
                .where(self.auth_sessions.c.expires_at < datetime.utcnow())
            )
            return result.rowcount

    # =============================
    # Debug Settings
    # =============================

    def set_debug_enabled(self, user_id, enabled: bool):
        """
        Set debug enabled flag for a user.

        Args:
            user_id: User identifier
            enabled: Whether debug mode is enabled
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.debug_settings)
                .where(self.debug_settings.c.user_id == user_id)
            )
            conn.execute(
                insert(self.debug_settings).values(
                    user_id=user_id,
                    enabled=enabled,
                    updated_at=datetime.utcnow(),
                )
            )

    def is_debug_enabled(self, user_id) -> bool:
        """
        Check if debug logging is enabled for a user.

        Args:
            user_id: User identifier

        Returns:
            True if debug enabled, False otherwise
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.debug_settings.c.enabled)
                .where(self.debug_settings.c.user_id == user_id)
            ).fetchone()
            return bool(row.enabled) if row and row.enabled else False
