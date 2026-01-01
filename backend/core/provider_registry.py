class ProviderRegistry:
    """
    Runtime registry for LLM providers.

    Responsibilities:
    - Load provider configs from MemoryStore
    - Cache them in memory
    - Expose lookup helpers for the router
    - Allow reload without restarting the app
    """

    BUILT_IN_PROVIDERS = {"mock"}

    def __init__(self, memory_store):
        self.memory = memory_store
        self._providers = {}
        self.reload()

    # =============================
    # Load / Reload
    # =============================
    def reload(self):
        """
        Reload providers from persistent storage into memory.
        """
        providers = self.memory.list_providers()
        self._providers = {
            p["id"]: p for p in providers if p.get("enabled", True)
        }

    # =============================
    # Query helpers
    # =============================
    def list(self):
        """
        Return all enabled providers.
        """
        return list(self._providers.values())

    def get(self, provider_id):
        """
        Get a provider by ID.
        """
        return self._providers.get(provider_id)

    def get_by_type(self, provider_type):
        """
        Get the first enabled provider matching a given type.
        Built-in providers (e.g. mock) are handled explicitly.
        """
        if provider_type in self.BUILT_IN_PROVIDERS:
            return {
                "id": provider_type,
                "type": provider_type,
                "enabled": True
            }

        for provider in self._providers.values():
            if provider.get("type") == provider_type and provider.get("enabled", True):
                return provider
        return None

    def get_by_model(self, model: str):
        """
        Return provider config that owns the given model name.
        """
        for provider in self._providers.values():
            if provider.get("model") == model:
                return provider
        return None

    # =============================
    # Mutations (write-through)
    # =============================
    def upsert(self, provider):
        """
        Create or update a provider config and reload registry.
        """
        self.memory.upsert_provider(provider)
        self.reload()

    def delete(self, provider_id):
        """
        Delete a provider config and reload registry.
        """
        self.memory.delete_provider(provider_id)
        self.reload()

    def get_system_provider(self):
        """
        Get the system provider (used for lightweight tasks like summarization).
        Uses the 'system' routing preference if set, otherwise falls back to first enabled provider.
        """
        # Try to get system provider from routing preferences
        try:
            from sqlalchemy import select
            with self.memory.engine.begin() as conn:
                result = conn.execute(
                    select(self.memory.routing_preferences.c.provider_id, self.memory.routing_preferences.c.fallback_provider_id)
                    .where(self.memory.routing_preferences.c.task_category == 'system')
                    .where(self.memory.routing_preferences.c.user_id == 1)
                ).fetchone()

                if result:
                    primary_id = result[0]
                    fallback_id = result[1]

                    # Try primary provider first
                    primary = self.get(primary_id)
                    if primary and primary.get('enabled', True):
                        return primary

                    # Fall back to fallback provider
                    if fallback_id:
                        fallback = self.get(fallback_id)
                        if fallback and fallback.get('enabled', True):
                            return fallback
        except Exception:
            pass

        # Default: return first enabled provider
        providers = self.list()
        if providers:
            return providers[0]
        return None
