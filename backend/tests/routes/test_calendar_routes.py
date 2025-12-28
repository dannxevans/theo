"""
Tests for calendar routes.

Tests natural language calendar query endpoint.
"""

import pytest
from unittest.mock import patch


def test_calendar_query_unauthorized(client):
    """Test calendar query requires authentication."""
    response = client.post("/api/calendar/query", json={
        "text": "What's on my calendar?"
    })

    assert response.status_code == 401


@patch("core.router.route_request")
def test_calendar_query_success(mock_route, client, auth_headers):
    """Test successful calendar query."""
    mock_route.return_value = {
        "text": "You have 2 meetings today",
        "provider": "gpt4",
        "task_type": "calendar"
    }

    response = client.post("/api/calendar/query", headers=auth_headers, json={
        "text": "What's on my calendar today?",
        "session_id": "test-session"
    })

    assert response.status_code == 200
    data = response.json
    assert "text" in data


@patch("core.router.route_request")
def test_calendar_query_empty_text(mock_route, client, auth_headers):
    """Test calendar query with empty text."""
    response = client.post("/api/calendar/query", headers=auth_headers, json={
        "text": ""
    })

    assert response.status_code == 400
    assert "error" in response.json


def test_calendar_query_missing_text(client, auth_headers):
    """Test calendar query without text field."""
    response = client.post("/api/calendar/query", headers=auth_headers, json={})

    assert response.status_code == 400


@patch("core.router.route_request")
def test_calendar_query_default_session(mock_route, client, auth_headers):
    """Test calendar query defaults session_id."""
    mock_route.return_value = {
        "text": "Response",
        "provider": "gpt4"
    }

    response = client.post("/api/calendar/query", headers=auth_headers, json={
        "text": "Show my calendar"
    })

    assert response.status_code == 200


@patch("core.router.route_request")
def test_calendar_query_saves_to_history(mock_route, client, memory, auth_headers):
    """Test calendar query saves to conversation history."""
    mock_route.return_value = {
        "text": "Calendar response",
        "provider": "gpt4",
        "model": "gpt-4"
    }

    session_id = "calendar-session"
    response = client.post("/api/calendar/query", headers=auth_headers, json={
        "text": "What meetings do I have?",
        "session_id": session_id
    })

    assert response.status_code == 200

    # Verify saved to history
    turns = memory.get_recent_turns(session_id)
    assert len(turns) > 0


@patch("core.router.route_request")
def test_calendar_query_error_handling(mock_route, client, auth_headers):
    """Test calendar query handles errors."""
    mock_route.side_effect = Exception("Calendar API error")

    response = client.post("/api/calendar/query", headers=auth_headers, json={
        "text": "Show calendar",
        "session_id": "test"
    })

    assert response.status_code == 500
    data = response.json
    assert "error" in data


@patch("core.router.route_request")
def test_calendar_query_with_m365_integration(mock_route, client, memory, auth_headers, test_user):
    """Test calendar query with M365 credentials."""
    from datetime import datetime, timedelta

    # Store M365 credentials
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.store_m365_credentials(
        user_id=test_user["id"],
        access_token="token",
        refresh_token="refresh",
        expires_at=expires_at
    )

    mock_route.return_value = {
        "text": "Calendar events retrieved",
        "provider": "gpt4"
    }

    response = client.post("/api/calendar/query", headers=auth_headers, json={
        "text": "What's my schedule?",
        "session_id": "test"
    })

    assert response.status_code == 200
