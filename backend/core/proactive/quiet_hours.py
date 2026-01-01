"""
Quiet Hours Management

Handles quiet hours logic for proactive notifications.
Prevents notifications during user-configured time windows.
"""

import logging
from datetime import datetime, time
from typing import Tuple, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


def is_quiet_hours_active(memory_store, user_id: str = 'local') -> bool:
    """
    Check if quiet hours are currently active for the user.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID (default: 'local')

    Returns:
        bool: True if quiet hours are active, False otherwise
    """
    try:
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT quiet_hours_enabled, quiet_hours_start, quiet_hours_end
                    FROM proactive_settings
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id}
            )

            row = result.fetchone()

        if not row:
            # No settings found, quiet hours not active
            return False

        enabled, start_str, end_str = row

        if not enabled or not start_str or not end_str:
            # Quiet hours disabled or not configured
            return False

        # Parse time strings (format: HH:MM:SS)
        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)
        current_time = datetime.utcnow().time()

        # Check if current time is within quiet hours
        if start_time < end_time:
            # Normal case: e.g., 22:00 - 07:00 same day
            in_quiet_hours = start_time <= current_time <= end_time
        else:
            # Cross-midnight case: e.g., 22:00 - 07:00 next day
            in_quiet_hours = current_time >= start_time or current_time <= end_time

        if in_quiet_hours:
            logger.info(f"[QUIET_HOURS] Currently in quiet hours ({start_str} - {end_str})")

        return in_quiet_hours

    except Exception as e:
        logger.error(f"[QUIET_HOURS] Error checking quiet hours: {e}")
        # On error, assume quiet hours not active (fail open)
        return False


def get_quiet_hours_config(memory_store, user_id: str = 'local') -> Tuple[bool, Optional[time], Optional[time]]:
    """
    Get quiet hours configuration for the user.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID (default: 'local')

    Returns:
        Tuple: (enabled, start_time, end_time)
    """
    try:
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT quiet_hours_enabled, quiet_hours_start, quiet_hours_end
                    FROM proactive_settings
                    WHERE user_id = :user_id
                """),
                {"user_id": user_id}
            )

            row = result.fetchone()

        if not row:
            return (False, None, None)

        enabled, start_str, end_str = row

        if not enabled or not start_str or not end_str:
            return (False, None, None)

        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)

        return (True, start_time, end_time)

    except Exception as e:
        logger.error(f"[QUIET_HOURS] Error getting quiet hours config: {e}")
        return (False, None, None)
