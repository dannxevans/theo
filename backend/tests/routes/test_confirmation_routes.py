"""
Tests for confirmation routes.

Tests pending confirmations, approval, and rejection.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock


def test_get_pending_confirmations_unauthorized(client):
    """Test get pending confirmations requires authentication."""
    response = client.get("/api/confirmations/pending")

    assert response.status_code == 401


def test_get_pending_confirmations_empty(client, auth_headers):
    """Test get pending confirmations when none exist."""
    response = client.get("/api/confirmations/pending", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert "confirmations" in data
    assert data["count"] == 0


def test_get_pending_confirmations(client, memory, auth_headers, test_user):
    """Test get pending confirmations."""
    # Create an action
    action_id = memory.create_action(
        user_id=test_user["id"],
        session_id="test-session",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create meeting"
    )

    # Create confirmation
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Create event?",
        expires_at=expires_at
    )

    response = client.get("/api/confirmations/pending", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["count"] > 0
    assert len(data["confirmations"]) > 0

    # Check confirmation structure
    conf = data["confirmations"][0]
    assert "confirmation_id" in conf
    assert "action_id" in conf
    assert "message" in conf


@patch("core.confirmation_manager.ConfirmationManager.approve_confirmation")
def test_approve_confirmation_success(mock_approve, client, memory, auth_headers, test_user):
    """Test approve confirmation."""
    # Create action and confirmation
    action_id = memory.create_action(
        user_id=test_user["id"],
        session_id="test",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create event"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve?",
        expires_at=expires_at
    )

    # Mock approval
    mock_approve.return_value = {
        "status": "success",
        "message": "Action approved",
        "action_result": {"created": True}
    }

    response = client.post(f"/api/confirmations/{conf_id}/approve", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "approved"


@patch("core.confirmation_manager.ConfirmationManager.approve_confirmation")
def test_approve_confirmation_error(mock_approve, client, auth_headers):
    """Test approve confirmation with error."""
    mock_approve.return_value = {
        "status": "error",
        "message": "Confirmation not found"
    }

    response = client.post("/api/confirmations/99999/approve", headers=auth_headers)

    assert response.status_code == 400
    data = response.json
    assert data["status"] == "error"


def test_approve_confirmation_unauthorized(client):
    """Test approve confirmation requires authentication."""
    response = client.post("/api/confirmations/1/approve")

    assert response.status_code == 401


@patch("core.confirmation_manager.ConfirmationManager.reject_confirmation")
def test_reject_confirmation_success(mock_reject, client, memory, auth_headers, test_user):
    """Test reject confirmation."""
    # Create action and confirmation
    action_id = memory.create_action(
        user_id=test_user["id"],
        session_id="test",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create event"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve?",
        expires_at=expires_at
    )

    # Mock rejection
    mock_reject.return_value = {
        "status": "success",
        "message": "Action rejected"
    }

    response = client.post(f"/api/confirmations/{conf_id}/reject", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "rejected"


@patch("core.confirmation_manager.ConfirmationManager.reject_confirmation")
def test_reject_confirmation_with_reason(mock_reject, client, auth_headers):
    """Test reject confirmation with reason."""
    mock_reject.return_value = {
        "status": "success",
        "message": "Rejected"
    }

    response = client.post("/api/confirmations/1/reject", headers=auth_headers, json={
        "reason": "Not needed"
    })

    assert response.status_code == 200


@patch("core.confirmation_manager.ConfirmationManager.reject_confirmation")
def test_reject_confirmation_without_reason(mock_reject, client, auth_headers):
    """Test reject confirmation without reason."""
    mock_reject.return_value = {
        "status": "success",
        "message": "Rejected"
    }

    response = client.post("/api/confirmations/1/reject", headers=auth_headers)

    assert response.status_code == 200


@patch("core.confirmation_manager.ConfirmationManager.reject_confirmation")
def test_reject_confirmation_error(mock_reject, client, auth_headers):
    """Test reject confirmation with error."""
    mock_reject.return_value = {
        "status": "error",
        "message": "Confirmation not found"
    }

    response = client.post("/api/confirmations/99999/reject", headers=auth_headers)

    assert response.status_code == 400


def test_reject_confirmation_unauthorized(client):
    """Test reject confirmation requires authentication."""
    response = client.post("/api/confirmations/1/reject")

    assert response.status_code == 401


def test_confirmation_lifecycle(client, memory, auth_headers, test_user):
    """Test full confirmation lifecycle."""
    # Create action
    action_id = memory.create_action(
        user_id=test_user["id"],
        session_id="test",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create meeting"
    )

    # Create confirmation
    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Create this event?",
        expires_at=expires_at
    )

    # Get pending confirmations
    response = client.get("/api/confirmations/pending", headers=auth_headers)
    assert response.status_code == 200
    assert response.json["count"] > 0

    # Approve it (will fail without mock but tests the flow)
    with patch("core.confirmation_manager.ConfirmationManager.approve_confirmation") as mock:
        mock.return_value = {"status": "success", "message": "Done"}
        response = client.post(f"/api/confirmations/{conf_id}/approve", headers=auth_headers)
        assert response.status_code == 200
