"""
Notification Rate Limiter

Manages rate limiting for proactive notifications to prevent spam.
Enforces max_messages_per_hour limit with priority system.
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple
from sqlalchemy import text

logger = logging.getLogger(__name__)

# Message type priorities (higher = more important)
PRIORITY_CALENDAR = 3
PRIORITY_IMPORTANT_EMAIL = 2
PRIORITY_DIGEST = 1


def can_send_notification(
    memory_store,
    message_type: str,
    user_id: str = 'local'
) -> Tuple[bool, str]:
    """
    Check if a notification can be sent based on rate limits.

    Args:
        memory_store: MemoryStore instance
        message_type: Type of message ('calendar', 'important_email', 'digest')
        user_id: User ID (default: 'local')

    Returns:
        Tuple: (can_send: bool, reason: str)
    """
    try:
        with memory_store.engine.connect() as conn:
            # Get max messages per hour setting
            result = conn.execute(
                text("SELECT max_messages_per_hour FROM proactive_settings WHERE user_id = :user_id"),
                {"user_id": user_id}
            )
            row = result.fetchone()

            if not row:
                # No settings, allow by default
                return (True, "No rate limit configured")

            max_per_hour = row[0]

            # Get current hour window (top of the hour)
            now = datetime.utcnow()
            hour_window = now.replace(minute=0, second=0, microsecond=0)

            # Get or create rate limit tracking for this hour
            result = conn.execute(
                text("SELECT message_count FROM proactive_rate_limit_tracking WHERE user_id = :user_id AND hour_window = :hour_window"),
                {"user_id": user_id, "hour_window": hour_window}
            )
            row = result.fetchone()
            current_count = row[0] if row else 0

            # Check if we're at or over the limit
            if current_count >= max_per_hour:
                # Check priority - only allow high priority messages to override
                priority = _get_message_priority(message_type)

                if priority < PRIORITY_CALENDAR:
                    # Low priority message, suppress
                    logger.info(
                        f"[RATE_LIMIT] Suppressing {message_type} notification "
                        f"(limit: {current_count}/{max_per_hour})"
                    )
                    return (False, f"Rate limit reached ({current_count}/{max_per_hour})")

                # Calendar events are high priority, allow even at limit
                logger.warning(
                    f"[RATE_LIMIT] Allowing high-priority {message_type} "
                    f"despite limit ({current_count}/{max_per_hour})"
                )

            return (True, f"Within rate limit ({current_count}/{max_per_hour})")

    except Exception as e:
        logger.error(f"[RATE_LIMIT] Error checking rate limit: {e}")
        # On error, allow notification (fail open)
        return (True, "Error checking rate limit")


def record_notification_sent(
    memory_store,
    message_type: str,
    user_id: str = 'local'
):
    """
    Record that a notification was sent for rate limiting purposes.

    Args:
        memory_store: MemoryStore instance
        message_type: Type of message sent
        user_id: User ID (default: 'local')
    """
    try:
        # Get current hour window
        now = datetime.utcnow()
        hour_window = now.replace(minute=0, second=0, microsecond=0)

        with memory_store.engine.connect() as conn:
            # Insert or update rate limit tracking
            conn.execute(text("""
                INSERT INTO proactive_rate_limit_tracking (user_id, hour_window, message_count)
                VALUES (:user_id, :hour_window, 1)
                ON CONFLICT(user_id, hour_window)
                DO UPDATE SET message_count = message_count + 1
            """), {"user_id": user_id, "hour_window": hour_window})

            conn.commit()

            # Get updated count for logging
            result = conn.execute(
                text("SELECT message_count FROM proactive_rate_limit_tracking WHERE user_id = :user_id AND hour_window = :hour_window"),
                {"user_id": user_id, "hour_window": hour_window}
            )
            row = result.fetchone()
            count = row[0] if row else 0

            logger.info(f"[RATE_LIMIT] Recorded {message_type} notification (count: {count} this hour)")

    except Exception as e:
        logger.error(f"[RATE_LIMIT] Error recording notification: {e}")


def get_current_hour_count(memory_store, user_id: str = 'local') -> int:
    """
    Get the number of notifications sent in the current hour.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID (default: 'local')

    Returns:
        int: Number of notifications sent this hour
    """
    try:
        now = datetime.utcnow()
        hour_window = now.replace(minute=0, second=0, microsecond=0)

        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("SELECT message_count FROM proactive_rate_limit_tracking WHERE user_id = :user_id AND hour_window = :hour_window"),
                {"user_id": user_id, "hour_window": hour_window}
            )
            row = result.fetchone()
            return row[0] if row else 0

    except Exception as e:
        logger.error(f"[RATE_LIMIT] Error getting current hour count: {e}")
        return 0


def _get_message_priority(message_type: str) -> int:
    """
    Get priority level for a message type.

    Args:
        message_type: Type of message

    Returns:
        int: Priority level (higher = more important)
    """
    priority_map = {
        'calendar': PRIORITY_CALENDAR,
        'calendar_reminder': PRIORITY_CALENDAR,
        'important_email': PRIORITY_IMPORTANT_EMAIL,
        'email': PRIORITY_IMPORTANT_EMAIL,
        'digest': PRIORITY_DIGEST,
        'email_digest': PRIORITY_DIGEST
    }

    return priority_map.get(message_type.lower(), PRIORITY_DIGEST)
