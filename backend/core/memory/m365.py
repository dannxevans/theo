"""
M365 Credentials Operations.

Handles Microsoft 365 OAuth credentials storage and management.
"""

from datetime import datetime
from sqlalchemy import select, update, delete, insert

from .base import BaseMemoryOperations


class M365Operations(BaseMemoryOperations):
    """M365 credentials management operations."""

    def store_m365_credentials(self, user_id, access_token, refresh_token,
                                expires_at, scope=None, tenant_id=None, upn=None):
        """
        Store M365 OAuth credentials.

        Args:
            user_id: User ID
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_at: Token expiration datetime
            scope: OAuth scope string
            tenant_id: Azure AD tenant ID
            upn: User principal name (email)
        """
        with self.engine.begin() as conn:
            # Check if exists
            existing = conn.execute(
                select(self.m365_credentials.c.id)
                .where(self.m365_credentials.c.user_id == user_id)
            ).fetchone()

            if existing:
                # Update
                conn.execute(
                    update(self.m365_credentials)
                    .where(self.m365_credentials.c.user_id == user_id)
                    .values(
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_at=expires_at,
                        scope=scope,
                        tenant_id=tenant_id,
                        user_principal_name=upn,
                        is_valid=True,
                        last_refreshed_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )
            else:
                # Insert
                conn.execute(
                    insert(self.m365_credentials).values(
                        user_id=user_id,
                        access_token=access_token,
                        refresh_token=refresh_token,
                        expires_at=expires_at,
                        scope=scope,
                        tenant_id=tenant_id,
                        user_principal_name=upn,
                        is_valid=True,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                )

    def get_m365_credentials(self, user_id):
        """
        Get M365 credentials for a user.

        Args:
            user_id: User ID

        Returns:
            dict: M365 credentials or None if not found
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.m365_credentials)
                .where(self.m365_credentials.c.user_id == user_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def invalidate_m365_credentials(self, user_id, error=None):
        """
        Mark M365 credentials as invalid.

        Args:
            user_id: User ID
            error: Optional error message
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.m365_credentials)
                .where(self.m365_credentials.c.user_id == user_id)
                .values(
                    is_valid=False,
                    last_error=error,
                    updated_at=datetime.utcnow()
                )
            )

    def delete_m365_credentials(self, user_id):
        """
        Delete M365 credentials for a user.

        Args:
            user_id: User ID
        """
        with self.engine.begin() as conn:
            conn.execute(
                delete(self.m365_credentials)
                .where(self.m365_credentials.c.user_id == user_id)
            )
