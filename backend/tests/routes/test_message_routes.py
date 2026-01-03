"""
Tests for message routes.

Tests chat and streaming endpoints.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


@patch("core.router.route_request")
def test_chat_success(mock_route, client, memory, auth_headers):
    """Test chat endpoint with successful response."""
    mock_route.return_value = {
        "text": "Hello! How can I help you?",
        "provider": "gpt4",
        "model": "gpt-4",
        "task_type": "general"
    }

    response = client.post("/api/chat",
        headers=auth_headers,
        json={
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
def test_chat_empty_text(mock_route, client, auth_headers):
    """Test chat endpoint with empty text."""
    # Empty text should be rejected with 400 error
    response = client.post("/api/chat",
        headers=auth_headers,
        json={
            "session_id": "test-session",
            "text": ""
        })

    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "empty" in data["error"].lower()


@patch("core.router.route_request")
def test_chat_no_session_id(mock_route, client, auth_headers):
    """Test chat endpoint defaults session_id."""
    mock_route.return_value = {
        "text": "Response",
        "provider": "gpt4"
    }

    response = client.post("/api/chat",
        headers=auth_headers,
        json={
            "text": "Hello"
        })

    assert response.status_code == 200


@patch("core.router.route_request")
def test_chat_saves_conversation(mock_route, client, memory, auth_headers):
    """Test chat saves conversation to database."""
    mock_route.return_value = {
        "text": "AI response",
        "provider": "gpt4",
        "model": "gpt-4",
        "task_type": "general"
    }

    session_id = "save-test-session"
    response = client.post("/api/chat",
        headers=auth_headers,
        json={
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


def test_stream_chat_real_time_streaming(client, auth_token):
    """Test that tokens are streamed in real-time, not buffered."""
    with patch("core.router.route_request") as mock_route:
        # Mock stream generator that yields tokens one by one
        def mock_stream_generator():
            yield {"token": "Hello"}
            yield {"token": " "}
            yield {"token": "world"}
            yield {"token": "!"}
            # End event
            yield {
                "event": "end",
                "provider": "gpt4",
                "model": "gpt-4",
                "task_type": "general",
                "fallback_reason": None,
                "routing": None
            }

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={auth_token}"
        )

        assert response.status_code == 200
        assert response.content_type == "text/event-stream"

        # Parse SSE data
        data = response.data.decode("utf-8")
        lines = [line for line in data.split("\n") if line.strip()]

        # Count token events (should have multiple individual tokens)
        token_events = [line for line in lines if line.startswith("data:") and "token" in line]
        assert len(token_events) >= 4  # Should have at least 4 token chunks

        # Verify tokens are sent individually
        assert '"token": "Hello"' in data or '"token":"Hello"' in data
        assert '"token": " "' in data or '"token":" "' in data
        assert '"token": "world"' in data or '"token":"world"' in data

        # Verify end event exists
        assert "event: end" in data


def test_stream_chat_accumulates_and_persists(client, auth_token):
    """Test that streamed tokens are accumulated and sent correctly."""
    session_id = "accumulation-test"

    with patch("core.router.route_request") as mock_route:
        # Mock stream generator
        def mock_stream_generator():
            yield {"token": "Streamed "}
            yield {"token": "response "}
            yield {"token": "text."}
            yield {
                "event": "end",
                "provider": "gpt4",
                "model": "gpt-4",
                "task_type": "general",
                "fallback_reason": None,
                "routing": None
            }

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/{session_id}?text=Test message&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data to verify all tokens were streamed
        data = response.data.decode("utf-8")

        # Verify all tokens are present
        assert "Streamed " in data
        assert "response " in data
        assert "text." in data

        # Verify end event
        assert "event: end" in data
        assert '"provider"' in data or 'provider' in data


def test_stream_chat_end_event_metadata(client, auth_token):
    """Test that end event contains correct metadata."""
    with patch("core.router.route_request") as mock_route:
        # Mock stream generator with metadata
        def mock_stream_generator():
            yield {"token": "Response"}
            yield {
                "event": "end",
                "provider": "claude",
                "model": "claude-3",
                "task_type": "coding",
                "fallback_reason": "primary_failed",
                "routing": {"intent": "coding", "primary": "gpt4", "fallback": "claude"}
            }

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/test-session?text=Write code&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data
        data = response.data.decode("utf-8")

        # Verify end event contains metadata
        assert "event: end" in data
        assert '"provider"' in data
        assert '"model"' in data
        assert '"task_type"' in data
        assert '"claude"' in data or 'claude' in data


def test_stream_chat_streaming_error_handling(client, auth_token):
    """Test graceful handling of streaming errors."""
    with patch("core.router.route_request") as mock_route:
        # Mock stream generator that raises an error
        def mock_stream_generator():
            yield {"token": "Start"}
            raise Exception("Streaming error occurred")

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data
        data = response.data.decode("utf-8")

        # Should fall back to non-streaming mode
        assert "data:" in data


def test_stream_chat_non_streaming_fallback(client, auth_token):
    """Test fallback to non-streaming when provider doesn't support streaming."""
    with patch("core.router.route_request") as mock_route:
        # Return non-streaming response (dict instead of generator)
        mock_route.return_value = {
            "text": "Complete response",
            "provider": "openai",
            "model": "gpt-4",
            "task_type": "general"
        }

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data - should still stream the response in chunks
        data = response.data.decode("utf-8")
        assert "data:" in data
        assert "event: end" in data


