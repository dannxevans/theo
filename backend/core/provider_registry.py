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
