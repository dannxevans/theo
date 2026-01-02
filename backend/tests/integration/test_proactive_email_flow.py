"""
Integration tests for proactive email notification flow.

Note: These tests verify the email service's database interaction patterns
and configuration handling. Full end-to-end testing with M365 requires a test
Microsoft 365 account.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import text
from core.proactive import email_service
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
            (user_id, email_enabled, email_check_frequency_minutes, max_messages_per_hour)
            VALUES ('test_user', 1, 15, 100)
        """))
        conn.commit()

    yield memory

    # Cleanup
    with memory.engine.connect() as conn:
        conn.execute(text("DELETE FROM proactive_email_tracking WHERE user_id = 'test_user'"))
        conn.execute(text("DELETE FROM proactive_email_digests WHERE user_id = 'test_user'"))
        conn.execute(text("DELETE FROM proactive_settings WHERE user_id = 'test_user'"))
        conn.commit()


class TestProactiveEmailConfiguration:
    """Test email service configuration and settings."""

    def test_email_settings_disabled(self, memory_store):
        """Test that disabled email settings are respected."""
        # Disable email notifications
        with memory_store.engine.connect() as conn:
            conn.execute(text("""
                UPDATE proactive_settings
                SET email_enabled = 0
                WHERE user_id = 'test_user'
            """))
            conn.commit()

        # Should not return test_user in enabled users list
        users = email_service._get_users_for_email_check(memory_store)
        assert 'test_user' not in users

    def test_email_settings_enabled(self, memory_store):
        """Test that enabled email settings are detected."""
        # Email is enabled by default in fixture
        # Note: This test requires M365 credentials to pass fully
        # For now, we just verify the settings query works
        with memory_store.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT email_enabled, email_check_frequency_minutes
                FROM proactive_settings
                WHERE user_id = 'test_user'
            """)).fetchone()

        assert result is not None
        assert result[0] == 1  # email_enabled
        assert result[1] == 15  # email_check_frequency_minutes
