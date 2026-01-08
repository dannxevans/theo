"""
Cleanup Service

Handles cleanup of old notification tracking records.

Note: This is infrastructure code that runs as a scheduled background job.
It's tested via integration tests, not unit tests.
"""  # pragma: no cover

import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


def cleanup_old_notifications(memory_store):
    """
    Clean up old notification tracking records.

    Removes:
    - Calendar notifications older than 7 days
    - Email tracking records older than 30 days
    - Rate limit tracking older than 24 hours
    - Resolved errors older than 30 days

    Args:
        memory_store: MemoryStore instance
    """
    try:
        from sqlalchemy import text

        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        day_ago = now - timedelta(days=1)

        with memory_store.engine.connect() as conn:
            # Clean up old calendar notifications (7 days)
            result = conn.execute(
                text("DELETE FROM proactive_calendar_notifications WHERE notified_at < :week_ago"),
                {"week_ago": week_ago}
            )
            calendar_deleted = result.rowcount

            # Clean up old email tracking (30 days)
            result = conn.execute(text("""
                DELETE FROM proactive_email_tracking
                WHERE (notified_at IS NOT NULL AND notified_at < :month_ago)
                   OR (digest_included_at IS NOT NULL AND digest_included_at < :month_ago)
            """), {"month_ago": month_ago})
            email_deleted = result.rowcount

            # Clean up old rate limit tracking (24 hours)
            result = conn.execute(
                text("DELETE FROM proactive_rate_limit_tracking WHERE hour_window < :day_ago"),
                {"day_ago": day_ago}
            )
            rate_limit_deleted = result.rowcount

            # Clean up resolved errors (30 days)
            result = conn.execute(
                text("DELETE FROM proactive_errors WHERE resolved = 1 AND occurred_at < :month_ago"),
                {"month_ago": month_ago}
            )
            errors_deleted = result.rowcount

            conn.commit()

            logger.info(
                f"[CLEANUP] Cleaned up old records: "
                f"{calendar_deleted} calendar, {email_deleted} email, "
                f"{rate_limit_deleted} rate_limit, {errors_deleted} errors"
            )

    except Exception as e:
        logger.error(f"[CLEANUP] Error during cleanup: {e}")
