"""
Calendar Monitoring Service

Handles proactive calendar event monitoring and notifications.
Fetches upcoming events and generates notifications using system LLM.
"""

import logging
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


def check_calendar_events(memory_store):
    """
    Check for upcoming calendar events and send notifications.

    This function:
    1. Iterates over all enabled users with M365 credentials
    2. Loads user settings (lead time, quiet hours, rate limits)
    3. Fetches upcoming events from M365
    4. Checks for events starting within the lead time window
    5. Generates notifications for events not yet notified
    6. Posts proactive messages to the chat

    Args:
        memory_store: MemoryStore instance
    """
    try:
        logger.info("[CALENDAR_SERVICE] Starting calendar check")

        # Get all users with M365 credentials and calendar monitoring enabled
        users = _get_users_for_calendar_check(memory_store)

        if not users:
            logger.debug("[CALENDAR_SERVICE] No users with calendar monitoring enabled")
            return

        total_notifications = 0
        for user_id in users:
            notifications = _check_calendar_for_user(memory_store, user_id)
            total_notifications += notifications

        logger.info(f"[CALENDAR_SERVICE] Calendar check complete. Sent {total_notifications} notification(s) across {len(users)} user(s)")

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Error during calendar check: {e}")
        _log_error(memory_store, DEFAULT_USER_ID, "calendar_fetch", str(e))


def _get_users_for_calendar_check(memory_store) -> List[int]:
    """
    Get list of user IDs that have calendar monitoring enabled and M365 credentials.

    Args:
        memory_store: MemoryStore instance

    Returns:
        List[int]: User IDs to check
    """
    try:
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT DISTINCT u.id
                    FROM users u
                    INNER JOIN m365_credentials m ON u.id = m.user_id
                    INNER JOIN proactive_settings p ON CAST(u.id AS TEXT) = p.user_id
                    WHERE u.is_enabled = 1
                      AND m.is_valid = 1
                      AND p.calendar_enabled = 1
                """)
            )

            users = [row[0] for row in result.fetchall()]
            logger.debug(f"[CALENDAR_SERVICE] Found {len(users)} user(s) with calendar monitoring enabled")
            return users

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Error getting users for calendar check: {e}")
        return []


def _check_calendar_for_user(memory_store, user_id: int) -> int:
    """
    Check calendar events for a specific user.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID

    Returns:
        int: Number of notifications sent
    """
    try:
        logger.info(f"[CALENDAR_SERVICE] Checking calendar for user {user_id}")

        # Load settings
        settings = _load_calendar_settings(memory_store, user_id)
        logger.info(f"[CALENDAR_SERVICE] Settings for user {user_id}: {settings}")

        if not settings['enabled']:
            logger.info(f"[CALENDAR_SERVICE] Calendar monitoring disabled for user {user_id}")
            return 0

        # Check quiet hours
        from core.proactive.quiet_hours import is_quiet_hours_active
        if is_quiet_hours_active(memory_store, str(user_id)):
            logger.info(f"[CALENDAR_SERVICE] Skipping user {user_id} (quiet hours active)")
            return 0

        # Fetch upcoming events
        logger.info(f"[CALENDAR_SERVICE] Fetching events for user {user_id} with lead time {settings['lead_time_minutes']} minutes")
        events = _fetch_upcoming_events(memory_store, user_id, settings['lead_time_minutes'])

        if not events:
            logger.debug(f"[CALENDAR_SERVICE] No upcoming events found for user {user_id}")
            return 0

        # Process each event
        notifications_sent = 0
        for event in events:
            if _should_notify_event(memory_store, user_id, event):
                if _send_event_notification(memory_store, user_id, event, settings['lead_time_minutes']):
                    notifications_sent += 1

        if notifications_sent > 0:
            logger.info(f"[CALENDAR_SERVICE] Sent {notifications_sent} notification(s) for user {user_id}")

        return notifications_sent

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Error checking calendar for user {user_id}: {e}")
        _log_error(memory_store, str(user_id), "calendar_fetch", str(e))
        return 0


def _load_calendar_settings(memory_store, user_id: int) -> Dict:
    """
    Load calendar-specific settings from database.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID

    Returns:
        dict: Calendar settings
    """
    try:
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT calendar_enabled, calendar_lead_time_minutes
                    FROM proactive_settings
                    WHERE user_id = :user_id
                """),
                {"user_id": str(user_id)}
            )

            row = result.fetchone()

            if row:
                return {
                    'enabled': bool(row[0]),
                    'lead_time_minutes': row[1]
                }
            else:
                return {
                    'enabled': True,
                    'lead_time_minutes': 15
                }

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Failed to load settings for user {user_id}: {e}")
        return {
            'enabled': True,
            'lead_time_minutes': 15
        }