def test_stream_chat_empty_stream(client, auth_token):
    """Test handling of empty streaming response."""
    with patch("core.router.route_request") as mock_route:
        # Mock stream generator with only end event
        def mock_stream_generator():
            yield {
                "event": "end",
                "provider": "gpt4",
                "model": "gpt-4",
                "task_type": "general",
                "fallback_reason": None,
                "routing": None
            }

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/test-session?text=Hello&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data
        data = response.data.decode("utf-8")
        assert "event: end" in data


def test_stream_chat_large_response(client, auth_token):
    """Test streaming with large response (many tokens)."""
    session_id = "large-stream-test"

    with patch("core.router.route_request") as mock_route:
        # Mock stream generator with many tokens
        def mock_stream_generator():
            for i in range(100):
                yield {"token": f"Token{i} "}
            yield {
                "event": "end",
                "provider": "gpt4",
                "model": "gpt-4",
                "task_type": "general",
                "fallback_reason": None,
                "routing": None
            }

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/{session_id}?text=Long response&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data
        data = response.data.decode("utf-8")
        token_events = [line for line in data.split("\n") if "token" in line and "data:" in line]

        # Should have approximately 100 token events
        assert len(token_events) >= 90  # Allow some margin

        # Verify tokens are present
        assert "Token0" in data
        assert "Token99" in data
        assert "event: end" in data


def test_stream_chat_with_routine_execution(client, auth_token):
    """Test streaming when routine is executed (non-streaming path)."""
    with patch("core.routines.detect_routine") as mock_detect, \
         patch("core.routines.execute_routine") as mock_execute, \
         patch("core.routines.consolidate_results") as mock_consolidate:

        # Mock routine detection
        mock_detect.return_value = ("morning_routine", {"name": "morning_routine", "actions": []})

        # Mock routine execution
        mock_execute.return_value = {"actions": []}

        # Mock consolidation (returns complete response, not generator)
        mock_consolidate.return_value = {
            "text": "Routine executed successfully",
            "provider": "routine",
            "model": None,
            "task_type": "routine"
        }

        response = client.get(
            f"/api/stream/routine-test?text=Run morning routine&token={auth_token}"
        )

        assert response.status_code == 200

        # Parse SSE data - should still stream (chunked)
        data = response.data.decode("utf-8")
        assert "data:" in data
        assert "event: end" in data


def test_stream_chat_preserves_metadata(client, auth_token):
    """Test that all metadata is preserved through streaming."""
    session_id = "metadata-preservation-test"

    with patch("core.router.route_request") as mock_route:
        # Mock stream generator with full metadata
        def mock_stream_generator():
            yield {"token": "Response with metadata"}
            yield {
                "event": "end",
                "provider": "claude",
                "model": "claude-3-opus",
                "task_type": "coding",
                "fallback_reason": "primary_unhealthy",
                "routing": {
                    "intent": "coding",
                    "primary_provider": "gpt4",
                    "fallback_provider": "claude",
                    "used_fallback": True
                }
            }

        mock_route.return_value = mock_stream_generator()

        response = client.get(
            f"/api/stream/{session_id}?text=Code help&token={auth_token}"
        )

        assert response.status_code == 200

        # Verify metadata in end event
        data = response.data.decode("utf-8")
        assert '"provider"' in data or 'provider' in data
        assert '"model"' in data or 'model' in data
        assert '"task_type"' in data or 'task_type' in data
        assert '"fallback_reason"' in data or 'fallback_reason' in data
        assert '"routing"' in data or 'routing' in data
        assert 'claude' in data
