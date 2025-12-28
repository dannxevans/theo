"""
THEO Memory Store - Modular Architecture.

Provides database-backed memory operations including:
- Memories and preferences
- User sessions and authentication
- AI provider management
- Intent and routing configuration
- Service provider integration
- Action and confirmation management

Example usage:
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    memory.remember("user_123", "favorite_color", "blue")
"""

from .store import MemoryStore

__all__ = ['MemoryStore']
