"""
Service provider operations module.

Handles:
- External service provider management (calendar, email, etc.)
- Service provider CRUD operations
- Capability and authentication tracking
- Preferred provider selection
"""

from datetime import datetime
from sqlalchemy import select, delete, insert, update

from .base import BaseMemoryOperations


class ServiceProviderOperations(BaseMemoryOperations):
    """Operations for managing external service providers."""

    # =============================
    # Service Provider CRUD
    # =============================

    def store_service_provider(self, user_id, name, category, provider_type, **kwargs):
        """
        Store a new service provider.

        Args:
            user_id: User identifier
            name: Provider name
            category: Category (e.g., "calendar", "email")
            provider_type: Provider type (e.g., "m365", "google")
            **kwargs: Additional fields (capabilities, api_base_url, auth_method, etc.)

        Returns:
            Provider ID
        """
        with self._get_connection() as conn:
            result = conn.execute(
                insert(self.service_providers).values(
                    user_id=user_id,
                    name=name,
                    category=category,
                    provider_type=provider_type,
                    capabilities=kwargs.get("capabilities"),
                    api_base_url=kwargs.get("api_base_url"),
                    auth_method=kwargs.get("auth_method"),
                    access_token=kwargs.get("access_token"),
                    refresh_token=kwargs.get("refresh_token"),
                    token_expires_at=kwargs.get("token_expires_at"),
                    trust_level=kwargs.get("trust_level", "manual"),
                    booking_method=kwargs.get("booking_method"),
                    preferred_for_category=kwargs.get("preferred_for_category", False),
                    is_enabled=True,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    additional_metadata=kwargs.get("additional_metadata"),
                )
            )
            return result.lastrowid

    def get_service_providers(self, user_id, category=None):
        """
        Get service providers for a user.

        Args:
            user_id: User identifier
            category: Optional category filter

        Returns:
            List of service provider dictionaries
        """
        with self._get_connection() as conn:
            query = select(self.service_providers).where(
                self.service_providers.c.user_id == user_id
            )

            if category:
                query = query.where(self.service_providers.c.category == category)

            rows = conn.execute(query).fetchall()
            return [dict(row._mapping) for row in rows]

    def get_service_provider(self, provider_id):
        """
        Get a single service provider by ID.

        Args:
            provider_id: Provider identifier

        Returns:
            Service provider dictionary or None
        """
        with self._get_connection() as conn:
            row = conn.execute(
                select(self.service_providers).where(
                    self.service_providers.c.id == provider_id
                )
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_preferred_provider(self, user_id, category):
        """
        Get the preferred provider for a category.
        Falls back to any provider in that category if no preferred one exists.

        Args:
            user_id: User identifier
            category: Category to search

        Returns:
            Service provider dictionary or None
        """
        with self._get_connection() as conn:
            # First, try to get a preferred provider
            row = conn.execute(
                select(self.service_providers)
                .where(self.service_providers.c.user_id == user_id)
                .where(self.service_providers.c.category == category)
                .where(self.service_providers.c.preferred_for_category == True)
                .limit(1)
            ).fetchone()

            if row:
                return dict(row._mapping)

            # Fall back to any provider in this category
            row = conn.execute(
                select(self.service_providers)
                .where(self.service_providers.c.user_id == user_id)
                .where(self.service_providers.c.category == category)
                .limit(1)
            ).fetchone()

            return dict(row._mapping) if row else None

    def update_service_provider(self, provider_id, **kwargs):
        """
        Update a service provider.

        Args:
            provider_id: Provider identifier
            **kwargs: Fields to update
        """
        with self._get_connection() as conn:
            update_values = {k: v for k, v in kwargs.items() if v is not None}
            update_values["updated_at"] = datetime.utcnow()

            conn.execute(
                update(self.service_providers)
                .where(self.service_providers.c.id == provider_id)
                .values(**update_values)
            )

    def delete_service_provider(self, provider_id, user_id):
        """
        Delete a service provider (with user ownership check).

        Args:
            provider_id: Provider identifier
            user_id: User identifier for ownership verification
        """
        with self._get_connection() as conn:
            conn.execute(
                delete(self.service_providers)
                .where(self.service_providers.c.id == provider_id)
                .where(self.service_providers.c.user_id == user_id)
            )
