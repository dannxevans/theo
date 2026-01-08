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
from core.user_utils import normalize_user_id


class UserOperations(BaseMemoryOperations):
    """Operations for managing users and authentication."""

    # =============================
    # User Management
    # =============================

    def create_user(self, username, password_hash, is_admin=False, name=None, email=None):
        """
        Create a new user.

        Args:
            username: Unique username
            password_hash: Hashed password
            is_admin: Whether user has admin privileges
            name: Optional full name
            email: Optional email address

        Returns:
            Created user ID
        """
        with self._get_connection() as conn:
            result = conn.execute(
                insert(self.users).values(
                    username=username,
                    password_hash=password_hash,
                    name=name,
                    email=email,
                    is_admin=is_admin,
                    is_enabled=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            user_id = result.lastrowid

            # Create Archive folder for new user
            try:
                conn.execute(
                    insert(self.session_folders).values(
                        name="Archive",
                        user_id=user_id,
                        is_system=True,
                        sort_order=-1,
                        collapsed=False,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                )
            except Exception as e:
                # Archive folder might already exist (e.g., from migration)
                print(f"Note: Could not create Archive folder for user {user_id}: {e}")

            return user_id

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

        user_id = normalize_user_id(user_id)

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

        user_id = normalize_user_id(user_id)

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

        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(
                    is_enabled=False,
                    updated_at=datetime.utcnow(),
                )
            )

    def list_all_users(self, include_disabled=False):
        """
        Get all users ordered by username.

        Args:
            include_disabled: Include disabled users (default: False)

        Returns:
            List of user dictionaries
        """
        with self._get_connection() as conn:
            query = select(self.users)
            if not include_disabled:
                query = query.where(self.users.c.is_enabled == True)
            query = query.order_by(self.users.c.username)

            rows = conn.execute(query).fetchall()
            return [dict(row._mapping) for row in rows]

    def update_user(self, user_id, updates):
        """
        Update user fields.

        Args:
            user_id: User ID to update
            updates: Dict with optional keys: username, name, email, is_admin, is_enabled

        Returns:
            Updated user dictionary

        Raises:
            ValueError: If user not found or username conflict
        """
        user_id = normalize_user_id(user_id)

        # Check user exists
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        # Validate updates
        allowed_fields = {'username', 'name', 'email', 'is_admin', 'is_enabled'}
        invalid_fields = set(updates.keys()) - allowed_fields
        if invalid_fields:
            raise ValueError(f"Invalid fields: {invalid_fields}")

        # Check username uniqueness if changing
        if 'username' in updates and updates['username'] != user['username']:
            existing = self.get_user_by_username(updates['username'])
            if existing:
                raise ValueError(f"Username '{updates['username']}' already exists")

        # Build update values
        update_values = {**updates, 'updated_at': datetime.utcnow()}

        with self._get_connection() as conn:
            conn.execute(
                update(self.users)
                .where(self.users.c.id == user_id)
                .values(**update_values)
            )

        return self.get_user_by_id(user_id)

    def enable_user(self, user_id):
        """
        Enable disabled user account.

        Args:
            user_id: User ID to enable

        Returns:
            Updated user dictionary
        """
        return self.update_user(user_id, {'is_enabled': True})

    def reset_user_password(self, user_id, new_password_hash):
        """
        Admin function to reset user password.

        Invalidates all active sessions for security.

        Args:
            user_id: User ID
            new_password_hash: Bcrypt hash of new password

        Returns:
            Updated user dictionary

        Raises:
            ValueError: If user not found
        """
        user_id = normalize_user_id(user_id)

        # Update password
        self.update_user_password(user_id, new_password_hash)

        # Invalidate all sessions for this user
        with self._get_connection() as conn:
            conn.execute(
                delete(self.auth_sessions)
                .where(self.auth_sessions.c.user_id == user_id)
            )

        return self.get_user_by_id(user_id)

    def get_user_activity_stats(self, user_id):
        """
        Get user activity metrics.

        Args:
            user_id: User ID

        Returns:
            Dictionary with:
            - session_count: Active sessions
            - api_key_count: Active API keys
            - last_activity: Most recent session activity
            - memory_count: Conversation memory count
            - created_at: Account creation date
        """
        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            # Session count (active only)
            session_count = conn.execute(
                select(self.auth_sessions)
                .where(self.auth_sessions.c.user_id == user_id)
                .where(self.auth_sessions.c.expires_at > datetime.utcnow())
            ).fetchall()

            # API key count (active only - not revoked and not expired)
            api_key_rows = conn.execute(
                select(self.api_keys)
                .where(self.api_keys.c.user_id == user_id)
                .where(self.api_keys.c.is_revoked == False)
            ).fetchall()

            # Filter out expired keys
            now = datetime.utcnow()
            active_api_keys = [
                k for k in api_key_rows
                if k.expires_at is None or k.expires_at > now
            ]

            # Last activity (from sessions)
            last_activity_row = conn.execute(
                select(self.auth_sessions.c.last_activity_at)
                .where(self.auth_sessions.c.user_id == user_id)
                .order_by(self.auth_sessions.c.last_activity_at.desc())
                .limit(1)
            ).fetchone()

            # Memory count
            memory_count_row = conn.execute(
                select(self.memories)
                .where(self.memories.c.user_id == user_id)
            ).fetchall()

            # User creation date
            user = self.get_user_by_id(user_id)

            return {
                'session_count': len(session_count),
                'api_key_count': len(active_api_keys),
                'last_activity': last_activity_row[0] if last_activity_row else None,
                'memory_count': len(memory_count_row),
                'created_at': user['created_at'] if user else None
            }

    def count_admins(self):
        """
        Count total number of enabled admin users.

        Used to prevent demoting the last admin.

        Returns:
            Number of enabled admin users
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.users)
                .where(self.users.c.is_admin == True)
                .where(self.users.c.is_enabled == True)
            ).fetchall()
            return len(rows)

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
        now = datetime.utcnow()
        with self._get_connection() as conn:
            conn.execute(
                insert(self.auth_sessions).values(
                    id=session_id,
                    user_id=user_id,
                    created_at=now,
                    expires_at=expires_at,
                    last_activity_at=now,
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

    def update_session_activity(self, session_id):
        """
        Update the last activity timestamp for a session.

        Args:
            session_id: Session identifier
        """
        with self._get_connection() as conn:
            conn.execute(
                update(self.auth_sessions)
                .where(self.auth_sessions.c.id == session_id)
                .values(last_activity_at=datetime.utcnow())
            )

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

        user_id = normalize_user_id(user_id)

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

    # =============================
    # API Key Management
    # =============================

    def create_api_key(self, user_id, name, key_hash, expires_at=None):
        """
        Create a new API key for a user.

        Args:
            user_id: User ID
            name: User-friendly label for the key
            key_hash: Bcrypt hash of the API key
            expires_at: Optional expiration datetime

        Returns:
            Created API key ID
        """
        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            result = conn.execute(
                insert(self.api_keys).values(
                    user_id=user_id,
                    name=name,
                    key_hash=key_hash,
                    expires_at=expires_at,
                    created_at=datetime.utcnow(),
                    is_revoked=False,
                )
            )
            return result.lastrowid

    def get_api_key_by_id(self, key_id, user_id=None):
        """
        Get API key by ID.

        Args:
            key_id: API key ID
            user_id: Optional user ID to verify ownership

        Returns:
            API key dictionary or None
        """
        with self._get_connection() as conn:
            query = select(self.api_keys).where(self.api_keys.c.id == key_id)

            if user_id is not None:
                user_id = normalize_user_id(user_id)
                query = query.where(self.api_keys.c.user_id == user_id)

            row = conn.execute(query).fetchone()
            return dict(row._mapping) if row else None

    def find_api_key_by_hash(self, key_hash):
        """
        Find API key by its hash (for authentication).

        Args:
            key_hash: The hash to search for

        Returns:
            API key dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.api_keys)
                .where(self.api_keys.c.key_hash == key_hash)
            ).fetchone()
            return dict(row._mapping) if row else None

    def list_user_api_keys(self, user_id):
        """
        List all API keys for a user.

        Args:
            user_id: User ID

        Returns:
            List of API key dictionaries (without hashes)
        """
        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            rows = conn.execute(
                select(self.api_keys)
                .where(self.api_keys.c.user_id == user_id)
                .order_by(self.api_keys.c.created_at.desc())
            ).fetchall()

            # Return keys without hashes for security
            return [
                {
                    "id": row.id,
                    "user_id": row.user_id,
                    "name": row.name,
                    "last_used_at": row.last_used_at,
                    "created_at": row.created_at,
                    "expires_at": row.expires_at,
                    "is_revoked": row.is_revoked,
                    "revoked_at": row.revoked_at,
                }
                for row in rows
            ]

    def update_api_key_last_used(self, key_id):
        """
        Update the last used timestamp for an API key.

        Args:
            key_id: API key ID
        """
        with self._get_connection() as conn:
            conn.execute(
                update(self.api_keys)
                .where(self.api_keys.c.id == key_id)
                .values(last_used_at=datetime.utcnow())
            )

    def revoke_api_key(self, key_id, user_id):
        """
        Revoke an API key (soft delete).

        Args:
            key_id: API key ID
            user_id: User ID (for ownership verification)

        Returns:
            True if key was revoked, False if not found or not owned by user
        """
        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            result = conn.execute(
                update(self.api_keys)
                .where(self.api_keys.c.id == key_id)
                .where(self.api_keys.c.user_id == user_id)
                .values(
                    is_revoked=True,
                    revoked_at=datetime.utcnow(),
                )
            )
            return result.rowcount > 0

    def delete_api_key(self, key_id, user_id):
        """
        Permanently delete an API key.

        Args:
            key_id: API key ID
            user_id: User ID (for ownership verification)

        Returns:
            True if key was deleted, False if not found or not owned by user
        """
        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            result = conn.execute(
                delete(self.api_keys)
                .where(self.api_keys.c.id == key_id)
                .where(self.api_keys.c.user_id == user_id)
            )
            return result.rowcount > 0

    def update_api_key_name(self, key_id, user_id, new_name):
        """
        Update the name of an API key.

        Args:
            key_id: API key ID
            user_id: User ID (for ownership verification)
            new_name: New name for the key

        Returns:
            True if key was updated, False if not found or not owned by user
        """
        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            result = conn.execute(
                update(self.api_keys)
                .where(self.api_keys.c.id == key_id)
                .where(self.api_keys.c.user_id == user_id)
                .values(name=new_name)
            )
            return result.rowcount > 0
