"""
Tests for action intent routing.

Tests cover:
- provider_supports_intent() correctly identifies action intents
- Action intents route to action providers, not LLM providers
- select_provider() respects is_action flag
- Dynamic action intent retrieval from database
"""

import pytest
import tempfile
import os
from core.router import provider_supports_intent, select_provider
from core.memory import MemoryStore


@pytest.fixture
def memory_store():
    """Create a temporary in-memory database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        memory = MemoryStore(f"sqlite:///{db_path}")
        # Seed default intents including action intents
        memory.seed_default_intents("test_user")
        yield memory
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_provider_supports_intent_llm_provider_rejects_action_intent(memory_store):
    """Test that LLM providers cannot handle action intents."""
    llm_provider = {
        "id": "openai",
        "provider_type": "llm",
        "model": "gpt-4"
    }

    # calendar_view is an action intent
    supports = provider_supports_intent(
        llm_provider,
        "calendar_view",
        memory=memory_store,
        user_id="test_user"
    )

    assert supports is False


def test_provider_supports_intent_llm_provider_accepts_routing_intent(memory_store):
    """Test that LLM providers can handle routing intents."""
    llm_provider = {
        "id": "openai",
        "provider_type": "llm",
        "model": "gpt-4"
    }

    # general is a routing intent (not an action)
    supports = provider_supports_intent(
        llm_provider,
        "general",
        memory=memory_store,
        user_id="test_user"
    )

    assert supports is True


def test_provider_supports_intent_action_provider_accepts_action_intent(memory_store):
    """Test that action providers can handle action intents."""
    action_provider = {
        "id": "m365_actions",
        "provider_type": "action"
    }

    # email_inbox is an action intent
    supports = provider_supports_intent(
        action_provider,
        "email_inbox",
        memory=memory_store,
        user_id="test_user"
    )

    # Action providers have their own routing logic
    # provider_supports_intent returns True for all intents for action providers
    assert supports is True


def test_provider_supports_intent_without_memory(memory_store):
    """Test that provider_supports_intent works without memory (falls back to empty list)."""
    llm_provider = {
        "id": "openai",
        "provider_type": "llm",
        "model": "gpt-4"
    }

    # Without memory, action_intents will be empty, so all intents are treated as routing intents
    supports = provider_supports_intent(llm_provider, "calendar_view", memory=None, user_id="test_user")

    # Should still return True because without memory, it can't determine if it's an action
    assert supports is True


def test_action_intent_list_retrieved_from_database(memory_store):
    """Test that action intents are dynamically retrieved from database."""
    # Get action intents
    action_intents = memory_store.get_action_intents("test_user")

    # Should include seeded action intents
    assert "calendar_view" in action_intents
    assert "email_inbox" in action_intents
    assert "calendar_create" in action_intents
    assert "email_compose" in action_intents

    # Should NOT include routing intents
    assert "general" not in action_intents
    assert "system" not in action_intents  # System is not an action


def test_disabled_action_intent_not_in_list(memory_store):
    """Test that disabled action intents are not returned."""
    # Disable an action intent
    memory_store.update_intent("test_user", "calendar_view", enabled=False)

    # Get action intents
    action_intents = memory_store.get_action_intents("test_user")

    # Disabled intent should not be in list
    assert "calendar_view" not in action_intents


def test_custom_action_intent_routing(memory_store):
    """Test that custom action intents are properly routed."""
    # Create a custom action intent
    memory_store.create_intent(
        user_id="test_user",
        intent_id="custom_action",
        name="Custom Action",
        description="A custom action",
        keywords="custom",
        priority=90,
        enabled=True,
        is_action=True
    )

    # Verify it's in the action intents list
    action_intents = memory_store.get_action_intents("test_user")
    assert "custom_action" in action_intents

    # Verify LLM provider rejects it
    llm_provider = {"id": "openai", "provider_type": "llm", "model": "gpt-4"}
    supports = provider_supports_intent(
        llm_provider,
        "custom_action",
        memory=memory_store,
        user_id="test_user"
    )
    assert supports is False


def test_system_intent_not_an_action(memory_store):
    """Test that system intent is not treated as an action intent."""
    action_intents = memory_store.get_action_intents("test_user")

    # System intent should NOT be in action intents
    assert "system" not in action_intents

    # Verify system intent exists but is_action=False
    system_intent = memory_store.get_intent("test_user", "system")
    assert system_intent is not None
    assert system_intent["is_action"] is False


def test_action_intent_user_isolation(memory_store):
    """Test that action intents are properly isolated by user."""
    # Create another user with different action intents
    memory_store.create_intent(
        user_id="user2",
        intent_id="user2_action",
        name="User 2 Action",
        description="User 2's action",
        keywords="user2",
        priority=90,
        enabled=True,
        is_action=True
    )

    # Get action intents for each user
    user1_actions = memory_store.get_action_intents("test_user")
    user2_actions = memory_store.get_action_intents("user2")

    # test_user should not see user2's custom action
    assert "user2_action" not in user1_actions

    # user2 should see their custom action
    assert "user2_action" in user2_actions


def test_converting_routing_intent_to_action(memory_store):
    """Test converting a routing intent to an action intent."""
    # Create a routing intent
    memory_store.create_intent(
        user_id="test_user",
        intent_id="test_routing",
        name="Test Routing",
        description="Originally a routing intent",
        keywords="test",
        priority=50,
        enabled=True,
        is_action=False
    )

    # Verify it's not in action intents
    action_intents = memory_store.get_action_intents("test_user")
    assert "test_routing" not in action_intents

    # Convert to action intent
    memory_store.update_intent("test_user", "test_routing", is_action=True)

    # Now it should be in action intents
    action_intents = memory_store.get_action_intents("test_user")
    assert "test_routing" in action_intents

    # LLM provider should reject it
    llm_provider = {"id": "openai", "provider_type": "llm", "model": "gpt-4"}
    supports = provider_supports_intent(
        llm_provider,
        "test_routing",
        memory=memory_store,
        user_id="test_user"
    )
    assert supports is False