def _fetch_upcoming_events(memory_store, user_id: int, lead_time_minutes: int) -> List[Dict]:
    """
    Fetch calendar events starting within the lead time window.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        lead_time_minutes: Minutes in advance to check for events

    Returns:
        List of upcoming events
    """
    try:
        # Load M365 credentials from database
        creds = memory_store.get_m365_credentials(user_id)

        if not creds:
            logger.warning(f"[CALENDAR_SERVICE] No M365 credentials found for user {user_id}")
            return []

        if not creds.get('is_valid'):
            logger.warning(f"[CALENDAR_SERVICE] M365 credentials are invalid for user {user_id}")
            return []

        # Get M365 provider
        from actions.m365_provider import M365Provider

        provider = M365Provider(
            access_token=creds["access_token"],
            refresh_token=creds["refresh_token"],
            expires_at=creds["expires_at"],
            user_id=user_id,
            memory_store=memory_store
        )

        # Calculate time window
        now = datetime.utcnow()
        window_start = now
        window_end = now + timedelta(minutes=lead_time_minutes + 5)  # +5 for overlap

        # Fetch events
        events = provider.read_calendar(window_start, window_end)

        logger.info(f"[CALENDAR_SERVICE] Fetched {len(events)} total event(s) from M365 for window {window_start} to {window_end}")

        # Debug: Log first event if any
        if events:
            logger.info(f"[CALENDAR_SERVICE] Sample event: {events[0]}")

        # Filter to events starting within the lead time window
        lead_time_threshold = now + timedelta(minutes=lead_time_minutes)

        upcoming = []
        for event in events:
            event_start = event.get('start_time')  # M365Provider returns 'start_time', not 'start'
            if not event_start:
                logger.debug(f"[CALENDAR_SERVICE] Event missing start_time: {event.get('id')}")
                continue

            # Parse event start time
            if isinstance(event_start, str):
                try:
                    # Microsoft Graph returns format like '2026-01-01T21:10:00.0000000'
                    # Python's fromisoformat needs either no fractional seconds or exactly 1-6 digits
                    cleaned_start = event_start.replace('Z', '+00:00')

                    if '.' in cleaned_start:
                        # Split on the decimal point
                        base, fractional = cleaned_start.split('.', 1)
                        # Extract only the digit portion (strip any non-digits like timezone info)
                        fractional_digits = ''
                        for char in fractional:
                            if char.isdigit():
                                fractional_digits += char
                            else:
                                break

                        # Strip trailing zeros
                        fractional_digits = fractional_digits.rstrip('0')

                        if fractional_digits and len(fractional_digits) <= 6:
                            # Use fractional seconds (1-6 digits)
                            cleaned_start = f"{base}.{fractional_digits}"
                        elif fractional_digits and len(fractional_digits) > 6:
                            # Truncate to 6 digits
                            cleaned_start = f"{base}.{fractional_digits[:6]}"
                        else:
                            # No fractional seconds, just use base
                            cleaned_start = base

                    event_start = datetime.fromisoformat(cleaned_start)
                except Exception as e:
                    logger.warning(f"[CALENDAR_SERVICE] Failed to parse event start time '{event_start}': {e}")
                    continue

            logger.debug(f"[CALENDAR_SERVICE] Event '{event.get('subject')}' starts at {event_start}, checking against {now} to {lead_time_threshold}")

            # Check if event starts within our notification window
            # (between now and lead_time_minutes from now)
            if now <= event_start <= lead_time_threshold:
                upcoming.append(event)
                logger.info(f"[CALENDAR_SERVICE] Event '{event.get('subject')}' is within notification window")

        logger.info(f"[CALENDAR_SERVICE] Found {len(upcoming)} event(s) starting within {lead_time_minutes} minutes")
        return upcoming

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Failed to fetch events: {e}")
        return []


