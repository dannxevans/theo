"""
Tests for routine consolidator.

Tests result consolidation and LLM response formatting.
"""

import pytest
from unittest.mock import Mock, patch
from core.routines.consolidator import consolidate_results


@pytest.fixture
def simple_routine_def():
    """Create a simple routine definition."""
    return {
        "name": "Test Routine",
        "consolidation_prompt": "Summarize the following routine results for the user:"
    }


@pytest.fixture
def successful_execution():
    """Create successful execution results."""
    return {
        "routine_name": "Test Routine",
        "actions": [
            {
                "type": "weather",
                "description": "Get weather forecast",
                "status": "success",
                "result": {
                    "text": "Weather in Salford: 3°C, clear sky, feels like -1°C",
                    "provider": "openweather"
                }
            },
            {
                "type": "custom_action",
                "description": "Get motivational quote",
                "status": "success",
                "result": {
                    "text": "The only impossible journey is the one you never begin. - Tony Robbins",
                    "provider": "openai"
                }
            }
        ],
        "success_count": 2,
        "failure_count": 0,
        "partial_success": False
    }


@pytest.fixture
def failed_execution():
    """Create failed execution results."""
    return {
        "routine_name": "Test Routine",
        "actions": [
            {
                "type": "weather",
                "description": "Get weather forecast",
                "status": "failed",
                "error": "API key invalid"
            }
        ],
        "success_count": 0,
        "failure_count": 1,
        "partial_success": False
    }


@pytest.fixture
def partial_execution():
    """Create partial success execution results."""
    return {
        "routine_name": "Test Routine",
        "actions": [
            {
                "type": "weather",
                "description": "Get weather forecast",
                "status": "success",
                "result": {
                    "text": "Weather in Salford: 3°C, clear sky",
                    "provider": "openweather"
                }
            },
            {
                "type": "route",
                "description": "Get route information",
                "status": "failed",
                "error": "Routing service unavailable"
            },
            {
                "type": "custom_action",
                "description": "Get quote",
                "status": "success",
                "result": {
                    "text": "Success is not final, failure is not fatal.",
                    "provider": "openai"
                }
            }
        ],
        "success_count": 2,
        "failure_count": 1,
        "partial_success": True
    }


