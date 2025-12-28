"""
Shared test fixtures for memory store tests.

Provides MemoryStore instances and pre-populated test data.
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta

from core.memory import MemoryStore


@pytest.fixture
def memory():
    """
    Create MemoryStore with in-memory SQLite database.
    """
    db_fd, db_path = tempfile.mkstemp()
    memory_store = MemoryStore(f"sqlite:///{db_path}")

    yield memory_store

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def user_fixture(memory):
    """
    Create a test user.
    """
    from auth import hash_password

    password_hash = hash_password("testpassword")
    user_id = memory.create_user("testuser", password_hash, is_admin=False)

    return {
        "id": user_id,
        "username": "testuser",
        "password_hash": password_hash,
        "is_admin": False
    }


@pytest.fixture
def session_fixture(memory):
    """
    Create a test session with messages.
    """
    session_id = "test-session-abc"

    memory.save_turn(session_id, "user", "Hello!")
    memory.save_turn(session_id, "assistant", "Hi there!")
    memory.save_session_title(session_id, "Test Session")

    return session_id


@pytest.fixture
def populated_memory(memory):
    """
    Create MemoryStore pre-populated with test data.
    """
    from auth import hash_password

    # Create users
    user1_id = memory.create_user("user1", hash_password("pass1"), is_admin=True)
    user2_id = memory.create_user("user2", hash_password("pass2"), is_admin=False)

    # Create memories
    memory.store_memory("local", "fact", "name", "THEO")
    memory.store_memory("local", "preference", "theme", "dark")
    memory.store_memory("local", "goal", "project", "Build test suite", pinned=True)

    # Create intents
    memory.create_intent(
        user_id="local",
        intent_id="coding",
        name="Coding",
        description="Programming help",
        keywords="code,program,function",
        priority=10,
        enabled=True
    )

    memory.create_intent(
        user_id="local",
        intent_id="creative",
        name="Creative Writing",
        description="Creative content",
        keywords="write,story,creative",
        priority=5,
        enabled=True
    )

    # Create providers
    memory.upsert_provider({
        "id": "gpt4",
        "name": "GPT-4",
        "type": "openai",
        "model": "gpt-4",
        "api_key": "sk-test",
        "enabled": True
    })

    memory.upsert_provider({
        "id": "claude",
        "name": "Claude",
        "type": "anthropic",
        "model": "claude-3-opus",
        "api_key": "sk-ant-test",
        "enabled": True
    })

    # Initialize provider metadata
    memory.init_provider_metadata("gpt4", cost_per_1k_input=10, cost_per_1k_output=30)
    memory.init_provider_metadata("claude", cost_per_1k_input=15, cost_per_1k_output=75)

    # Create sessions
    session1 = "session-001"
    memory.save_turn(session1, "user", "What is Python?")
    memory.save_turn(session1, "assistant", "Python is a programming language.", provider_id="gpt4")
    memory.save_session_title(session1, "Python Discussion")

    session2 = "session-002"
    memory.save_turn(session2, "user", "Tell me a story")
    memory.save_turn(session2, "assistant", "Once upon a time...", provider_id="claude")
    memory.save_session_title(session2, "Creative Writing")

    # Set routing preferences
    memory.set_routing_preference("local", "coding", "gpt4")
    memory.set_routing_preference("local", "creative", "claude")

    return {
        "memory": memory,
        "user1_id": user1_id,
        "user2_id": user2_id,
        "session1": session1,
        "session2": session2
    }


@pytest.fixture
def memory_with_modes(memory, user_fixture):
    """
    Create MemoryStore with mode configurations.
    """
    user_id = user_fixture["id"]

    # Set active mode
    memory.set_user_mode(user_id, "work")

    # Create mode settings
    memory.create_or_update_mode_settings(
        user_id,
        "work",
        system_prompt_override="You are a professional assistant.",
        tone="professional"
    )

    memory.create_or_update_mode_settings(
        user_id,
        "personal",
        system_prompt_override="You are a friendly assistant.",
        tone="casual"
    )

    # Create work subtab configs
    import json
    memory.update_work_subtab_config(
        user_id,
        "code",
        json.dumps({
            "language": "python",
            "framework": "django",
            "additional_context": "Focus on clean code"
        })
    )

    memory.update_work_subtab_config(
        user_id,
        "email",
        json.dumps({
            "tone": "professional",
            "signature": "Best regards"
        })
    )

    return memory
