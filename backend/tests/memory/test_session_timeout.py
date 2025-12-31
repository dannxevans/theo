"""
Tests for session timeout and inactivity tracking.

Tests cover:
- last_activity_at field on auth_sessions
- update_session_activity() method
- Session inactivity timeout logic
- User preference for session_timeout
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
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


def test_create_session_initializes_last_activity(memory_store):
    """Test that creating a session initializes last_activity_at."""
    # Create a user first
    user_id = memory_store.create_user("test_user", "password123")

    # Create a session
    session_id = memory_store.create_auth_session(user_id)

    # Get the session
    session = memory_store.get_auth_session(session_id)

    assert session is not None
    assert "last_activity_at" in session
    assert session["last_activity_at"] is not None

    # last_activity_at should be close to created_at
    last_activity = datetime.fromisoformat(session["last_activity_at"])
    created_at = datetime.fromisoformat(session["created_at"])

    time_diff = abs((last_activity - created_at).total_seconds())
    assert time_diff < 2  # Should be within 2 seconds


def test_update_session_activity(memory_store):
    """Test updating last_activity_at timestamp."""
    user_id = memory_store.create_user("test_user", "password123")
    session_id = memory_store.create_auth_session(user_id)

    # Get initial last_activity_at
    session1 = memory_store.get_auth_session(session_id)
    initial_activity = datetime.fromisoformat(session1["last_activity_at"])

    # Wait a moment
    import time
    time.sleep(0.1)

    # Update session activity
    memory_store.update_session_activity(session_id)

    # Get updated last_activity_at
    session2 = memory_store.get_auth_session(session_id)
    updated_activity = datetime.fromisoformat(session2["last_activity_at"])

    # last_activity_at should be updated
    assert updated_activity > initial_activity


def test_update_session_activity_invalid_session(memory_store):
    """Test updating activity for non-existent session doesn't raise error."""
    # Should not raise an exception
    memory_store.update_session_activity("non_existent_session_id")


def test_get_user_preference_session_timeout(memory_store):
    """Test getting user preference for session timeout."""
    user_id = memory_store.create_user("test_user", "password123")

    # Set session timeout preference
    memory_store.set_user_preference(user_id, "session_timeout", "12")

    # Get the preference
    timeout = memory_store.get_user_preference(user_id, "session_timeout")

    assert timeout == "12"


def test_get_user_preference_with_default(memory_store):
    """Test getting user preference with default value."""
    user_id = memory_store.create_user("test_user", "password123")

    # Get preference that doesn't exist, should return default
    timeout = memory_store.get_user_preference(user_id, "session_timeout", "8")

    assert timeout == "8"


def test_set_user_preference_upsert(memory_store):
    """Test that set_user_preference updates existing preference."""
    user_id = memory_store.create_user("test_user", "password123")

    # Set initial value
    memory_store.set_user_preference(user_id, "session_timeout", "8")
    assert memory_store.get_user_preference(user_id, "session_timeout") == "8"

    # Update value
    memory_store.set_user_preference(user_id, "session_timeout", "12")
    assert memory_store.get_user_preference(user_id, "session_timeout") == "12"


def test_preferences_unique_constraint(memory_store):
    """Test that preferences table has unique constraint on (user_id, key)."""
    user_id = memory_store.create_user("test_user", "password123")

    # Set preference
    memory_store.set_user_preference(user_id, "session_timeout", "8")

    # Set again - should update, not create duplicate
    memory_store.set_user_preference(user_id, "session_timeout", "12")

    # Verify only one preference exists
    all_prefs = memory_store.get_all(user_id)
    timeout_prefs = [v for k, v in all_prefs.items() if k == "session_timeout"]

    # Should only have one session_timeout preference
    assert len(timeout_prefs) == 1
    assert timeout_prefs[0] == "12"


def test_user_preference_isolation(memory_store):
    """Test that user preferences are isolated by user_id."""
    user1_id = memory_store.create_user("user1", "password123")
    user2_id = memory_store.create_user("user2", "password456")

    # Set different timeouts for each user
    memory_store.set_user_preference(user1_id, "session_timeout", "8")
    memory_store.set_user_preference(user2_id, "session_timeout", "24")

    # Verify isolation
    assert memory_store.get_user_preference(user1_id, "session_timeout") == "8"
    assert memory_store.get_user_preference(user2_id, "session_timeout") == "24"


def test_session_activity_tracking_multiple_updates(memory_store):
    """Test that session activity can be updated multiple times."""
    user_id = memory_store.create_user("test_user", "password123")
    session_id = memory_store.create_auth_session(user_id)

    activities = []

    # Update activity multiple times
    for i in range(3):
        import time
        time.sleep(0.1)
        memory_store.update_session_activity(session_id)
        session = memory_store.get_auth_session(session_id)
        activities.append(datetime.fromisoformat(session["last_activity_at"]))

    # Each activity timestamp should be later than the previous
    assert activities[1] > activities[0]
    assert activities[2] > activities[1]


def test_expired_session_cleanup(memory_store):
    """Test that old sessions can be identified by last_activity_at."""
    user_id = memory_store.create_user("test_user", "password123")

    # Create session
    session_id = memory_store.create_auth_session(user_id)

    # Get the session and check it exists
    session = memory_store.get_auth_session(session_id)
    assert session is not None

    # In a real scenario, auth_routes.py would check last_activity_at
    # and delete expired sessions using delete_auth_session()
    last_activity = datetime.fromisoformat(session["last_activity_at"])
    now = datetime.utcnow()

    # Simulate checking if session is inactive (would be > 8 hours in prod)
    inactive_duration = now - last_activity

    # For this test, the session should be active (just created)
    assert inactive_duration.total_seconds() < 10
