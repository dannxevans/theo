"""
Tests for session routes.

Tests session CRUD, messages, export, fork, and title generation.
"""

import pytest
import json
from unittest.mock import patch


def test_get_session(client, memory, auth_headers):
    """Test get session summary."""
    session_id = "test-session-123"
    memory.save_turn(session_id, "user", "Hello")
    memory.save_session_title(session_id, "Test Chat")

    response = client.get(f"/api/session/{session_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["session_id"] == session_id
    assert "summary" in data


def test_list_sessions(client, memory, test_user, auth_headers):
    """Test list all sessions."""
    # Create multiple sessions associated with the authenticated user
    memory.save_turn("session1", "user", "First message", user_id=test_user["id"])
    memory.save_session_title("session1", "First Session")

    memory.save_turn("session2", "user", "Second message", user_id=test_user["id"])
    memory.save_session_title("session2", "Second Session")

    response = client.get("/api/sessions", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) >= 2

    # Check structure
    session = data[0]
    assert "id" in session
    assert "title" in session
    assert "summary" in session


def test_list_sessions_empty(client, auth_headers):
    """Test list sessions when none exist."""
    response = client.get("/api/sessions", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)


def test_get_session_messages(client, memory, sample_session, auth_headers):
    """Test get messages for a session."""
    response = client.get(f"/api/sessions/{sample_session}/messages", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) > 0

    # Check message structure
    message = data[0]
    assert "role" in message
    assert "content" in message
    assert "created_at" in message


def test_get_session_messages_empty(client, auth_headers):
    """Test get messages for session with no messages."""
    response = client.get("/api/sessions/nonexistent/messages", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0


def test_delete_session(client, memory, sample_session, auth_headers):
    """Test delete a session."""
    response = client.delete(f"/api/sessions/{sample_session}", headers=auth_headers)

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify session is deleted
    turns = memory.get_recent_turns(sample_session)
    assert len(turns) == 0


def test_delete_nonexistent_session(client, auth_headers):
    """Test delete a nonexistent session."""
    response = client.delete("/api/sessions/nonexistent", headers=auth_headers)

    assert response.status_code == 200
    assert response.json["status"] == "ok"


def test_export_session_json(client, memory, sample_session, auth_headers):
    """Test export session as JSON."""
    response = client.get(f"/api/sessions/{sample_session}/export?format=json", headers=auth_headers)

    assert response.status_code == 200
    assert response.content_type == "application/json"

    # Check content-disposition header
    assert "attachment" in response.headers["Content-Disposition"]
    assert sample_session in response.headers["Content-Disposition"]

    # Parse JSON response
    data = json.loads(response.data)
    assert "session_id" in data
    assert "messages" in data
    assert isinstance(data["messages"], list)


def test_export_session_markdown(client, memory, sample_session, auth_headers):
    """Test export session as Markdown."""
    response = client.get(f"/api/sessions/{sample_session}/export?format=markdown", headers=auth_headers)

    assert response.status_code == 200
    assert "text/markdown" in response.content_type

    # Check content-disposition header
    assert "attachment" in response.headers["Content-Disposition"]
    assert sample_session in response.headers["Content-Disposition"]

    # Check markdown content
    content = response.data.decode("utf-8")
    assert "#" in content  # Should have headers


def test_export_session_default_format(client, memory, sample_session, auth_headers):
    """Test export session defaults to JSON."""
    response = client.get(f"/api/sessions/{sample_session}/export", headers=auth_headers)

    assert response.status_code == 200
    assert response.content_type == "application/json"


def test_fork_session_all_messages(client, memory, sample_session, auth_headers):
    """Test fork session with all messages."""
    response = client.post(f"/api/sessions/{sample_session}/fork", json={}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json

    assert "session_id" in data
    assert data["session_id"] != sample_session
    assert data["status"] == "ok"
    assert data["messages_copied"] > 0

    # Verify new session has messages
    new_turns = memory.get_recent_turns(data["session_id"])
    original_turns = memory.get_recent_turns(sample_session)
    assert len(new_turns) == len(original_turns)


def test_fork_session_partial(client, memory, sample_session, auth_headers):
    """Test fork session up to specific turn index."""
    response = client.post(f"/api/sessions/{sample_session}/fork", json={
        "turn_index": 1
    }, headers=auth_headers)

    assert response.status_code == 200
    data = response.json

    assert data["messages_copied"] == 2  # Indexes 0 and 1


def test_fork_session_with_title(client, memory, sample_session, auth_headers):
    """Test fork session with custom title."""
    response = client.post(f"/api/sessions/{sample_session}/fork", json={
        "title": "Forked Conversation"
    }, headers=auth_headers)

    assert response.status_code == 200
    data = response.json

    # Get session list and verify title
    sessions = memory.list_sessions()
    forked = next((s for s in sessions if s["id"] == data["session_id"]), None)
    assert forked is not None
    assert forked["title"] == "Forked Conversation"


def test_fork_empty_session(client, memory, auth_headers):
    """Test fork session with no messages."""
    response = client.post("/api/sessions/empty-session/fork", json={}, headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["messages_copied"] == 0


@patch("core.router.route_request")
def test_generate_title_success(mock_route, client, memory, sample_session, auth_headers):
    """Test generate session title."""
    mock_route.return_value = {
        "text": "Test Conversation Title",
        "provider": "gpt4"
    }

    response = client.post(f"/api/sessions/{sample_session}/generate-title", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert "title" in data
    assert len(data["title"]) > 0

    # Verify title was saved
    sessions = memory.list_sessions()
    session = next((s for s in sessions if s["id"] == sample_session), None)
    assert session is not None
    assert session["title"] == data["title"]


@patch("core.router.route_request")
def test_generate_title_truncates_long_titles(mock_route, client, memory, sample_session, auth_headers):
    """Test title generation truncates long titles."""
    long_title = "This is a very long title that exceeds the fifty character limit"
    mock_route.return_value = {
        "text": long_title,
        "provider": "gpt4"
    }

    response = client.post(f"/api/sessions/{sample_session}/generate-title", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert len(data["title"]) <= 53  # 50 + "..."


@patch("core.router.route_request")
def test_generate_title_removes_quotes(mock_route, client, memory, sample_session, auth_headers):
    """Test title generation removes quotes."""
    mock_route.return_value = {
        "text": '"Quoted Title"',
        "provider": "gpt4"
    }

    response = client.post(f"/api/sessions/{sample_session}/generate-title", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert '"' not in data["title"]


def test_generate_title_empty_session(client, memory, auth_headers):
    """Test generate title for empty session."""
    response = client.post("/api/sessions/empty/generate-title", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["title"] == "New chat"


@patch("core.router.route_request")
def test_generate_title_error_fallback(mock_route, client, memory, sample_session, auth_headers):
    """Test title generation falls back on error."""
    mock_route.side_effect = Exception("API Error")

    response = client.post(f"/api/sessions/{sample_session}/generate-title", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    # Should fallback to first user message or "New chat"
    assert "title" in data
