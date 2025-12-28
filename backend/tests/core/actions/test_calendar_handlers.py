"""
Unit tests for CalendarHandlers.

Tests calendar action handling including read, book, update, cancel operations.
"""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, timedelta
from core.actions.calendar_handlers import CalendarHandlers


class TestCalendarHandlers:
    """Test CalendarHandlers functionality."""

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
    def mock_confirmation_manager(self):
        """Create mock confirmation manager."""
        return Mock()

    @pytest.fixture
    def handler(self, mock_registry, mock_memory, mock_confirmation_manager):
        """Create handler instance with mocks."""
        return CalendarHandlers(mock_registry, mock_memory, mock_confirmation_manager)

    def test_handle_read_calendar_no_provider(self, handler, mock_registry):
        """Test read calendar when no provider available."""
        mock_registry.get_providers_by_capability.return_value = []

        result = handler.handle_read_calendar(
            "What's on my calendar tomorrow?",
            "session_123",
            1,
            {}
        )

        assert "calendar" in result["text"].lower()
        assert result["metadata"]["error"] == "no_provider"

    def test_handle_read_calendar_no_events(self, handler, mock_registry):
        """Test read calendar with no events."""
        mock_provider = Mock()
        mock_provider.read_calendar.return_value = []
        mock_registry.get_providers_by_capability.return_value = [("provider_1", mock_provider)]

        result = handler.handle_read_calendar(
            "What's on tomorrow?",
            "session_123",
            1,
            {}
        )

        assert "no upcoming events" in result["text"].lower()
        assert result["metadata"]["events_count"] == 0

    def test_handle_read_calendar_with_events(self, handler, mock_registry):
        """Test read calendar with events."""
        mock_provider = Mock()
        future_time = (datetime.now() + timedelta(days=1)).isoformat()
        mock_provider.read_calendar.return_value = [{
            "subject": "Meeting",
            "start_time": future_time,
            "location": "Office"
        }]
        mock_registry.get_providers_by_capability.return_value = [("provider_1", mock_provider)]

        result = handler.handle_read_calendar(
            "What's on tomorrow?",
            "session_123",
            1,
            {}
        )

        assert "Meeting" in result["text"]
        assert result["metadata"]["events_count"] == 1

    def test_handle_read_calendar_flight_query(self, handler, mock_registry):
        """Test read calendar with flight-specific query."""
        mock_provider = Mock()
        future_time = (datetime.now() + timedelta(days=7)).isoformat()
        mock_provider.read_calendar.return_value = [{
            "subject": "Flight to NYC",
            "start_time": future_time,
            "location": "Airport"
        }]
        mock_registry.get_providers_by_capability.return_value = [("provider_1", mock_provider)]

        result = handler.handle_read_calendar(
            "When is my flight?",
            "session_123",
            1,
            {}
        )

        assert "flight" in result["text"].lower()
        assert result["metadata"]["flight_query"] is True

    def test_handle_book_appointment_no_confirmation_manager(self, mock_registry, mock_memory):
        """Test book appointment without confirmation manager."""
        handler = CalendarHandlers(mock_registry, mock_memory, confirmation_manager=None)

        result = handler.handle_book_appointment(
            "Add lunch at 1pm today",
            "session_123",
            1,
            {}
        )

        assert "confirmation system" in result["text"].lower()

    def test_handle_cancel_appointment_no_provider(self, handler, mock_registry):
        """Test cancel appointment when no provider available."""
        mock_registry.get_providers_by_capability.return_value = []

        result = handler.handle_cancel_appointment(
            "Cancel my meeting today",
            "session_123",
            1,
            {}
        )

        assert result["metadata"]["error"] == "no_provider"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
