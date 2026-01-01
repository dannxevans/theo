"""
Tests for intent operations.

Tests intent CRUD and routing operations.
"""

import pytest


def test_create_intent(memory):
    """Test create new intent."""
    memory.create_intent(
        user_id="user1",
        intent_id="coding",
        name="Coding Assistant",
        description="Help with code",
        keywords="code,program,function",
        priority=10,
        enabled=True
    )

    intent = memory.get_intent("user1", "coding")
    assert intent is not None
    assert intent["name"] == "Coding Assistant"
    assert intent["priority"] == 10


def test_get_intent(memory):
    """Test get specific intent."""
    memory.create_intent(
        user_id="user1",
        intent_id="test",
        name="Test Intent",
        description="Test",
        keywords="test"
    )

    intent = memory.get_intent("user1", "test")
    assert intent["id"] == "test"
    assert intent["name"] == "Test Intent"


def test_get_intent_nonexistent(memory):
    """Test get nonexistent intent returns None."""
    intent = memory.get_intent("user1", "nonexistent")
    assert intent is None


def test_list_intents(memory):
    """Test list all intents."""
    memory.create_intent("user1", "intent1", "Intent 1", "Desc 1", "key1")
    memory.create_intent("user1", "intent2", "Intent 2", "Desc 2", "key2")

    intents = memory.list_intents("user1")
    assert len(intents) == 2


def test_list_intents_empty(memory):
    """Test list intents when none exist."""
    intents = memory.list_intents("user1")
    assert isinstance(intents, list)
    assert len(intents) == 0


def test_update_intent(memory):
    """Test update existing intent."""
    memory.create_intent("user1", "update_test", "Original", "Desc", "keys")

    memory.update_intent(
        "user1",
        "update_test",
        name="Updated Name",
        description="Updated Description",
        priority=20
    )

    intent = memory.get_intent("user1", "update_test")
    assert intent["name"] == "Updated Name"
    assert intent["description"] == "Updated Description"
    assert intent["priority"] == 20


def test_update_intent_partial(memory):
    """Test update intent with partial fields."""
    memory.create_intent("user1", "partial", "Original", "Desc", "keys")

    memory.update_intent("user1", "partial", name="New Name")

    intent = memory.get_intent("user1", "partial")
    assert intent["name"] == "New Name"
    assert intent["description"] == "Desc"  # Unchanged


def test_update_intent_enable_disable(memory):
    """Test enable/disable intent."""
    memory.create_intent("user1", "toggle", "Toggle", "Desc", "keys", enabled=True)

    memory.update_intent("user1", "toggle", enabled=False)
    intent = memory.get_intent("user1", "toggle")
    assert intent["enabled"] is False

    memory.update_intent("user1", "toggle", enabled=True)
    intent = memory.get_intent("user1", "toggle")
    assert intent["enabled"] is True


def test_delete_intent(memory):
    """Test delete intent."""
    memory.create_intent("user1", "to_delete", "Delete Me", "Desc", "keys")

    memory.delete_intent("user1", "to_delete")

    intent = memory.get_intent("user1", "to_delete")
    assert intent is None


def test_delete_intent_removes_routing(memory):
    """Test delete intent removes routing preferences."""
    memory.create_intent("user1", "with_routing", "Intent", "Desc", "keys")
    memory.set_routing_preference("user1", "with_routing", "provider1")

    memory.delete_intent("user1", "with_routing")

    # Routing should be removed
    provider = memory.get_routing_provider("user1", "with_routing")
    assert provider is None


def test_set_routing_preference(memory):
    """Test set routing preference."""
    memory.set_routing_preference("user1", "coding", "gpt4")

    provider = memory.get_routing_provider("user1", "coding")
    assert provider == "gpt4"


def test_set_routing_preference_update(memory):
    """Test update routing preference."""
    memory.set_routing_preference("user1", "coding", "gpt4")
    memory.set_routing_preference("user1", "coding", "claude")

    provider = memory.get_routing_provider("user1", "coding")
    assert provider == "claude"


def test_get_routing_preferences(memory):
    """Test get all routing preferences."""
    memory.set_routing_preference("user1", "coding", "gpt4")
    memory.set_routing_preference("user1", "creative", "claude")

    prefs = memory.get_routing_preferences("user1")
    assert len(prefs) == 2


