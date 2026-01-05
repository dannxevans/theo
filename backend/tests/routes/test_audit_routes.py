"""
Tests for database audit routes.

Tests session listing, turn viewing, statistics, admin access control, and filtering.
"""

import pytest
import json
from datetime import datetime, timedelta


def test_get_sessions_requires_admin(client, memory, test_user):
    """Test get sessions requires admin authentication."""
    # Create non-admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions", headers=headers)

    assert response.status_code == 403
    assert "admin access required" in response.json["error"].lower()


def test_get_sessions_requires_auth(client):
    """Test get sessions requires authentication."""
    response = client.get("/api/audit/sessions")

    assert response.status_code == 401


def test_get_sessions_empty(client, memory, admin_user):
    """Test get sessions when empty."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert "sessions" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data
    assert data["sessions"] == []
    assert data["total"] == 0
    assert data["has_more"] is False


def test_get_sessions_success(client, memory, admin_user):
    """Test get sessions returns session list."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test sessions
    session1_id = "test-session-1"
    session2_id = "test-session-2"

    memory.save_turn(session1_id, "user", "Hello world")
    memory.save_turn(session1_id, "assistant", "Hi there!")
    memory.save_session_title(session1_id, "Test Session 1")

    memory.save_turn(session2_id, "user", "How are you?")
    memory.save_session_title(session2_id, "Test Session 2")

    response = client.get("/api/audit/sessions", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["sessions"]) == 2
    assert data["total"] == 2
    assert data["has_more"] is False

    # Check session data structure
    session = data["sessions"][0]
    assert "id" in session
    assert "title" in session
    assert "mode" in session
    assert "created_at" in session
    assert "turn_count" in session


def test_get_sessions_with_mode_filter(client, memory, admin_user):
    """Test get sessions with mode filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create sessions with different modes
    work_session = "work-session-1"
    personal_session = "personal-session-1"

    memory.save_turn(work_session, "user", "Work stuff")
    memory.save_session_title(work_session, "Work Session")
    # Update session mode to work
    import sqlite3
    db_path = memory.engine.url.database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET mode = ? WHERE id = ?", ("work", work_session))
    conn.commit()
    conn.close()

    memory.save_turn(personal_session, "user", "Personal stuff")
    memory.save_session_title(personal_session, "Personal Session")

    # Filter by work mode
    response = client.get("/api/audit/sessions?mode=work", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["sessions"]) == 1
    assert data["sessions"][0]["mode"] == "work"


def test_get_sessions_with_invalid_mode(client, memory, admin_user):
    """Test get sessions with invalid mode filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions?mode=invalid", headers=headers)

    assert response.status_code == 400
    assert "Invalid mode" in response.json["error"]


def test_get_sessions_with_date_filter(client, memory, admin_user):
    """Test get sessions with date range filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session
    session_id = "test-session-dated"
    memory.save_turn(session_id, "user", "Test message")

    # Filter by date (should include all sessions created today)
    today = datetime.utcnow().date().isoformat()
    response = client.get(f"/api/audit/sessions?start_date={today}", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert data["total"] >= 1


def test_get_sessions_with_invalid_date(client, memory, admin_user):
    """Test get sessions with invalid date format."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions?start_date=invalid-date", headers=headers)

    assert response.status_code == 400
    assert "Invalid date format" in response.json["error"]


def test_get_sessions_pagination(client, memory, admin_user):
    """Test get sessions pagination."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create 5 test sessions
    for i in range(5):
        session_id = f"test-session-{i}"
        memory.save_turn(session_id, "user", f"Message {i}")
        memory.save_session_title(session_id, f"Session {i}")

    # Get first page
    response = client.get("/api/audit/sessions?limit=2&offset=0", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["sessions"]) == 2
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 0
    assert data["has_more"] is True

    # Get second page
    response = client.get("/api/audit/sessions?limit=2&offset=2", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["sessions"]) == 2
    assert data["offset"] == 2
    assert data["has_more"] is True


def test_get_sessions_invalid_pagination(client, memory, admin_user):
    """Test get sessions with invalid pagination parameters."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions?limit=invalid", headers=headers)

    assert response.status_code == 400
    assert "Invalid pagination parameters" in response.json["error"]


