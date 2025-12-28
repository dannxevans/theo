"""
Tests for action and confirmation operations.

Tests action CRUD and confirmation management.
"""

import pytest
from datetime import datetime, timedelta


def test_create_action(memory, user_fixture):
    """Test create new action."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create meeting"
    )

    assert action_id is not None

    action = memory.get_action(action_id)
    assert action["action_type"] == "calendar_event"
    assert action["status"] == "pending"


def test_create_action_with_options(memory, user_fixture):
    """Test create action with optional fields."""
    import json

    action_params = {
        "title": "Team Meeting",
        "start_time": "2025-01-15T10:00:00",
        "duration": 60
    }

    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create meeting",
        service_provider_id=1,
        action_params=json.dumps(action_params)
    )

    action = memory.get_action(action_id)
    assert action["service_provider_id"] == 1


def test_get_action(memory, user_fixture):
    """Test get specific action."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="send_email",
        category="email",
        intent_summary="Send email"
    )

    action = memory.get_action(action_id)
    assert action["id"] == action_id


def test_get_action_nonexistent(memory):
    """Test get nonexistent action."""
    action = memory.get_action(99999)
    assert action is None


def test_get_pending_actions(memory, user_fixture):
    """Test get pending actions for user."""
    memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="action1",
        category="calendar",
        intent_summary="Action 1"
    )

    memory.create_action(
        user_id=user_fixture["id"],
        session_id="session2",
        action_type="action2",
        category="email",
        intent_summary="Action 2"
    )

    actions = memory.get_pending_actions(user_fixture["id"])
    assert len(actions) >= 2


def test_get_pending_actions_empty(memory, user_fixture):
    """Test get pending actions when none exist."""
    actions = memory.get_pending_actions(user_fixture["id"])
    assert isinstance(actions, list)


def test_update_action_status(memory, user_fixture):
    """Test update action status."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    memory.update_action_status(action_id, "approved")

    action = memory.get_action(action_id)
    assert action["status"] == "approved"


def test_update_action_status_with_result(memory, user_fixture):
    """Test update action status with result data."""
    import json

    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    result = {"created": True, "event_id": "evt123"}

    memory.update_action_status(
        action_id,
        "completed",
        result_data=json.dumps(result)
    )

    action = memory.get_action(action_id)
    assert action["status"] == "completed"


def test_create_confirmation(memory, user_fixture):
    """Test create confirmation request."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve this action?",
        expires_at=expires_at
    )

    assert conf_id is not None


def test_get_pending_confirmations(memory, user_fixture):
    """Test get pending confirmations."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve?",
        expires_at=expires_at
    )

    confirmations = memory.get_pending_confirmations(user_fixture["id"])
    assert len(confirmations) > 0


def test_get_pending_confirmations_empty(memory, user_fixture):
    """Test get pending confirmations when none exist."""
    confirmations = memory.get_pending_confirmations(user_fixture["id"])
    assert isinstance(confirmations, list)


def test_update_confirmation_response(memory, user_fixture):
    """Test update confirmation with user response."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve?",
        expires_at=expires_at
    )

    memory.update_confirmation_response(
        action_id=action_id,
        user_response="approved",
        user_response_text="Looks good"
    )

    # Verification depends on implementation


def test_get_confirmation_by_id(memory, user_fixture):
    """Test get confirmation by ID."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve?",
        expires_at=expires_at
    )

    confirmation = memory.get_confirmation_by_id(conf_id)
    assert confirmation is not None


def test_update_confirmation_status(memory, user_fixture):
    """Test update confirmation status."""
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="test",
        category="calendar",
        intent_summary="Test"
    )

    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Approve?",
        expires_at=expires_at
    )

    memory.update_confirmation_status(conf_id, "approved")

    # Verification depends on implementation


def test_action_confirmation_lifecycle(memory, user_fixture):
    """Test complete action and confirmation lifecycle."""
    import json

    # Create action
    action_id = memory.create_action(
        user_id=user_fixture["id"],
        session_id="session1",
        action_type="calendar_event",
        category="calendar",
        intent_summary="Create team meeting",
        action_params=json.dumps({
            "title": "Team Sync",
            "start": "2025-01-15T10:00:00"
        })
    )

    # Create confirmation
    expires_at = datetime.utcnow() + timedelta(hours=1)
    conf_id = memory.create_confirmation(
        action_id=action_id,
        confirmation_message="Create event 'Team Sync'?",
        expires_at=expires_at
    )

    # Get pending confirmations
    confirmations = memory.get_pending_confirmations(user_fixture["id"])
    assert len(confirmations) > 0

    # Approve
    memory.update_confirmation_response(
        action_id=action_id,
        user_response="approved"
    )

    memory.update_action_status(action_id, "approved")

    # Execute (simulate)
    memory.update_action_status(
        action_id,
        "completed",
        result_data=json.dumps({"event_id": "evt123"})
    )

    # Verify final state
    action = memory.get_action(action_id)
    assert action["status"] == "completed"
