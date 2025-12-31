"""
Tests for intent management with is_action field.

Tests cover:
- Creating intents with is_action flag
- Retrieving action intents vs routing intents
- Updating is_action field
- get_action_intents() method
"""

import pytest
import tempfile
import os
from core.memory import MemoryStore


@pytest.fixture
def memory_store():
    """Create a temporary in-memory database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        memory = MemoryStore(f"sqlite:///{db_path}")
        yield memory
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_create_intent_with_is_action_true(memory_store):
    """Test creating an action intent."""
    memory_store.create_intent(
        user_id="test_user",
        intent_id="test_action",
        name="Test Action",
        description="A test action intent",
        keywords="test, action",
        priority=90,
        enabled=True,
        is_action=True
    )

    intent = memory_store.get_intent("test_user", "test_action")
    assert intent is not None
    assert intent["id"] == "test_action"
    assert intent["is_action"] is True


def test_create_intent_with_is_action_false(memory_store):
    """Test creating a routing intent."""
    memory_store.create_intent(
        user_id="test_user",
        intent_id="test_routing",
        name="Test Routing",
        description="A test routing intent",
        keywords="test, routing",
        priority=50,
        enabled=True,
        is_action=False
    )

    intent = memory_store.get_intent("test_user", "test_routing")
    assert intent is not None
    assert intent["id"] == "test_routing"
    assert intent["is_action"] is False


def test_create_intent_default_is_action(memory_store):
    """Test that is_action defaults to False when not specified."""
    memory_store.create_intent(
        user_id="test_user",
        intent_id="test_default",
        name="Test Default",
        description="A test with default is_action",
        keywords="test",
        priority=50,
        enabled=True
    )

    intent = memory_store.get_intent("test_user", "test_default")
    assert intent is not None
    assert intent["is_action"] is False


def test_get_action_intents(memory_store):
    """Test retrieving only enabled action intents."""
    # Create action intents
    memory_store.create_intent("test_user", "action1", "Action 1", "", "test", 90, True, is_action=True)
    memory_store.create_intent("test_user", "action2", "Action 2", "", "test", 90, True, is_action=True)
    memory_store.create_intent("test_user", "action3", "Action 3", "", "test", 90, False, is_action=True)  # Disabled

    # Create routing intents
    memory_store.create_intent("test_user", "routing1", "Routing 1", "", "test", 50, True, is_action=False)
    memory_store.create_intent("test_user", "routing2", "Routing 2", "", "test", 50, True, is_action=False)

    action_intents = memory_store.get_action_intents("test_user")

    assert len(action_intents) == 2
    assert "action1" in action_intents
    assert "action2" in action_intents
    assert "action3" not in action_intents  # Disabled
    assert "routing1" not in action_intents  # Not an action
    assert "routing2" not in action_intents  # Not an action


def test_get_action_intents_empty(memory_store):
    """Test get_action_intents returns empty list when no action intents exist."""
    # Create only routing intents
    memory_store.create_intent("test_user", "routing1", "Routing 1", "", "test", 50, True, is_action=False)

    action_intents = memory_store.get_action_intents("test_user")
    assert action_intents == []


def test_get_action_intents_user_isolation(memory_store):
    """Test that action intents are isolated by user_id."""
    memory_store.create_intent("user1", "action1", "Action 1", "", "test", 90, True, is_action=True)
    memory_store.create_intent("user2", "action2", "Action 2", "", "test", 90, True, is_action=True)

    user1_actions = memory_store.get_action_intents("user1")
    user2_actions = memory_store.get_action_intents("user2")

    assert "action1" in user1_actions
    assert "action1" not in user2_actions
    assert "action2" in user2_actions
    assert "action2" not in user1_actions


def test_update_intent_is_action(memory_store):
    """Test updating is_action field on existing intent."""
    memory_store.create_intent("test_user", "test_intent", "Test", "", "test", 50, True, is_action=False)

    # Update to action intent
    memory_store.update_intent("test_user", "test_intent", is_action=True)

    intent = memory_store.get_intent("test_user", "test_intent")
    assert intent["is_action"] is True

    # Update back to routing intent
    memory_store.update_intent("test_user", "test_intent", is_action=False)

    intent = memory_store.get_intent("test_user", "test_intent")
    assert intent["is_action"] is False


def test_list_intents_includes_is_action(memory_store):
    """Test that list_intents returns is_action field."""
    memory_store.create_intent("test_user", "action1", "Action 1", "", "test", 90, True, is_action=True)
    memory_store.create_intent("test_user", "routing1", "Routing 1", "", "test", 50, True, is_action=False)

    intents = memory_store.list_intents("test_user")

    assert len(intents) == 2

    action_intent = next(i for i in intents if i["id"] == "action1")
    routing_intent = next(i for i in intents if i["id"] == "routing1")

    assert action_intent["is_action"] is True
    assert routing_intent["is_action"] is False


def test_seed_default_intents_includes_action_intents(memory_store):
    """Test that seed_default_intents creates action intents with is_action=True."""
    memory_store.seed_default_intents("test_user")

    intents = memory_store.list_intents("test_user")
    action_intents = memory_store.get_action_intents("test_user")

    # Should have both action and routing intents
    assert len(intents) > 0
    assert len(action_intents) > 0

    # Verify some known action intents
    assert "calendar_view" in action_intents
    assert "email_inbox" in action_intents

    # Verify system intent exists and is NOT an action
    system_intent = next((i for i in intents if i["id"] == "system"), None)
    assert system_intent is not None
    assert system_intent["is_action"] is False