def test_get_session_turns_requires_admin(client, memory, test_user):
    """Test get session turns requires admin authentication."""
    # Create non-admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions/test-session/turns", headers=headers)

    assert response.status_code == 403
    assert "admin access required" in response.json["error"].lower()


def test_get_session_turns_requires_auth(client):
    """Test get session turns requires authentication."""
    response = client.get("/api/audit/sessions/test-session/turns")

    assert response.status_code == 401


def test_get_session_turns_nonexistent_session(client, memory, admin_user):
    """Test get session turns for nonexistent session."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/sessions/nonexistent-session/turns", headers=headers)

    assert response.status_code == 404
    assert "Session not found" in response.json["error"]


def test_get_session_turns_success(client, memory, admin_user):
    """Test get session turns returns turn list."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with turns
    session_id = "test-session-turns"
    memory.save_turn(session_id, "user", "Hello, how are you?")
    memory.save_turn(
        session_id,
        "assistant",
        "I'm doing well, thank you!",
        provider_id="test-provider",
        model="test-model",
        intent="general"
    )
    memory.save_turn(session_id, "user", "What's the weather?")
    memory.save_session_title(session_id, "Test Conversation")

    response = client.get(f"/api/audit/sessions/{session_id}/turns", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert "session" in data
    assert "turns" in data
    assert "total" in data
    assert len(data["turns"]) == 3
    assert data["total"] == 3

    # Check session info
    assert data["session"]["id"] == session_id
    assert data["session"]["title"] == "Test Conversation"

    # Check turn structure
    turn = data["turns"][1]  # Assistant turn
    assert "id" in turn
    assert turn["role"] == "assistant"
    assert turn["content"] == "I'm doing well, thank you!"
    assert turn["provider_id"] == "test-provider"
    assert turn["model"] == "test-model"
    assert turn["intent"] == "general"
    assert "created_at" in turn


def test_get_session_turns_with_role_filter(client, memory, admin_user):
    """Test get session turns with role filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with turns
    session_id = "test-session-role-filter"
    memory.save_turn(session_id, "user", "Question 1")
    memory.save_turn(session_id, "assistant", "Answer 1")
    memory.save_turn(session_id, "user", "Question 2")
    memory.save_turn(session_id, "assistant", "Answer 2")

    # Filter by user role
    response = client.get(f"/api/audit/sessions/{session_id}/turns?role=user", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["turns"]) == 2
    assert all(turn["role"] == "user" for turn in data["turns"])


def test_get_session_turns_with_invalid_role(client, memory, admin_user):
    """Test get session turns with invalid role filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session
    session_id = "test-session-invalid-role"
    memory.save_turn(session_id, "user", "Test")

    response = client.get(f"/api/audit/sessions/{session_id}/turns?role=invalid", headers=headers)

    assert response.status_code == 400
    assert "Invalid role" in response.json["error"]


def test_get_session_turns_with_provider_filter(client, memory, admin_user):
    """Test get session turns with provider filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with different providers
    session_id = "test-session-provider-filter"
    memory.save_turn(session_id, "user", "Question 1")
    memory.save_turn(session_id, "assistant", "Answer 1", provider_id="provider-a")
    memory.save_turn(session_id, "user", "Question 2")
    memory.save_turn(session_id, "assistant", "Answer 2", provider_id="provider-b")

    # Filter by provider-a
    response = client.get(f"/api/audit/sessions/{session_id}/turns?provider_id=provider-a", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["turns"]) == 1
    assert data["turns"][0]["provider_id"] == "provider-a"


def test_get_session_turns_with_model_filter(client, memory, admin_user):
    """Test get session turns with model filter."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with different models
    session_id = "test-session-model-filter"
    memory.save_turn(session_id, "user", "Question 1")
    memory.save_turn(session_id, "assistant", "Answer 1", model="gpt-4")
    memory.save_turn(session_id, "user", "Question 2")
    memory.save_turn(session_id, "assistant", "Answer 2", model="claude-3")

    # Filter by gpt-4
    response = client.get(f"/api/audit/sessions/{session_id}/turns?model=gpt-4", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["turns"]) == 1
    assert data["turns"][0]["model"] == "gpt-4"


def test_get_session_turns_pagination(client, memory, admin_user):
    """Test get session turns pagination."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with many turns
    session_id = "test-session-turn-pagination"
    for i in range(10):
        memory.save_turn(session_id, "user", f"Question {i}")
        memory.save_turn(session_id, "assistant", f"Answer {i}")

    # Get first page
    response = client.get(f"/api/audit/sessions/{session_id}/turns?limit=5&offset=0", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["turns"]) == 5
    assert data["total"] == 20
    assert data["has_more"] is True

    # Get second page
    response = client.get(f"/api/audit/sessions/{session_id}/turns?limit=5&offset=5", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["turns"]) == 5
    assert data["offset"] == 5


def test_get_session_turns_with_metadata(client, memory, admin_user):
    """Test get session turns with JSON metadata fields."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with metadata
    session_id = "test-session-metadata"

    # Manually insert turn with metadata using SQLite
    import sqlite3
    db_path = memory.engine.url.database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # First ensure session exists
    memory.save_turn(session_id, "user", "Test")

    # Insert turn with metadata
    cursor.execute("""
        INSERT INTO turns (session_id, role, content, provider_id, model, intent, metadata)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id,
        "assistant",
        "Response with metadata",
        "test-provider",
        "test-model",
        "general",
        json.dumps({"tokens": 100, "cost": 0.01})
    ))
    conn.commit()
    conn.close()

    response = client.get(f"/api/audit/sessions/{session_id}/turns", headers=headers)

    assert response.status_code == 200
    data = response.json

    # Find the assistant turn with metadata
    assistant_turn = next((t for t in data["turns"] if t["role"] == "assistant" and t["provider_id"] == "test-provider"), None)
    assert assistant_turn is not None
    assert assistant_turn["metadata"] is not None
    assert assistant_turn["metadata"]["tokens"] == 100
    assert assistant_turn["metadata"]["cost"] == 0.01


def test_get_audit_stats_requires_admin(client, memory, test_user):
    """Test get audit stats requires admin authentication."""
    # Create non-admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/stats", headers=headers)

    assert response.status_code == 403
    assert "admin access required" in response.json["error"].lower()


def test_get_audit_stats_requires_auth(client):
    """Test get audit stats requires authentication."""
    response = client.get("/api/audit/stats")

    assert response.status_code == 401


def test_get_audit_stats_empty(client, memory, admin_user):
    """Test get audit stats when database is empty."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    response = client.get("/api/audit/stats", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert "total_sessions" in data
    assert "total_turns" in data
    assert "sessions_by_mode" in data
    assert "turns_by_role" in data
    assert "turns_by_provider" in data
    assert "turns_by_model" in data
    assert "turns_by_intent" in data
    assert data["total_sessions"] == 0
    assert data["total_turns"] == 0


def test_get_audit_stats_success(client, memory, admin_user):
    """Test get audit stats returns correct statistics."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test data
    # Session 1 - work mode
    session1 = "work-session"
    memory.save_turn(session1, "user", "Work question")
    memory.save_turn(session1, "assistant", "Work answer", provider_id="openai", model="gpt-4", intent="work")

    # Update session mode
    import sqlite3
    db_path = memory.engine.url.database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE sessions SET mode = ? WHERE id = ?", ("work", session1))
    conn.commit()
    conn.close()

    # Session 2 - personal mode
    session2 = "personal-session"
    memory.save_turn(session2, "user", "Personal question")
    memory.save_turn(session2, "assistant", "Personal answer", provider_id="anthropic", model="claude-3", intent="general")

    response = client.get("/api/audit/stats", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert data["total_sessions"] == 2
    assert data["total_turns"] == 4
    assert data["sessions_by_mode"]["work"] == 1
    assert data["sessions_by_mode"]["personal"] == 1
    assert data["turns_by_role"]["user"] == 2
    assert data["turns_by_role"]["assistant"] == 2
    assert "openai" in data["turns_by_provider"]
    assert "anthropic" in data["turns_by_provider"]
    assert "gpt-4" in data["turns_by_model"]
    assert "claude-3" in data["turns_by_model"]
    assert "work" in data["turns_by_intent"]
    assert "general" in data["turns_by_intent"]


def test_get_audit_stats_comprehensive(client, memory, admin_user):
    """Test get audit stats with comprehensive data."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create multiple sessions with various providers and models
    for i in range(3):
        session_id = f"stats-session-{i}"
        memory.save_turn(session_id, "user", f"Question {i}")
        memory.save_turn(session_id, "assistant", f"Answer {i}", provider_id=f"provider-{i % 2}", model=f"model-{i % 2}")

    response = client.get("/api/audit/stats", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert data["total_sessions"] == 3
    assert data["total_turns"] == 6
    assert len(data["turns_by_provider"]) == 2
    assert len(data["turns_by_model"]) == 2


def test_get_session_turns_with_full_request_context(client, memory, admin_user):
    """Test that full_request_context is properly returned when present."""
    # Create admin auth token
    from auth import generate_session_token

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, admin_user["id"], expires_at)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Create test session with full_request_context
    session_id = "test-session-with-context"
    memory.save_turn(session_id, "user", "What is the weather?")

    # Simulate a full LLM request context
    full_context = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Previous message"},
        {"role": "assistant", "content": "Previous response"},
        {"role": "user", "content": "What is the weather?"}
    ]

    memory.save_turn(
        session_id,
        "assistant",
        "I can help you check the weather.",
        provider_id="openai",
        model="gpt-4",
        intent="weather",
        full_request_context=full_context
    )

    response = client.get(f"/api/audit/sessions/{session_id}/turns", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["turns"]) == 2

    # Check user turn (should not have full_request_context)
    user_turn = data["turns"][0]
    assert user_turn["role"] == "user"
    assert user_turn["full_request_context"] is None

    # Check assistant turn (should have full_request_context)
    assistant_turn = data["turns"][1]
    assert assistant_turn["role"] == "assistant"
    assert assistant_turn["full_request_context"] is not None
    assert len(assistant_turn["full_request_context"]) == 4
    assert assistant_turn["full_request_context"][0]["role"] == "system"
    assert assistant_turn["full_request_context"][0]["content"] == "You are a helpful assistant."
    assert assistant_turn["full_request_context"][3]["role"] == "user"
    assert assistant_turn["full_request_context"][3]["content"] == "What is the weather?"


def test_save_turn_with_full_request_context(memory):
    """Test that save_turn properly stores full_request_context as JSON."""
    session_id = "test-context-storage"

    full_context = [
        {"role": "system", "content": "Test system prompt"},
        {"role": "user", "content": "Test user message"}
    ]

    # Save turn with full_request_context
    memory.save_turn(
        session_id,
        "assistant",
        "Test response",
        full_request_context=full_context
    )

    # Retrieve and verify it was stored correctly
    import sqlite3
    from routes.audit_routes import get_db_path

    db_path = get_db_path(memory)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT full_request_context
        FROM turns
        WHERE session_id = ? AND role = 'assistant'
    """, (session_id,))

    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row["full_request_context"] is not None

    # Parse JSON and verify structure
    stored_context = json.loads(row["full_request_context"])
    assert len(stored_context) == 2
    assert stored_context[0]["role"] == "system"
    assert stored_context[0]["content"] == "Test system prompt"
