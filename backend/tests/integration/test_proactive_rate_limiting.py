"""
Integration tests for proactive notification rate limiting and quiet hours.

Tests notification suppression based on rate limits and quiet hours settings.
"""

import pytest
from datetime import datetime, time, timedelta
from unittest.mock import patch
from sqlalchemy import text
from core.proactive import notification_limiter, quiet_hours
from core.memory import MemoryStore


@pytest.fixture
def memory_store():
    """Create a test memory store."""
    from config import Config
    from sqlalchemy import text
    memory = MemoryStore(Config.DATABASE_URL)

    # Set up test settings
    with memory.engine.connect() as conn:
        conn.execute(text("""
            INSERT OR REPLACE INTO proactive_settings
            (user_id, max_messages_per_hour, quiet_hours_enabled, quiet_hours_start, quiet_hours_end)
            VALUES ('test_user', 5, 1, '22:00:00', '07:00:00')
        """))
        conn.commit()

    yield memory

    # Cleanup
    with memory.engine.connect() as conn:
        conn.execute(text("DELETE FROM proactive_rate_limit_tracking WHERE user_id = 'test_user'"))
        conn.execute(text("DELETE FROM proactive_settings WHERE user_id = 'test_user'"))
        conn.commit()


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limit_enforcement(self, memory_store):
        """Test that rate limits are enforced for low-priority messages."""

        # Send 5 digest messages (low priority - should respect limit)
        for i in range(5):
            can_send, reason = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
            assert can_send is True
            notification_limiter.record_notification_sent(memory_store, 'email_digest', 'test_user')

        # 6th low-priority message should be blocked
        can_send, reason = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
        assert can_send is False

        # But high-priority calendar messages can still get through
        can_send_calendar, _ = notification_limiter.can_send_notification(memory_store, 'calendar', 'test_user')
        assert can_send_calendar is True  # Calendar bypasses rate limit


    def test_rate_limit_hourly_reset(self, memory_store):
        """Test that rate limits reset every hour."""

        current_hour = datetime.utcnow().replace(minute=0, second=0, microsecond=0)

        # Fill up current hour with digest messages
        for i in range(5):
            notification_limiter.record_notification_sent(memory_store, 'email_digest', 'test_user')

        # Low-priority should be blocked
        can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
        assert can_send is False

        # Mock next hour
        next_hour = current_hour + timedelta(hours=1)
        with patch('core.proactive.notification_limiter.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = next_hour

            # Should be allowed again in new hour
            can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
            assert can_send is True


    def test_rate_limit_priority_ordering(self, memory_store):
        """Test that higher priority messages bypass rate limits."""

        # Fill up to limit with digest messages
        for i in range(5):
            notification_limiter.record_notification_sent(memory_store, 'email_digest', 'test_user')

        # At limit - low priority should be blocked
        can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
        assert can_send is False

        # Calendar (highest priority) bypasses rate limit
        can_send_calendar, _ = notification_limiter.can_send_notification(memory_store, 'calendar', 'test_user')
        assert can_send_calendar is True  # Calendar messages always allowed


    def test_rate_limit_per_user(self, memory_store):
        """Test that rate limits are per-user."""

        # Create second user with different limit
        with memory_store.engine.connect() as conn:
            conn.execute(text("""
                INSERT OR REPLACE INTO proactive_settings
                (user_id, max_messages_per_hour)
                VALUES ('user2', 10)
            """))
            conn.commit()

        # Fill test_user to limit with low-priority messages
        for i in range(5):
            notification_limiter.record_notification_sent(memory_store, 'email_digest', 'test_user')

        # test_user low-priority should be blocked
        can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
        assert can_send is False

        # user2 should still be allowed (different user, different limit)
        can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'user2')
        assert can_send is True

        # Cleanup
        with memory_store.engine.connect() as conn:
            conn.execute(text("DELETE FROM proactive_settings WHERE user_id = 'user2'"))
            conn.execute(text("DELETE FROM proactive_rate_limit_tracking WHERE user_id = 'user2'"))
            conn.commit()


