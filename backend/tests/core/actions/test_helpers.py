"""
Unit tests for action helpers.

Tests date parsing, formatting, and utility functions.
"""

import pytest
from datetime import datetime, timedelta
from core.actions.helpers import (
    parse_date_range,
    format_date_range,
    format_event_list,
    detect_service_category,
    parse_m365_datetime
)


class TestDateParsing:
    """Test date parsing functions."""

    def test_parse_today(self):
        """Test parsing 'today' returns today's date range."""
        start, end = parse_date_range("What's on my calendar today?")
        assert start.date() == datetime.now().date()
        assert end.date() == datetime.now().date()
        assert start.hour == 0
        assert end.hour == 23

    def test_parse_tomorrow(self):
        """Test parsing 'tomorrow' returns tomorrow's date range."""
        start, end = parse_date_range("What's on tomorrow?")
        tomorrow = datetime.now() + timedelta(days=1)
        assert start.date() == tomorrow.date()
        assert end.date() == tomorrow.date()

    def test_parse_day_of_week(self):
        """Test parsing day names returns correct future day."""
        start, end = parse_date_range("What's on Tuesday?")
        assert start.weekday() == 1  # Tuesday
        assert start > datetime.now()  # Should be in the future

    def test_parse_this_week(self):
        """Test parsing 'this week' returns current week range."""
        start, end = parse_date_range("this week")
        assert start.weekday() == 0  # Monday
        assert (end - start).days == 6  # Full week

    def test_parse_next_week(self):
        """Test parsing 'next week' returns next week range."""
        start, end = parse_date_range("next week")
        assert start.weekday() == 0  # Monday
        assert start > datetime.now()  # Future
        assert (end - start).days == 6


class TestDateFormatting:
    """Test date formatting functions."""

    def test_format_single_day(self):
        """Test formatting same-day range."""
        date = datetime(2025, 12, 26)
        end = datetime(2025, 12, 26, 23, 59, 59)
        result = format_date_range(date, end)
        assert "Friday" in result
        assert "December 26" in result
        assert result.startswith("on ")

    def test_format_multiple_days_same_month(self):
        """Test formatting multi-day range in same month."""
        start = datetime(2025, 12, 26)
        end = datetime(2025, 12, 28)
        result = format_date_range(start, end)
        assert "December 26" in result
        assert "to 28" in result

    def test_format_different_months(self):
        """Test formatting range across months."""
        start = datetime(2025, 12, 26)
        end = datetime(2026, 1, 5)
        result = format_date_range(start, end)
        assert "December 26" in result
        assert "January 5" in result


class TestEventFormatting:
    """Test event list formatting."""

    def test_format_empty_list(self):
        """Test formatting empty event list."""
        result = format_event_list([])
        assert result == ""

    def test_format_single_event(self):
        """Test formatting single event."""
        events = [{
            "subject": "Meeting",
            "start_time": "2025-12-26T09:00:00",
            "location": "Office"
        }]
        result = format_event_list(events)
        assert "Meeting" in result
        assert "9:00 AM" in result
        assert "Office" in result

    def test_format_event_with_attendees(self):
        """Test formatting event with attendees."""
        events = [{
            "subject": "Team Sync",
            "start_time": "2025-12-26T14:00:00",
            "attendees": ["Alice", "Bob", "Charlie"]
        }]
        result = format_event_list(events)
        assert "Team Sync" in result
        assert "3 attendees" in result

    def test_format_multiday_events(self):
        """Test formatting events with show_date flag."""
        events = [{
            "subject": "Conference",
            "start_time": "2025-12-26T09:00:00"
        }]
        result = format_event_list(events, show_date=True)
        assert "Friday, December 26" in result
        assert "Conference" in result


class TestServiceDetection:
    """Test service category detection."""

    def test_detect_haircut(self):
        """Test detecting haircut service."""
        assert detect_service_category("book a haircut") == "haircut"
        assert detect_service_category("I need a trim") == "haircut"
        assert detect_service_category("barber appointment") == "haircut"

    def test_detect_doctor(self):
        """Test detecting doctor service."""
        assert detect_service_category("schedule doctor appointment") == "doctor"
        assert detect_service_category("see my physician") == "doctor"
        assert detect_service_category("medical checkup") == "doctor"

    def test_detect_dentist(self):
        """Test detecting dentist service."""
        assert detect_service_category("dentist appointment") == "dentist"
        assert detect_service_category("teeth cleaning") == "dentist"

    def test_detect_no_service(self):
        """Test no service detected."""
        assert detect_service_category("book a meeting") == ""
        assert detect_service_category("schedule a call") == ""


class TestM365DateTimeParsing:
    """Test M365 datetime parsing."""

    def test_parse_7_digit_microseconds(self):
        """Test parsing M365 datetime with 7-digit microseconds."""
        dt_string = "2025-12-28T15:00:00.0000000"
        result = parse_m365_datetime(dt_string)
        assert result.year == 2025
        assert result.month == 12
        assert result.day == 28
        assert result.hour == 15

    def test_parse_with_z_timezone(self):
        """Test parsing datetime with Z timezone indicator."""
        dt_string = "2025-12-28T15:00:00Z"
        result = parse_m365_datetime(dt_string)
        assert result.year == 2025
        assert result.hour == 15

    def test_parse_fallback_without_microseconds(self):
        """Test fallback parsing when format is invalid."""
        # Should not raise exception
        dt_string = "2025-12-28T15:00:00"
        result = parse_m365_datetime(dt_string)
        assert result.year == 2025


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