def _should_notify_event(memory_store, user_id: int, event: Dict) -> bool:
    """
    Check if we should send a notification for this event.

    Checks:
    1. Not already notified
    2. Rate limits allow

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        event: Event dictionary

    Returns:
        bool: True if should notify
    """
    try:
        event_id = event.get('id')
        event_start = event.get('start_time')  # M365Provider returns 'start_time', not 'start'

        if not event_id or not event_start:
            return False

        # Parse event start time
        if isinstance(event_start, str):
            try:
                # Microsoft Graph returns format like '2026-01-01T21:10:00.0000000'
                # Python's fromisoformat needs either no fractional seconds or exactly 1-6 digits
                cleaned_start = event_start.replace('Z', '+00:00')

                if '.' in cleaned_start:
                    # Split on the decimal point
                    base, fractional = cleaned_start.split('.', 1)
                    # Extract only the digit portion (strip any non-digits like timezone info)
                    fractional_digits = ''
                    for char in fractional:
                        if char.isdigit():
                            fractional_digits += char
                        else:
                            break

                    # Strip trailing zeros
                    fractional_digits = fractional_digits.rstrip('0')

                    if fractional_digits and len(fractional_digits) <= 6:
                        # Use fractional seconds (1-6 digits)
                        cleaned_start = f"{base}.{fractional_digits}"
                    elif fractional_digits and len(fractional_digits) > 6:
                        # Truncate to 6 digits
                        cleaned_start = f"{base}.{fractional_digits[:6]}"
                    else:
                        # No fractional seconds, just use base
                        cleaned_start = base

                event_start = datetime.fromisoformat(cleaned_start)
            except Exception:
                return False

        # Check if already notified
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id FROM proactive_calendar_notifications
                    WHERE user_id = :user_id
                      AND event_id = :event_id
                      AND event_start = :event_start
                """),
                {
                    "user_id": str(user_id),
                    "event_id": event_id,
                    "event_start": event_start
                }
            )

            if result.fetchone():
                logger.debug(f"[CALENDAR_SERVICE] Event {event_id} already notified for user {user_id}")
                return False

        # Check rate limits
        from core.proactive.notification_limiter import can_send_notification
        can_send, reason = can_send_notification(memory_store, 'calendar', str(user_id))

        if not can_send:
            logger.debug(f"[CALENDAR_SERVICE] Rate limit prevents notification for user {user_id}: {reason}")
            return False

        return True

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Error checking notification status for user {user_id}: {e}")
        return False


def _send_event_notification(memory_store, user_id: int, event: Dict, lead_time_minutes: int) -> bool:
    """
    Generate and send notification for an event.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        event: Event dictionary
        lead_time_minutes: Lead time in minutes

    Returns:
        bool: True if notification sent successfully
    """
    try:
        # Record notification in database FIRST (prevent duplicate sends in race conditions)
        _record_notification(memory_store, user_id, event, "")

        # Generate notification content (pass memory_store and user_id for routing)
        notification_text, provider_id, model = _generate_notification(event, lead_time_minutes, memory_store, user_id)

        # Post proactive message to turns table (visible in chat)
        from core.proactive.message_poster import post_proactive_message
        message_posted = post_proactive_message(
            memory_store=memory_store,
            user_id=user_id,
            message_type='calendar_reminder',
            content=notification_text,
            source_ids=[event.get('id')],
            provider_id=provider_id,
            model=model
        )

        if not message_posted:
            logger.warning(f"[CALENDAR_SERVICE] Failed to post message to chat for user {user_id}")

        # Update rate limiter
        from core.proactive.notification_limiter import record_notification_sent
        record_notification_sent(memory_store, 'calendar', str(user_id))

        logger.info(f"[CALENDAR_SERVICE] Sent notification for event: {event.get('subject', 'Untitled')} (user {user_id})")
        return True

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Failed to send notification for user {user_id}: {e}")
        return False


def _generate_notification(event: Dict, lead_time_minutes: int, memory_store=None, user_id: int = None) -> tuple:
    """
    Generate notification text for an event using LLM summarization.

    Args:
        event: Event dictionary
        lead_time_minutes: Lead time in minutes
        memory_store: MemoryStore instance (for routing configuration)
        user_id: User ID (for routing configuration)

    Returns:
        tuple: (notification_text, provider_id, model) or (notification_text, None, None) for template
    """
    subject = event.get('subject', 'Untitled Event')
    start = event.get('start_time')  # M365Provider returns 'start_time', not 'start'
    location = event.get('location')
    body = event.get('body', '')

    # Parse start time for friendly display
    start_time = "Unknown time"
    if isinstance(start, str):
        try:
            # Microsoft Graph returns format like '2026-01-01T21:10:00.0000000'
            # Python's fromisoformat needs either no fractional seconds or exactly 1-6 digits
            cleaned_start = start.replace('Z', '+00:00')

            if '.' in cleaned_start:
                # Split on the decimal point
                base, fractional = cleaned_start.split('.', 1)
                # Extract only the digit portion (strip any non-digits like timezone info)
                fractional_digits = ''
                for char in fractional:
                    if char.isdigit():
                        fractional_digits += char
                    else:
                        break

                # Strip trailing zeros
                fractional_digits = fractional_digits.rstrip('0')

                if fractional_digits and len(fractional_digits) <= 6:
                    # Use fractional seconds (1-6 digits)
                    cleaned_start = f"{base}.{fractional_digits}"
                elif fractional_digits and len(fractional_digits) > 6:
                    # Truncate to 6 digits
                    cleaned_start = f"{base}.{fractional_digits[:6]}"
                else:
                    # No fractional seconds, just use base
                    cleaned_start = base

            start_dt = datetime.fromisoformat(cleaned_start)
            start_time = start_dt.strftime('%I:%M %p').lstrip('0')
        except Exception:
            start_time = str(start)
    elif start:
        start_time = start.strftime('%I:%M %p').lstrip('0')

    # Try LLM summarization first
    try:
        from core.router import route_request

        # Build context for LLM
        event_context = f"Title: {subject}\nStarts: {start_time} (in {lead_time_minutes} minutes)"
        if location:
            event_context += f"\nLocation: {location}"
        if body and len(body) > 0:
            event_context += f"\nDetails: {body[:500]}"  # Limit to first 500 chars

        prompt = f"""You are a helpful assistant that creates friendly calendar reminders.