def test_consolidate_successful_results(simple_routine_def, successful_execution):
    """Test consolidation of successful execution results."""
    mock_router = Mock()
    mock_router.return_value = {
        "text": "Good morning! Here's your weather check: It's 3°C in Salford with clear skies. Your quote: 'The only impossible journey is the one you never begin.'",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    result = consolidate_results(
        simple_routine_def,
        successful_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Verify result structure
    assert "text" in result
    assert "provider" in result
    assert "model" in result
    assert "metadata" in result

    # Verify metadata
    assert result["metadata"]["routine"] == "Test Routine"
    assert result["metadata"]["success_count"] == 2
    assert result["metadata"]["failure_count"] == 0
    assert result["metadata"]["partial_success"] is False

    # Verify router was called
    mock_router.assert_called_once()
    call_context = mock_router.call_args[0][0]
    assert call_context["force_intent"] == "system"  # Lightweight LLM
    assert "Summarize the following routine results" in call_context["text"]


def test_consolidate_failed_results(simple_routine_def, failed_execution):
    """Test consolidation of failed execution results."""
    mock_router = Mock()
    mock_router.return_value = {
        "text": "I encountered an issue running your routine. The weather service returned an API error.",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    result = consolidate_results(
        simple_routine_def,
        failed_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Verify metadata reflects failure
    assert result["metadata"]["success_count"] == 0
    assert result["metadata"]["failure_count"] == 1

    # Verify router was called with failure note
    call_context = mock_router.call_args[0][0]
    assert "Some actions failed" in call_context["text"]


def test_consolidate_partial_success(simple_routine_def, partial_execution):
    """Test consolidation of partial success results."""
    mock_router = Mock()
    mock_router.return_value = {
        "text": "Here's your routine update. Weather: 3°C in Salford. Note: routing info unavailable. Quote: 'Success is not final, failure is not fatal.'",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    result = consolidate_results(
        simple_routine_def,
        partial_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Verify metadata reflects partial success
    assert result["metadata"]["success_count"] == 2
    assert result["metadata"]["failure_count"] == 1
    assert result["metadata"]["partial_success"] is True

    # Verify router received both success and failure info
    call_context = mock_router.call_args[0][0]
    assert "3°C" in call_context["text"]  # Success info
    assert "failed" in call_context["text"].lower() or "unavailable" in call_context["text"].lower()


def test_consolidate_with_custom_prompt(successful_execution):
    """Test consolidation with custom consolidation prompt."""
    routine_def = {
        "name": "Custom Routine",
        "consolidation_prompt": "Present these results in a friendly, conversational tone:"
    }

    mock_router = Mock()
    mock_router.return_value = {
        "text": "Hey there! Here's what I found...",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    result = consolidate_results(
        routine_def,
        successful_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Verify custom prompt was used
    call_context = mock_router.call_args[0][0]
    assert "Present these results in a friendly, conversational tone" in call_context["text"]


def test_consolidate_router_failure_fallback(simple_routine_def, successful_execution):
    """Test fallback when consolidation router fails."""
    mock_router = Mock()
    mock_router.side_effect = Exception("LLM service unavailable")
    mock_memory = Mock()

    result = consolidate_results(
        simple_routine_def,
        successful_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Should return fallback response
    assert result["provider"] == "fallback"
    assert result["metadata"]["consolidation_failed"] is True
    assert "Test Routine" in result["text"]
    # Should include successful action results
    assert "3°C" in result["text"] or "clear sky" in result["text"]


def test_consolidate_all_failed_fallback(simple_routine_def, failed_execution):
    """Test fallback when all actions failed and router fails."""
    mock_router = Mock()
    mock_router.side_effect = Exception("LLM error")
    mock_memory = Mock()

    result = consolidate_results(
        simple_routine_def,
        failed_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Should return fallback with error message
    assert result["provider"] == "fallback"
    assert "all actions failed" in result["text"].lower()


def test_consolidate_partial_failure_fallback(simple_routine_def, partial_execution):
    """Test fallback when partial success and router fails."""
    mock_router = Mock()
    mock_router.side_effect = Exception("LLM error")
    mock_memory = Mock()

    result = consolidate_results(
        simple_routine_def,
        partial_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Should return fallback with partial success message
    assert result["provider"] == "fallback"
    assert "some actions" in result["text"].lower() or "couldn't be completed" in result["text"].lower()
    # Should include successful results
    assert "3°C" in result["text"] or "clear sky" in result["text"]


def test_consolidate_uses_system_intent(simple_routine_def, successful_execution):
    """Test that consolidation uses lightweight LLM (system intent)."""
    mock_router = Mock()
    mock_router.return_value = {
        "text": "Consolidated response",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    consolidate_results(
        simple_routine_def,
        successful_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Verify system intent was used for lightweight LLM
    call_context = mock_router.call_args[0][0]
    assert call_context["force_intent"] == "system"


def test_consolidate_empty_actions():
    """Test consolidation with no actions."""
    routine_def = {
        "name": "Empty Routine",
        "consolidation_prompt": "Summarize:"
    }
    execution_results = {
        "routine_name": "Empty Routine",
        "actions": [],
        "success_count": 0,
        "failure_count": 0,
        "partial_success": False
    }

    mock_router = Mock()
    mock_router.return_value = {
        "text": "No actions were executed.",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    result = consolidate_results(
        routine_def,
        execution_results,
        mock_router,
        mock_memory,
        user_id="local"
    )

    assert result["metadata"]["success_count"] == 0
    assert result["metadata"]["failure_count"] == 0


def test_consolidate_prompt_includes_all_actions(simple_routine_def, partial_execution):
    """Test that consolidation prompt includes all actions (success and failure)."""
    mock_router = Mock()
    mock_router.return_value = {
        "text": "Consolidated",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    consolidate_results(
        simple_routine_def,
        partial_execution,
        mock_router,
        mock_memory,
        user_id="local"
    )

    # Verify all actions are in the prompt
    call_text = mock_router.call_args[0][0]["text"]
    assert "weather" in call_text.lower()
    assert "route" in call_text.lower()
    assert "quote" in call_text.lower()
    # Check for success indicators
    assert "Success" in call_text or "✓" in call_text
    # Check for failure indicators
    assert "Failed" in call_text or "✗" in call_text


def test_consolidate_user_id_passed_through(simple_routine_def, successful_execution):
    """Test that user_id is correctly passed to router."""
    mock_router = Mock()
    mock_router.return_value = {
        "text": "Result",
        "provider": "openai",
        "model": "gpt-4"
    }
    mock_memory = Mock()

    consolidate_results(
        simple_routine_def,
        successful_execution,
        mock_router,
        mock_memory,
        user_id="test-user-123"
    )

    call_context = mock_router.call_args[0][0]
    assert call_context["user_id"] == "test-user-123"
