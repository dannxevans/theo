"""
Action Provider Registry.

Manages the lifecycle of action providers (similar to LLM provider registry).
Loads providers from database and provides lookup methods.
"""

from typing import Dict, Optional, List, Tuple
from actions.base import ActionProvider
from actions.m365_provider import M365Provider
from actions.plex_provider import PlexProvider
import logging


class ActionProviderRegistry:
    """
    Registry for action providers.

    Manages action provider lifecycle:
    - Loads providers from database
    - Instantiates provider classes with credentials
    - Provides lookup by ID or capability
    - Tracks provider health
    """

    def __init__(self, memory_store):
        """
        Initialize the registry.

        Args:
            memory_store: MemoryStore instance for database access
        """
        self.memory = memory_store
        self._providers: Dict[int, ActionProvider] = {}

    def load_providers(self, user_id: int):
        """
        Load all service providers for a user from database.
        Instantiate appropriate ActionProvider instances.

        Args:
            user_id: User ID to load providers for
        """
        service_providers = self.memory.get_service_providers(user_id)

        logging.info(f"[ACTION_REGISTRY] Loading providers for user {user_id}")

        for sp in service_providers:
            if not sp.get("is_enabled"):
                logging.debug(f"[ACTION_REGISTRY] Skipping disabled provider: {sp['name']}")
                continue

            provider_type = sp.get("provider_type")

            try:
                if provider_type == "m365":
                    # Load M365 credentials
                    creds = self.memory.get_m365_credentials(user_id)

                    if creds and creds.get("is_valid"):
                        provider = M365Provider(
                            access_token=creds["access_token"],
                            refresh_token=creds["refresh_token"],
                            expires_at=creds["expires_at"],
                            user_id=user_id,
                            memory_store=self.memory
                        )
                        self._providers[sp["id"]] = provider
                        logging.info(f"[ACTION_REGISTRY] Loaded M365 provider (ID: {sp['id']})")
                    else:
                        logging.warning(f"[ACTION_REGISTRY] M365 credentials invalid for provider {sp['id']}")

                elif provider_type == "plex":
                    # Load Plex credentials
                    creds = self.memory.get_plex_credentials(user_id)

                    if creds and creds.get("is_valid"):
                        provider = PlexProvider(
                            access_token=creds["access_token"],
                            server_url=creds["server_url"],
                            user_id=user_id,
                            memory_store=self.memory
                        )
                        self._providers[sp["id"]] = provider
                        logging.info(f"[ACTION_REGISTRY] Loaded Plex provider (ID: {sp['id']})")
                    else:
                        logging.warning(f"[ACTION_REGISTRY] Plex credentials invalid for provider {sp['id']}")

                # Add more provider types here as they're implemented
                # elif provider_type == "google_calendar":
                #     ...
                # elif provider_type == "booking_api":
                #     ...

                else:
                    logging.warning(f"[ACTION_REGISTRY] Unknown provider type: {provider_type}")

            except Exception as e:
                logging.error(f"[ACTION_REGISTRY] Failed to load provider {sp['id']}: {e}")

        logging.info(f"[ACTION_REGISTRY] Loaded {len(self._providers)} provider(s)")

    def get_provider(self, provider_id: int) -> Optional[ActionProvider]:
        """
        Get an action provider by ID.

        Args:
            provider_id: Service provider ID from database

        Returns:
            ActionProvider instance or None if not found
        """
        return self._providers.get(provider_id)

    def get_providers_by_capability(
        self,
        capability: str,
        user_id: int
    ) -> List[Tuple[int, ActionProvider]]:
        """
        Find all providers that support a specific capability.

        Args:
            capability: Action type (e.g., "read_calendar")
            user_id: User ID (for filtering)

        Returns:
            List of (provider_id, provider_instance) tuples

        Example:
            >>> registry = ActionProviderRegistry(memory)
            >>> registry.load_providers(user_id=1)
            >>> providers = registry.get_providers_by_capability("read_calendar", 1)
            >>> for provider_id, provider in providers:
            ...     events = provider.read_calendar(start, end)
        """
        result = []

        for provider_id, provider in self._providers.items():
            if provider.supports_action(capability):
                result.append((provider_id, provider))

        logging.debug(f"[ACTION_REGISTRY] Found {len(result)} provider(s) for '{capability}'")

        return result

    def get_preferred_provider(
        self,
        capability: str,
        category: str,
        user_id: int
    ) -> Optional[Tuple[int, ActionProvider]]:
        """
        Get the preferred provider for a capability and category.

        This checks the database for a preferred provider in the category,
        then verifies it supports the requested capability.

        Args:
            capability: Action type (e.g., "create_calendar_event")
            category: Service category (e.g., "calendar")
            user_id: User ID

        Returns:
            Tuple of (provider_id, provider_instance) or None

        Example:
            >>> registry = ActionProviderRegistry(memory)
            >>> registry.load_providers(user_id=1)
            >>> provider_tuple = registry.get_preferred_provider(
            ...     "create_calendar_event", "calendar", 1
            ... )
            >>> if provider_tuple:
            ...     provider_id, provider = provider_tuple
            ...     event = provider.create_calendar_event(...)
        """
        # Get preferred provider from database
        preferred = self.memory.get_preferred_provider(user_id, category)

        if not preferred:
            # No preferred provider set, return first capable provider
            providers = self.get_providers_by_capability(capability, user_id)
            return providers[0] if providers else None

        provider_id = preferred.get("id")
        provider = self.get_provider(provider_id)

        if provider and provider.supports_action(capability):
            return (provider_id, provider)

        # Preferred provider doesn't support this action, fallback to any capable provider
        logging.warning(
            f"[ACTION_REGISTRY] Preferred provider {provider_id} "
            f"doesn't support '{capability}', using fallback"
        )

        providers = self.get_providers_by_capability(capability, user_id)
        return providers[0] if providers else None

    def check_all_health(self) -> Dict[int, Dict]:
        """
        Check health of all registered providers.

        Returns:
            Dictionary mapping provider_id to health status dict

        Example:
            >>> registry = ActionProviderRegistry(memory)
            >>> registry.load_providers(user_id=1)
            >>> health = registry.check_all_health()
            >>> for provider_id, status in health.items():
            ...     print(f"Provider {provider_id}: {status['status']}")
        """
        health_status = {}

        for provider_id, provider in self._providers.items():
            try:
                health_status[provider_id] = provider.check_health()
            except Exception as e:
                logging.error(f"[ACTION_REGISTRY] Health check failed for provider {provider_id}: {e}")
                health_status[provider_id] = {
                    "healthy": False,
                    "status": "error",
                    "error": str(e)
                }

        return health_status

    def reload_provider(self, provider_id: int, user_id: int):
        """
        Reload a single provider (e.g., after credential refresh).

        Args:
            provider_id: Service provider ID to reload
            user_id: User ID for credential lookup
        """
        # Remove existing provider
        if provider_id in self._providers:
            del self._providers[provider_id]

        # Reload from database
        sp = self.memory.get_service_provider(provider_id)

        if sp and sp.get("is_enabled"):
            provider_type = sp.get("provider_type")

            if provider_type == "m365":
                creds = self.memory.get_m365_credentials(user_id)

                if creds and creds.get("is_valid"):
                    provider = M365Provider(
                        access_token=creds["access_token"],
                        refresh_token=creds["refresh_token"],
                        expires_at=creds["expires_at"],
                        user_id=user_id,
                        memory_store=self.memory
                    )
                    self._providers[provider_id] = provider
                    logging.info(f"[ACTION_REGISTRY] Reloaded provider {provider_id}")

            elif provider_type == "plex":
                creds = self.memory.get_plex_credentials(user_id)

                if creds and creds.get("is_valid"):
                    provider = PlexProvider(
                        access_token=creds["access_token"],
                        server_url=creds["server_url"],
                        user_id=user_id,
                        memory_store=self.memory
                    )
                    self._providers[provider_id] = provider
                    logging.info(f"[ACTION_REGISTRY] Reloaded provider {provider_id}")

    def get_all_providers(self) -> Dict[int, ActionProvider]:
        """
        Get all loaded providers.

        Returns:
            Dictionary mapping provider_id to provider instance
        """
        return self._providers.copy()

    def get_provider_count(self) -> int:
        """
        Get count of loaded providers.

        Returns:
            Number of providers currently loaded
        """
        return len(self._providers)

    def clear(self):
        """Clear all loaded providers."""
        self._providers.clear()
        logging.info("[ACTION_REGISTRY] Cleared all providers")