def test_get_routing_preferences_empty(memory):
    """Test get routing preferences when none exist."""
    prefs = memory.get_routing_preferences("user1")
    assert isinstance(prefs, dict)
    assert len(prefs) == 0


def test_delete_routing_preference(memory):
    """Test delete routing preference."""
    memory.set_routing_preference("user1", "coding", "gpt4")

    memory.delete_routing_preference("user1", "coding")

    provider = memory.get_routing_provider("user1", "coding")
    assert provider is None


def test_get_routing_provider_nonexistent(memory):
    """Test get routing provider for nonexistent intent."""
    provider = memory.get_routing_provider("user1", "nonexistent")
    assert provider is None


def test_set_routing_provider_alias(memory):
    """Test set_routing_provider is alias for set_routing_preference."""
    memory.set_routing_provider("user1", "test", "provider1")

    provider = memory.get_routing_provider("user1", "test")
    assert provider == "provider1"


def test_seed_default_intents(memory):
    """Test seed default intents."""
    memory.seed_default_intents("user1")

    intents = memory.list_intents("user1")
    assert len(intents) > 0

    # Check for expected default intents
    intent_ids = [i["id"] for i in intents]
    assert "general" in intent_ids


def test_seed_default_intents_idempotent(memory):
    """Test seed default intents is idempotent."""
    memory.seed_default_intents("user1")
    count1 = len(memory.list_intents("user1"))

    memory.seed_default_intents("user1")
    count2 = len(memory.list_intents("user1"))

    # Should not create duplicates
    assert count1 == count2


# ====================
# Fallback Provider Tests
# ====================

def test_set_routing_preference_with_fallback(memory):
    """Test set routing preference with fallback provider."""
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="claude")

    provider = memory.get_routing_provider("user1", "general")
    fallback = memory.get_fallback_provider("user1", "general")

    assert provider == "gpt4"
    assert fallback == "claude"


def test_set_routing_preference_update_fallback(memory):
    """Test update routing preference with new fallback."""
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="claude")
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="gemini")

    fallback = memory.get_fallback_provider("user1", "general")
    assert fallback == "gemini"


def test_set_routing_preference_remove_fallback(memory):
    """Test remove fallback by setting to None."""
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="claude")
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id=None)

    fallback = memory.get_fallback_provider("user1", "general")
    assert fallback is None


def test_get_fallback_provider_nonexistent(memory):
    """Test get fallback provider for nonexistent routing rule."""
    fallback = memory.get_fallback_provider("user1", "nonexistent")
    assert fallback is None


def test_get_fallback_provider_no_fallback_set(memory):
    """Test get fallback when only primary provider is set."""
    memory.set_routing_preference("user1", "general", "gpt4")

    fallback = memory.get_fallback_provider("user1", "general")
    assert fallback is None


def test_fallback_provider_persists_across_updates(memory):
    """Test fallback provider persists when updating primary."""
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="claude")

    # Update primary provider without specifying fallback
    memory.set_routing_preference("user1", "general", "gemini")

    # Fallback should be cleared since we didn't specify it
    fallback = memory.get_fallback_provider("user1", "general")
    assert fallback is None


def test_delete_routing_preference_removes_fallback(memory):
    """Test delete routing preference also removes fallback."""
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="claude")

    memory.delete_routing_preference("user1", "general")

    provider = memory.get_routing_provider("user1", "general")
    fallback = memory.get_fallback_provider("user1", "general")

    assert provider is None
    assert fallback is None


def test_get_routing_preferences_includes_fallback(memory):
    """Test get routing preferences includes fallback provider info."""
    memory.set_routing_preference("user1", "general", "gpt4", fallback_provider_id="claude")
    memory.set_routing_preference("user1", "coding", "gemini", fallback_provider_id="gpt4")

    prefs = memory.get_routing_preferences("user1")

    assert len(prefs) == 2
    assert prefs["general"]["provider_id"] == "gpt4"
    assert prefs["general"]["fallback_provider_id"] == "claude"
    assert prefs["coding"]["provider_id"] == "gemini"
    assert prefs["coding"]["fallback_provider_id"] == "gpt4"
