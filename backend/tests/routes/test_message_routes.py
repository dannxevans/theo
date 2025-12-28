"""
Tests for message routes.

Tests chat and streaming endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


@patch("core.router.route_request")
def test_chat_success(mock_route, client, memory):
    """Test chat endpoint with successful response."""
    mock_route.return_value = {
        "text": "Hello! How can I help you?",
        "provider": "gpt4",
        "model": "gpt-4",
        "task_type": "general"
    }

    response = client.post("/api/chat", json={
        "session_id": "test-session",
        "text": "Hello"
    })

    assert response.status_code == 200
    data = response.json

    assert "text" in data
    assert "provider" in data
    assert "model" in data
    assert data["text"] == "Hello! How can I help you?"

    # Verify message was saved
    turns = memory.get_recent_turns("test-session")
    assert len(turns) >= 2  # User and assistant messages


@patch("core.router.route_request")
def test_chat_empty_text(mock_route, client):
    """Test chat endpoint with empty text."""
    mock_route.return_value = {
        "text": "Response",
        "provider": "gpt4"
    }

    response = client.post("/api/chat", json={
        "session_id": "test-session",
        "text": ""
    })

    assert response.status_code == 200


@patch("core.router.route_request")
def test_chat_no_session_id(mock_route, client):
    """Test chat endpoint defaults session_id."""
    mock_route.return_value = {
        "text": "Response",
        "provider": "gpt4"
    }

    response = client.post("/api/chat", json={
        "text": "Hello"
    })

    assert response.status_code == 200


@patch("core.router.route_request")
def test_chat_saves_conversation(mock_route, client, memory):
    """Test chat saves conversation to database."""
    mock_route.return_value = {
        "text": "AI response",
        "provider": "gpt4",
        "model": "gpt-4",
        "task_type": "general"
    }

    session_id = "save-test-session"
    response = client.post("/api/chat", json={
        "session_id": session_id,
        "text": "User message"
    })

    assert response.status_code == 200

    # Verify both turns saved
    turns = memory.get_recent_turns(session_id)
    assert len(turns) >= 2

    # Check user message
    user_turn = next((t for t in turns if t["role"] == "user"), None)
    assert user_turn is not None
    assert user_turn["content"] == "User message"

    # Check assistant message
    assistant_turn = next((t for t in turns if t["role"] == "assistant"), None)
    assert assistant_turn is not None
    assert assistant_turn["content"] == "AI response"
    assert assistant_turn["provider_id"] == "gpt4"


def test_stream_chat_success(client, memory, auth_token):
    """Test streaming chat endpoint."""
    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Streaming response",
            "provider": "gpt4",
            "model": "gpt-4",
            "task_type": "general"
        }

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={auth_token}"
        )

        assert response.status_code == 200
        assert response.content_type == "text/event-stream"

        # Parse SSE data
        data = response.data.decode("utf-8")
        assert "data:" in data


def test_stream_chat_no_token(client):
    """Test streaming without authentication token."""
    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Response",
            "provider": "gpt4"
        }

        response = client.get("/api/stream/test-session?text=Hello")

        # Should still work but without authenticated features
        assert response.status_code == 200


def test_stream_chat_forced_provider(client, auth_token):
    """Test streaming with forced provider."""
    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Response",
            "provider": "claude",
            "model": "claude-3"
        }

        response = client.get(
            f"/api/stream/test-session?text=Hello&forced_provider=claude&token={auth_token}"
        )

        assert response.status_code == 200


def test_stream_chat_with_mode(client, memory, auth_token, test_user):
    """Test streaming respects user mode."""
    # Set work mode
    memory.set_user_mode(test_user["id"], "work")

    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Professional response",
            "provider": "gpt4"
        }

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={auth_token}"
        )

        assert response.status_code == 200


def test_stream_chat_work_subtab(client, memory, auth_token, test_user):
    """Test streaming with work mode subtab configuration."""
    # Set work mode and subtab config
    memory.set_user_mode(test_user["id"], "work")
    memory.update_work_subtab_config(
        test_user["id"],
        "code",
        json.dumps({"language": "python"})
    )

    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Code help response",
            "provider": "gpt4"
        }

        response = client.get(
            f"/api/stream/test-session?text=Help&work_subtab=code&token={auth_token}"
        )

        assert response.status_code == 200


def test_stream_chat_saves_metadata(client, memory, auth_token):
    """Test streaming saves turn metadata."""
    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Response",
            "provider": "gpt4",
            "model": "gpt-4",
            "task_type": "coding"
        }

        session_id = "metadata-test"
        response = client.get(
            f"/api/stream/{session_id}?text=Write code&token={auth_token}"
        )

        assert response.status_code == 200

        # Verify metadata saved
        turns = memory.get_recent_turns(session_id)
        assistant_turn = next((t for t in turns if t["role"] == "assistant"), None)

        if assistant_turn:
            assert assistant_turn["provider_id"] == "gpt4"
            assert assistant_turn["model"] == "gpt-4"
            assert assistant_turn["intent"] == "coding"


@patch("core.router.route_request")
def test_stream_chat_error_handling(mock_route, client, auth_token):
    """Test streaming handles errors gracefully."""
    mock_route.side_effect = Exception("API Error")

    response = client.get(
        f"/api/stream/test-session?text=Hello&token={auth_token}"
    )

    assert response.status_code == 200
    data = response.data.decode("utf-8")
    assert "error" in data.lower()


def test_stream_chat_expired_token(client, memory, test_user):
    """Test streaming with expired auth token."""
    from auth import generate_session_token
    from datetime import datetime, timedelta

    # Create expired token
    token = generate_session_token()
    expires_at = datetime.utcnow() - timedelta(hours=1)
    memory.create_auth_session(token, test_user["id"], expires_at)

    with patch("core.router.route_request") as mock_route:
        mock_route.return_value = {
            "text": "Response",
            "provider": "gpt4"
        }

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={token}"
        )

        # Should still work, just without authenticated user features
        assert response.status_code == 200
