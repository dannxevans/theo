"""
Tests for routine executor.

Tests routine execution, action routing, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.routines.executor import execute_routine, _execute_action


@pytest.fixture
def mock_context():
    """Create mock execution context."""
    return {
        "session_id": "test-session-123",
        "user_id": 1,
        "mode": "personal",
        "action_router": Mock(),
        "memory": Mock()
    }


@pytest.fixture
def simple_routine():
    """Create a simple routine definition."""
    return {
        "name": "Test Routine",
        "actions": [
            {
                "type": "custom_action",
                "description": "Say hello",
                "customPrompt": "Say hello"
            }
        ]
    }


@pytest.fixture
def weather_routine():
    """Create a weather-based routine."""
    return {
        "name": "Weather Check",
        "actions": [
            {
                "type": "weather",
                "description": "Get weather forecast for Work"
            }
        ]
    }


@pytest.fixture
def routing_routine():
    """Create a routing-based routine."""
    return {
        "name": "Commute Check",
        "actions": [
            {
                "type": "route",
                "description": "Get route and traffic information from Home to Work"
            }
        ]
    }


@pytest.fixture
def complex_routine():
    """Create a complex multi-action routine."""
    return {
        "name": "Morning Routine",
        "actions": [
            {
                "type": "weather",
                "description": "Get weather forecast for Work"
            },
            {
                "type": "route",
                "description": "Get route and traffic information from Home to Work"
            },
            {
                "type": "custom_action",
                "description": "Give me a motivational quote",
                "customPrompt": "Give me a motivational quote"
            }
        ]
    }


def test_execute_routine_success(simple_routine, mock_context):
    """Test successful routine execution."""
    # Mock action router response
    mock_context["action_router"].route_action_request.return_value = {
        "text": "Hello! How can I help you?",
        "provider": "openai",
        "model": "gpt-4"
    }

    with patch('core.router.route_request') as mock_route:
        mock_route.return_value = {
            "text": "Hello! How can I help you?",
            "provider": "openai",
            "model": "gpt-4"
        }

        result = execute_routine(simple_routine, mock_context)

    assert result["routine_name"] == "Test Routine"
    assert result["success_count"] == 1
    assert result["failure_count"] == 0
    assert result["partial_success"] is False
    assert len(result["actions"]) == 1
    assert result["actions"][0]["status"] == "success"
    assert result["actions"][0]["type"] == "custom_action"


def test_execute_routine_empty_actions(mock_context):
    """Test routine with no actions."""
    routine = {
        "name": "Empty Routine",
        "actions": []
    }

    result = execute_routine(routine, mock_context)

    assert result["routine_name"] == "Empty Routine"
    assert result["success_count"] == 0
    assert result["failure_count"] == 0
    assert len(result["actions"]) == 0


def test_execute_routine_action_failure(simple_routine, mock_context):
    """Test routine with failing action."""
    with patch('core.router.route_request') as mock_route:
        mock_route.side_effect = Exception("API Error")

        result = execute_routine(simple_routine, mock_context)

    assert result["routine_name"] == "Test Routine"
    assert result["success_count"] == 0
    assert result["failure_count"] == 1
    assert result["partial_success"] is False
    assert len(result["actions"]) == 1
    assert result["actions"][0]["status"] == "failed"
    assert "API Error" in result["actions"][0]["error"]


def test_execute_routine_partial_success(complex_routine, mock_context):
    """Test routine with mixed success/failure."""
    call_count = [0]

    def mock_route_side_effect(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 2:  # Fail on second call (routing)
            raise Exception("Routing service unavailable")
        return {
            "text": "Success",
            "provider": "openai",
            "model": "gpt-4"
        }

    with patch('core.router.route_request') as mock_route:
        mock_route.side_effect = mock_route_side_effect

        result = execute_routine(complex_routine, mock_context)

    assert result["routine_name"] == "Morning Routine"
    assert result["success_count"] == 2  # weather and custom action
    assert result["failure_count"] == 1  # routing
    assert result["partial_success"] is True
    assert len(result["actions"]) == 3


def test_execute_weather_action(mock_context):
    """Test weather action execution."""
    mock_context["memory"].get_relevant_memories.return_value = [
        {"key": "Work Location", "value": "Soapworks, Colgate Ln, Salford M5 3LZ"}
    ]

    with patch('core.router.route_request') as mock_route, \
         patch('app.context_manager') as mock_cm:

        mock_cm.build_context.return_value = {"facts": [], "recent_turns": []}
        mock_route.return_value = {
            "text": "Weather in Salford: 3°C, clear sky",
            "provider": "openweather",
            "model": None
        }

        result = _execute_action(
            action_type="weather",
            params={},
            session_id="test-session",
            user_id=1,
            mode="personal",
            action_router=mock_context["action_router"],
            memory=mock_context["memory"],
            action_description="Get weather forecast for Work"
        )

    assert result is not None
    assert "text" in result
    mock_route.assert_called_once()


def test_execute_routing_action(mock_context):
    """Test routing action execution."""
    mock_context["memory"].get_relevant_memories.return_value = [
        {"key": "Home Location", "value": "8 Harefields Way, Wirral. CH494SB"},
        {"key": "Work Location", "value": "Soapworks, Colgate Ln, Salford M5 3LZ"}
    ]

    with patch('core.router.route_request') as mock_route, \
         patch('app.context_manager') as mock_cm:

        mock_cm.build_context.return_value = {"facts": [], "recent_turns": []}
        mock_route.return_value = {
            "text": "Route: 66 km, 55 minutes",
            "provider": "here",
            "model": None
        }

        result = _execute_action(
            action_type="route",
            params={},
            session_id="test-session",
            user_id=1,
            mode="personal",
            action_router=mock_context["action_router"],
            memory=mock_context["memory"],
            action_description="Get route and traffic information from Home to Work"
        )

    assert result is not None
    assert "text" in result
    mock_route.assert_called_once()


def test_execute_custom_action(mock_context):
    """Test custom action execution."""
    with patch('core.router.route_request') as mock_route, \
         patch('app.context_manager') as mock_cm:

        mock_cm.build_context.return_value = {"facts": [], "recent_turns": []}
        mock_route.return_value = {
            "text": "Here's a motivational quote: ...",
            "provider": "openai",
            "model": "gpt-4"
        }

        result = _execute_action(
            action_type="custom_action",
            params={},
            session_id="test-session",
            user_id=1,
            mode="personal",
            action_router=mock_context["action_router"],
            memory=mock_context["memory"],
            custom_prompt="Give me a motivational quote",
            action_description="Give me a motivational quote"
        )

    assert result is not None
    assert "text" in result
    mock_route.assert_called_once()
    # Verify force_intent was set to "general"
    call_context = mock_route.call_args[0][0]
    assert call_context["force_intent"] == "general"


def test_execute_custom_action_missing_prompt(mock_context):
    """Test custom action without custom prompt."""
    with pytest.raises(ValueError, match="Custom action requires a custom prompt"):
        _execute_action(
            action_type="custom_action",
            params={},
            session_id="test-session",
            user_id=1,
            mode="personal",
            action_router=mock_context["action_router"],
            memory=mock_context["memory"],
            custom_prompt=None,
            action_description="Custom action"
        )


def test_execute_unknown_action_type(mock_context):
    """Test unknown action type."""
    with pytest.raises(ValueError, match="Unknown action type"):
        _execute_action(
            action_type="unknown_action",
            params={},
            session_id="test-session",
            user_id=1,
            mode="personal",
            action_router=mock_context["action_router"],
            memory=mock_context["memory"]
        )


def test_execute_email_check_action(mock_context):
    """Test email check action."""
    result = _execute_action(
        action_type="email_check",
        params={"filter": "important", "unread_only": True},
        session_id="test-session",
        user_id=1,
        mode="personal",
        action_router=mock_context["action_router"],
        memory=mock_context["memory"]
    )

    # Should call action router
    mock_context["action_router"].route_action_request.assert_called_once()
    call_args = mock_context["action_router"].route_action_request.call_args[0][0]
    assert call_args["intent"] == "read_email"
    assert call_args["filter"] == "important"
    assert call_args["unread_only"] is True


def test_execute_calendar_read_action(mock_context):
    """Test calendar read action."""
    result = _execute_action(
        action_type="calendar_read",
        params={"timeframe": "today"},
        session_id="test-session",
        user_id=1,
        mode="personal",
        action_router=mock_context["action_router"],
        memory=mock_context["memory"]
    )

    # Should call action router
    mock_context["action_router"].route_action_request.assert_called_once()
    call_args = mock_context["action_router"].route_action_request.call_args[0][0]
    assert call_args["intent"] == "read_calendar"
    assert "calendar" in call_args["text"].lower()


def test_routine_context_preservation(simple_routine, mock_context):
    """Test that routine preserves context across actions."""
    with patch('core.router.route_request') as mock_route:
        mock_route.return_value = {"text": "Success", "provider": "test", "model": "test"}

        result = execute_routine(simple_routine, mock_context)

    # Verify session_id and user_id were passed through
    call_context = mock_route.call_args[0][0]
    assert call_context["session_id"] == "test-session-123"
    assert call_context["user_id"] == 1
    assert call_context["mode"] == "personal"