class TestQuietHours:
    """Test quiet hours functionality."""

    def test_quiet_hours_active(self, memory_store):
        """Test that notifications are blocked during quiet hours."""

        # Mock time during quiet hours (23:00)
        quiet_time = datetime.utcnow().replace(hour=23, minute=0, second=0)

        with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = quiet_time

            is_quiet = quiet_hours.is_quiet_hours_active(memory_store, 'test_user')
            assert is_quiet is True


    def test_quiet_hours_inactive(self, memory_store):
        """Test that notifications are allowed outside quiet hours."""

        # Mock time outside quiet hours (10:00)
        active_time = datetime.utcnow().replace(hour=10, minute=0, second=0)

        with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = active_time

            is_quiet = quiet_hours.is_quiet_hours_active(memory_store, 'test_user')
            assert is_quiet is False


    def test_quiet_hours_cross_midnight(self, memory_store):
        """Test quiet hours that span midnight (22:00-07:00)."""

        # Test times during the quiet period
        test_times = [
            22, 23,  # Evening hours
            0, 1, 2, 3, 4, 5, 6   # Morning hours before 7am
        ]

        for hour in test_times:
            test_time = datetime.utcnow().replace(hour=hour, minute=0, second=0)

            with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
                mock_datetime.utcnow.return_value = test_time

                is_quiet = quiet_hours.is_quiet_hours_active(memory_store, 'test_user')
                assert is_quiet is True, f"Hour {hour} should be quiet"


    def test_quiet_hours_disabled(self, memory_store):
        """Test that quiet hours can be disabled."""

        # Disable quiet hours
        with memory_store.engine.connect() as conn:
            conn.execute(text("""
                UPDATE proactive_settings
                SET quiet_hours_enabled = 0
                WHERE user_id = 'test_user'
            """))
            conn.commit()

        # Mock time during configured quiet hours
        quiet_time = datetime.utcnow().replace(hour=23, minute=0, second=0)

        with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = quiet_time

            # Should not be quiet (disabled)
            is_quiet = quiet_hours.is_quiet_hours_active(memory_store, 'test_user')
            assert is_quiet is False


class TestCombinedSuppression:
    """Test rate limiting and quiet hours working together."""

    def test_combined_suppression(self, memory_store):
        """Test that both rate limiting and quiet hours are enforced."""

        # Mock time during quiet hours
        quiet_time = datetime.utcnow().replace(hour=23, minute=0, second=0)

        with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = quiet_time

            # Should be blocked by quiet hours
            is_quiet = quiet_hours.is_quiet_hours_active(memory_store, 'test_user')
            assert is_quiet is True

            # Even if rate limit allows, quiet hours should block
            can_send, _ = notification_limiter.can_send_notification(memory_store, 'calendar', 'test_user')
            should_send = can_send and not is_quiet

            assert should_send is False


    def test_suppression_priority(self, memory_store):
        """Test interaction between quiet hours and rate limiting."""

        # Fill up rate limit with low-priority messages
        for i in range(5):
            notification_limiter.record_notification_sent(memory_store, 'email_digest', 'test_user')

        # Mock active hours (not quiet)
        active_time = datetime.utcnow().replace(hour=10, minute=0, second=0)

        with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = active_time

            is_quiet = quiet_hours.is_quiet_hours_active(memory_store, 'test_user')
            can_send_digest, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')

            # Not quiet, but digest blocked by rate limit
            assert is_quiet is False
            assert can_send_digest is False

            # Calendar messages still allowed (high priority bypasses rate limit)
            can_send_calendar, _ = notification_limiter.can_send_notification(memory_store, 'calendar', 'test_user')
            assert can_send_calendar is True


    def test_settings_changes_immediate_effect(self, memory_store):
        """Test that settings changes take immediate effect."""

        # Initial: quiet hours enabled, max 5 per hour
        quiet_time = datetime.utcnow().replace(hour=23, minute=0, second=0)

        with patch('core.proactive.quiet_hours.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = quiet_time

            # Should be blocked by quiet hours
            assert quiet_hours.is_quiet_hours_active(memory_store, 'test_user') is True

            # Disable quiet hours
            with memory_store.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE proactive_settings
                    SET quiet_hours_enabled = 0
                    WHERE user_id = 'test_user'
                """))
                conn.commit()

            # Should now be allowed
            assert quiet_hours.is_quiet_hours_active(memory_store, 'test_user') is False

            # Change rate limit
            with memory_store.engine.connect() as conn:
                conn.execute(text("""
                    UPDATE proactive_settings
                    SET max_messages_per_hour = 10
                    WHERE user_id = 'test_user'
                """))
                conn.commit()

            # Fill to new limit with low-priority messages
            for i in range(10):
                can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
                if can_send:
                    notification_limiter.record_notification_sent(memory_store, 'email_digest', 'test_user')

            # 11th low-priority message should be blocked
            can_send, _ = notification_limiter.can_send_notification(memory_store, 'email_digest', 'test_user')
            assert can_send is False

            # But calendar messages still bypass the limit
            can_send_calendar, _ = notification_limiter.can_send_notification(memory_store, 'calendar', 'test_user')
            assert can_send_calendar is True
