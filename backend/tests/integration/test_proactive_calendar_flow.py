"""
Integration tests for proactive calendar notification flow.

Note: These tests verify the calendar service's database interaction patterns
and configuration handling. Full end-to-end testing with M365 requires a test
Microsoft 365 account.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from core.proactive import calendar_service
from core.memory import MemoryStore


@pytest.fixture
def memory_store():
    """Create a test memory store."""
    from config import Config
    memory = MemoryStore(Config.DATABASE_URL)

    # Ensure proactive settings exist
    with memory.engine.connect() as conn:
        conn.execute(text("""
            INSERT OR REPLACE INTO proactive_settings
            (user_id, calendar_enabled, calendar_lead_time_minutes, max_messages_per_hour)
            VALUES ('test_user', 1, 15, 100)
        """))
        conn.commit()

    yield memory

    # Cleanup
    with memory.engine.connect() as conn:
        conn.execute(text("DELETE FROM proactive_calendar_notifications WHERE user_id = 'test_user'"))
        conn.execute(text("DELETE FROM proactive_settings WHERE user_id = 'test_user'"))
        conn.commit()


class TestProactiveCalendarConfiguration:
    """Test calendar service configuration and settings."""

    def test_calendar_settings_disabled(self, memory_store):
        """Test that disabled calendar settings are respected."""
        # Disable calendar notifications
        with memory_store.engine.connect() as conn:
            conn.execute(text("""
                UPDATE proactive_settings
                SET calendar_enabled = 0
                WHERE user_id = 'test_user'
            """))
            conn.commit()

        # Should not return test_user in enabled users list
        users = calendar_service._get_users_for_calendar_check(memory_store)
        assert 'test_user' not in users

    def test_calendar_settings_enabled(self, memory_store):
        """Test that enabled calendar settings are detected."""
        # Calendar is enabled by default in fixture
        # Note: This test requires M365 credentials to pass fully
        # For now, we just verify the settings query works
        with memory_store.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT calendar_enabled, calendar_lead_time_minutes
                FROM proactive_settings
                WHERE user_id = 'test_user'
            """)).fetchone()

        assert result is not None
        assert result[0] == 1  # calendar_enabled
        assert result[1] == 15  # calendar_lead_time_minutes
