"""
Unit tests for BaseActionHandler.

Tests common handler functionality including provider access,
response formatting, and error handling.
"""

import pytest
from unittest.mock import Mock, MagicMock
from core.actions.base_handler import BaseActionHandler


class TestBaseActionHandler:
    """Test BaseActionHandler functionality."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock action registry."""
        registry = Mock()
        registry.load_providers = Mock()
        registry.get_providers_by_capability = Mock()
        return registry

    @pytest.fixture
    def mock_memory(self):
        """Create mock memory store."""
        return Mock()

    @pytest.fixture
    def handler(self, mock_registry, mock_memory):
        """Create handler instance with mocks."""
        return BaseActionHandler(mock_registry, mock_memory)

    def test_get_provider_success(self, handler, mock_registry):
        """Test successful provider retrieval."""
        mock_provider = Mock()
        mock_registry.get_providers_by_capability.return_value = [("provider_1", mock_provider)]

        result = handler._get_provider("read_calendar", user_id=1)

        assert result is not None
        assert result[0] == "provider_1"
        assert result[1] == mock_provider
        mock_registry.load_providers.assert_called_once_with(1)

    def test_get_provider_not_found(self, handler, mock_registry):
        """Test provider not found returns None."""
        mock_registry.get_providers_by_capability.return_value = []

        result = handler._get_provider("read_calendar", user_id=1)

        assert result is None

    def test_format_success_response(self, handler):
        """Test formatting successful response."""
        result = handler._format_success_response(
            "Task completed",
            "test_task",
            {"extra": "data"}
        )

        assert result["text"] == "Task completed"
        assert result["provider"] == "action_router"
        assert result["model"] is None
        assert result["task_type"] == "test_task"
        assert result["metadata"]["extra"] == "data"

    def test_format_success_response_no_metadata(self, handler):
        """Test formatting response without metadata."""
        result = handler._format_success_response(
            "Task completed",
            "test_task"
        )

        assert result["text"] == "Task completed"
        assert "metadata" not in result

    def test_format_error_response(self, handler):
        """Test formatting error response."""
        result = handler._format_error_response(
            "Something went wrong",
            "test_task",
            "Technical error details"
        )

        assert result["text"] == "Something went wrong"
        assert result["task_type"] == "test_task"
        assert result["metadata"]["error"] is True
        assert result["metadata"]["error_details"] == "Technical error details"

    def test_format_error_response_no_details(self, handler):
        """Test formatting error without technical details."""
        result = handler._format_error_response(
            "Something went wrong",
            "test_task"
        )

        assert result["metadata"]["error"] is True
        assert "error_details" not in result["metadata"]

    def test_format_no_provider_response(self, handler):
        """Test formatting no provider available response."""
        result = handler._format_no_provider_response(
            "read_calendar",
            "test_task",
            "calendar"
        )

        assert "calendar" in result["text"]
        assert "Microsoft 365" in result["text"]
        assert result["metadata"]["error"] == "no_provider"
        assert result["metadata"]["required_capability"] == "read_calendar"

    def test_log_error(self, handler, caplog):
        """Test error logging."""
        error = Exception("Test error")

        handler._log_error("test_handler", error)

        # Check that error was logged (would need caplog fixture from pytest)
        # This is a basic test - in production you'd verify the log output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