Event details:
{event_context}

Generate a brief, natural reminder message (1-2 sentences) that:
1. Addresses the user as "Hey Danny" (casual, friendly tone)
2. Reminds them about the upcoming event
3. Mentions when it starts and how much time they have
4. If there's a location, mention it naturally

Example: "Hey Danny, just a heads up - your Team Meeting is starting at 2:00 PM in 15 minutes. It's in Conference Room A."

Generate the reminder:"""

        # Route to LLM for summarization using "system" intent and user's routing preferences
        context = {
            "text": prompt,
            "session_id": "proactive_summarization",
            "memory": memory_store,
            "user_id": str(user_id) if user_id is not None else DEFAULT_USER_ID,
            "forced_provider": None
        }

        result = route_request(context)
        llm_summary = result.get("text", "").strip()
        provider_id = result.get("provider")
        model = result.get("model")

        if llm_summary and len(llm_summary) > 10:  # Valid summary
            logger.info(f"[CALENDAR_SERVICE] Generated LLM summary for calendar notification (provider: {provider_id}, model: {model})")
            return llm_summary, provider_id, model

    except Exception as e:
        logger.warning(f"[CALENDAR_SERVICE] Failed to generate LLM summary, falling back to template: {e}")

    # Fallback to template-based notification
    parts = [
        f"Upcoming Event: {subject}",
        f"Starts at {start_time} (in {lead_time_minutes} minutes)"
    ]

    if location:
        parts.append(f"Location: {location}")

    return "\n".join(parts), None, None


def _record_notification(memory_store, user_id: int, event: Dict, notification_text: str):
    """
    Record that we notified about this event.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        event: Event dictionary
        notification_text: Generated notification text
    """
    try:
        event_id = event.get('id')
        event_start = event.get('start_time')  # M365Provider returns 'start_time', not 'start'
        event_title = event.get('subject', 'Untitled')

        if isinstance(event_start, str):
            # Microsoft Graph returns format like '2026-01-01T21:10:00.0000000'
            # Python's fromisoformat needs either no fractional seconds or exactly 1-6 digits
            cleaned_start = event_start.replace('Z', '+00:00')

            if '.' in cleaned_start:
                # Split on the decimal point
                base, fractional = cleaned_start.split('.', 1)
                # Extract only the digit portion (strip any non-digits like timezone info)
                fractional_digits = ''
                for char in fractional:
                    if char.isdigit():
                        fractional_digits += char
                    else:
                        break

                # Strip trailing zeros
                fractional_digits = fractional_digits.rstrip('0')

                if fractional_digits and len(fractional_digits) <= 6:
                    # Use fractional seconds (1-6 digits)
                    cleaned_start = f"{base}.{fractional_digits}"
                elif fractional_digits and len(fractional_digits) > 6:
                    # Truncate to 6 digits
                    cleaned_start = f"{base}.{fractional_digits[:6]}"
                else:
                    # No fractional seconds, just use base
                    cleaned_start = base

            event_start = datetime.fromisoformat(cleaned_start)

        with memory_store.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO proactive_calendar_notifications
                    (user_id, event_id, event_start, event_title, notification_content)
                    VALUES (:user_id, :event_id, :event_start, :event_title, :notification_content)
                """),
                {
                    "user_id": str(user_id),
                    "event_id": event_id,
                    "event_start": event_start,
                    "event_title": event_title,
                    "notification_content": notification_text
                }
            )
            conn.commit()

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Failed to record notification for user {user_id}: {e}")


def _log_error(memory_store, user_id: str, error_type: str, error_message: str):
    """
    Log an error to the proactive_errors table.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID (as string)
        error_type: Type of error
        error_message: Error message
    """
    try:
        with memory_store.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO proactive_errors (user_id, error_type, error_message)
                    VALUES (:user_id, :error_type, :error_message)
                """),
                {
                    "user_id": user_id,
                    "error_type": error_type,
                    "error_message": error_message
                }
            )
            conn.commit()

    except Exception as e:
        logger.error(f"[CALENDAR_SERVICE] Failed to log error: {e}")
