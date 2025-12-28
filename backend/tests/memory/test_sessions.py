"""
Tests for session operations.

Tests session management, turns, summaries, and context building.
"""

import pytest
from datetime import datetime


def test_save_turn(memory):
    """Test save conversation turn."""
    memory.save_turn("session1", "user", "Hello!")

    turns = memory.get_recent_turns("session1")
    assert len(turns) == 1
    assert turns[0]["role"] == "user"
    assert turns[0]["content"] == "Hello!"


def test_save_turn_with_metadata(memory):
    """Test save turn with provider metadata."""
    memory.save_turn(
        "session1",
        "assistant",
        "Response",
        provider_id="gpt4",
        model="gpt-4",
        intent="general"
    )

    turns = memory.get_recent_turns("session1")
    turn = turns[0]
    assert turn["provider_id"] == "gpt4"
    assert turn["model"] == "gpt-4"
    assert turn["intent"] == "general"


def test_get_recent_turns(memory):
    """Test get recent conversation turns."""
    for i in range(10):
        memory.save_turn("session1", "user", f"Message {i}")

    turns = memory.get_recent_turns("session1", limit=5)
    assert len(turns) == 5


def test_get_recent_turns_empty(memory):
    """Test get recent turns for new session."""
    turns = memory.get_recent_turns("new_session")
    assert isinstance(turns, list)
    assert len(turns) == 0


def test_save_session_title(memory):
    """Test save session title."""
    memory.save_session_title("session1", "My Conversation")

    sessions = memory.list_sessions()
    session = next((s for s in sessions if s["id"] == "session1"), None)
    assert session is not None
    assert session["title"] == "My Conversation"


def test_save_session_title_update(memory):
    """Test update session title."""
    memory.save_session_title("session1", "Original")
    memory.save_session_title("session1", "Updated")

    sessions = memory.list_sessions()
    session = next((s for s in sessions if s["id"] == "session1"), None)
    assert session["title"] == "Updated"


def test_list_sessions(memory):
    """Test list all sessions."""
    memory.save_turn("session1", "user", "Message 1")
    memory.save_session_title("session1", "Session 1")

    memory.save_turn("session2", "user", "Message 2")
    memory.save_session_title("session2", "Session 2")

    sessions = memory.list_sessions()
    assert len(sessions) >= 2


def test_list_sessions_empty(memory):
    """Test list sessions when none exist."""
    sessions = memory.list_sessions()
    assert isinstance(sessions, list)


def test_delete_session(memory):
    """Test delete session and all data."""
    # Create session with data
    memory.save_turn("session1", "user", "Message")
    memory.save_session_title("session1", "Title")
    memory.save_session_summary("session1", "Summary")

    memory.delete_session("session1")

    # Verify all deleted
    turns = memory.get_recent_turns("session1")
    assert len(turns) == 0

    summary = memory.get_session_summary("session1")
    assert summary is None


def test_save_session_summary(memory):
    """Test save session summary."""
    memory.save_session_summary("session1", "This is a summary")

    summary = memory.get_session_summary("session1")
    assert summary == "This is a summary"


def test_get_session_summary_nonexistent(memory):
    """Test get summary for nonexistent session."""
    summary = memory.get_session_summary("nonexistent")
    assert summary is None


def test_should_generate_summary(memory):
    """Test should generate summary threshold."""
    # New session should not need summary
    assert memory.should_generate_summary("new_session") is False

    # Add many turns
    for i in range(25):
        memory.save_turn("session1", "user", f"Message {i}")

    # Should need summary now
    assert memory.should_generate_summary("session1", threshold=20) is True


def test_build_context(memory):
    """Test build context for model invocation."""
    memory.save_turn("session1", "user", "Hello")
    memory.save_turn("session1", "assistant", "Hi there!")

    context = memory.build_context("session1", "You are helpful", limit=10)

    assert isinstance(context, list)
    assert len(context) > 0
    # Should include system message and conversation turns


def test_build_context_limits_turns(memory):
    """Test build context respects limit."""
    for i in range(20):
        memory.save_turn("session1", "user", f"Message {i}")

    context = memory.build_context("session1", "System", limit=5)

    # Should have system message + limited turns
    assert len(context) <= 6  # System + 5 messages


def test_update_turn_metadata(memory):
    """Test update turn metadata."""
    memory.save_turn("session1", "assistant", "Response")

    import json
    metadata = {"confirmation_id": 123, "approved": True}

    memory.update_turn_metadata("session1", "assistant", metadata)

    turns = memory.get_recent_turns("session1")
    turn = turns[0]

    # Metadata should be stored as JSON
    if turn["metadata"]:
        stored_metadata = json.loads(turn["metadata"])
        assert stored_metadata["confirmation_id"] == 123


def test_ensure_session_creates_session(memory):
    """Test ensure session creates if not exists."""
    memory._ensure_session("new_session")

    sessions = memory.list_sessions()
    session_ids = [s["id"] for s in sessions]
    assert "new_session" in session_ids


def test_ensure_session_idempotent(memory):
    """Test ensure session is idempotent."""
    memory._ensure_session("session1")
    count1 = len(memory.list_sessions())

    memory._ensure_session("session1")
    count2 = len(memory.list_sessions())

    assert count1 == count2


def test_set_last_provider(memory):
    """Test set last provider for session."""
    memory.set_last_provider("session1", "gpt4")

    provider = memory.get_last_provider("session1")
    assert provider == "gpt4"


def test_get_last_provider_nonexistent(memory):
    """Test get last provider for new session."""
    provider = memory.get_last_provider("new_session")
    assert provider is None


def test_conversation_flow(memory):
    """Test complete conversation flow."""
    session_id = "conversation_test"

    # Start conversation
    memory.save_turn(session_id, "user", "What is Python?")
    memory.save_turn(session_id, "assistant", "Python is a programming language.", provider_id="gpt4")

    memory.save_turn(session_id, "user", "Tell me more")
    memory.save_turn(session_id, "assistant", "Python is used for...", provider_id="gpt4")

    # Set title
    memory.save_session_title(session_id, "Python Discussion")

    # Verify
    turns = memory.get_recent_turns(session_id)
    assert len(turns) == 4

    sessions = memory.list_sessions()
    session = next((s for s in sessions if s["id"] == session_id), None)
    assert session["title"] == "Python Discussion"
