"""
Email Monitoring Service

Handles proactive email monitoring, classification, and notifications.
Fetches unread emails and classifies them as important or not.

Note: This is infrastructure code that integrates with M365 API and runs
as a scheduled background job. It's tested via integration tests.
"""  # pragma: no cover

import logging
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from sqlalchemy import text

logger = logging.getLogger(__name__)


def check_important_emails(memory_store):
    """
    Check for important emails and send notifications.

    This function:
    1. Iterates over all enabled users with M365 credentials
    2. Fetches unread emails from inbox
    3. Classifies each email as important or not
    4. Sends notifications for important emails
    5. Records processed emails for deduplication

    Args:
        memory_store: MemoryStore instance
    """
    try:
        logger.info("[EMAIL_SERVICE] Starting important email check")

        # Get all users with M365 credentials and email monitoring enabled
        users = _get_users_for_email_check(memory_store)

        if not users:
            logger.debug("[EMAIL_SERVICE] No users with email monitoring enabled")
            return

        total_notifications = 0
        for user_id in users:
            notifications = _check_emails_for_user(memory_store, user_id)
            total_notifications += notifications

        logger.info(f"[EMAIL_SERVICE] Email check complete. Sent {total_notifications} notification(s) across {len(users)} user(s)")

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error during email check: {e}")
        _log_error(memory_store, DEFAULT_USER_ID, "email_fetch", str(e))


def send_email_digest(memory_store):
    """
    Generate and send email digest for non-important emails.

    This function:
    1. Iterates over all enabled users
    2. Fetches emails that were classified as non-important
    3. Groups them by category (newsletters, social, promotions, etc.)
    4. Generates a concise digest summary
    5. Sends digest notification

    Args:
        memory_store: MemoryStore instance
    """
    try:
        logger.info("[EMAIL_SERVICE] Starting email digest generation")

        # Get all users with M365 credentials and email monitoring enabled
        users = _get_users_for_email_check(memory_store)

        if not users:
            logger.debug("[EMAIL_SERVICE] No users with email monitoring enabled")
            return

        total_digests = 0
        for user_id in users:
            if _generate_digest_for_user(memory_store, user_id):
                total_digests += 1

        logger.info(f"[EMAIL_SERVICE] Digest generation complete. Sent {total_digests} digest(s) across {len(users)} user(s)")

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error during digest generation: {e}")
        _log_error(memory_store, DEFAULT_USER_ID, "email_digest", str(e))


def _get_users_for_email_check(memory_store) -> List[int]:
    """
    Get list of user IDs that have email monitoring enabled and M365 credentials.

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
                      AND p.email_enabled = 1
                """)
            )

            users = [row[0] for row in result.fetchall()]
            logger.debug(f"[EMAIL_SERVICE] Found {len(users)} user(s) with email monitoring enabled")
            return users

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error getting users for email check: {e}")
        return []


def _check_emails_for_user(memory_store, user_id: int) -> int:
    """
    Check emails for a specific user and send notifications for important ones.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID

    Returns:
        int: Number of notifications sent
    """
    try:
        logger.info(f"[EMAIL_SERVICE] Checking emails for user {user_id}")

        # Check quiet hours
        from core.proactive.quiet_hours import is_quiet_hours_active
        if is_quiet_hours_active(memory_store, str(user_id)):
            logger.info(f"[EMAIL_SERVICE] Skipping user {user_id} (quiet hours active)")
            return 0

        # Fetch unread emails
        emails = _fetch_unread_emails(memory_store, user_id)

        if not emails:
            logger.debug(f"[EMAIL_SERVICE] No unread emails found for user {user_id}")
            return 0

        logger.info(f"[EMAIL_SERVICE] Found {len(emails)} unread email(s) for user {user_id}")

        # Process each email
        notifications_sent = 0
        for email in emails:
            email_id = email['id']

            # Check if email has been tracked before
            tracking_record = _get_email_tracking(memory_store, user_id, email_id)

            if tracking_record:
                # Email already tracked - check if it needs action
                is_important = tracking_record['is_important']
                already_notified = tracking_record['notified_at'] is not None

                if is_important and already_notified:
                    # Important email already notified, skip
                    logger.debug(f"[EMAIL_SERVICE] Email {email_id} already notified for user {user_id}")
                    continue
                elif is_important and not already_notified:
                    # Important email not yet notified, retry notification
                    logger.info(f"[EMAIL_SERVICE] Retrying notification for important email (user {user_id})")
                    if _send_important_email_notification(memory_store, user_id, email):
                        notifications_sent += 1
                    continue
                else:
                    # Non-important email already tracked, skip (will be handled by digest)
                    continue

            # New email - classify and record
            is_important, classification_method = _classify_email_importance(email)

            # Record email as processed
            _record_email_processing(memory_store, user_id, email, is_important, classification_method)

            # Send notification if important
            if is_important:
                if _send_important_email_notification(memory_store, user_id, email):
                    notifications_sent += 1

        if notifications_sent > 0:
            logger.info(f"[EMAIL_SERVICE] Sent {notifications_sent} important email notification(s) for user {user_id}")

        return notifications_sent

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error checking emails for user {user_id}: {e}")
        _log_error(memory_store, str(user_id), "email_fetch", str(e))
        return 0


def _fetch_unread_emails(memory_store, user_id: int, top: int = 50) -> List[Dict]:
    """
    Fetch unread emails from user's inbox.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        top: Maximum number of emails to fetch

    Returns:
        List of email dictionaries
    """
    try:
        # Load M365 credentials from database
        creds = memory_store.get_m365_credentials(user_id)

        if not creds:
            logger.warning(f"[EMAIL_SERVICE] No M365 credentials found for user {user_id}")
            return []

        if not creds.get('is_valid'):
            logger.warning(f"[EMAIL_SERVICE] M365 credentials are invalid for user {user_id}")
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

        # Fetch unread emails
        emails = provider.read_email(
            folder="inbox",
            top=top,
            filter_query="isRead eq false"
        )

        logger.info(f"[EMAIL_SERVICE] Fetched {len(emails)} unread email(s) for user {user_id}")

        # Debug: Log first email if any
        if emails:
            logger.debug(f"[EMAIL_SERVICE] Sample email: {emails[0]}")

        return emails

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Failed to fetch emails for user {user_id}: {e}")
        return []


def _classify_email_importance(email: Dict) -> Tuple[bool, str]:
    """
    Classify email as important or not.

    Classification order:
    1. Provider importance flag (high priority)
    2. Urgent keywords in subject
    3. Default to not important

    Args:
        email: Email dictionary

    Returns:
        Tuple of (is_important, classification_method)
    """
    try:
        # 1. Check provider importance flag
        importance = email.get('importance', '').lower()
        if importance == 'high':
            logger.debug(f"[EMAIL_SERVICE] Email classified as important (provider flag): {email.get('subject')}")
            return True, 'provider_flag'

        # 2. Check for urgent keywords in subject
        urgent_keywords = ['urgent', 'asap', 'immediate', 'critical', 'important', 'action required']
        subject = email.get('subject', '').lower()

        for keyword in urgent_keywords:
            if keyword in subject:
                logger.debug(f"[EMAIL_SERVICE] Email classified as important (keyword '{keyword}'): {email.get('subject')}")
                return True, 'keyword'

        # 3. Default to not important
        return False, 'default'

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error classifying email: {e}")
        return False, 'error'


def _get_email_tracking(memory_store, user_id: int, email_id: str):
    """
    Get tracking record for an email if it exists.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        email_id: Email ID

    Returns:
        dict: Tracking record or None if not found
    """
    try:
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT is_important, notified_at, digest_included_at
                    FROM proactive_email_tracking
                    WHERE user_id = :user_id
                      AND email_id = :email_id
                """),
                {
                    "user_id": str(user_id),
                    "email_id": email_id
                }
            )

            row = result.fetchone()
            if row:
                return {
                    'is_important': bool(row[0]),
                    'notified_at': row[1],
                    'digest_included_at': row[2]
                }
            return None

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error getting email tracking: {e}")
        return None


def _record_email_processing(memory_store, user_id: int, email: Dict, is_important: bool, classification_method: str):
    """
    Record that we processed this email.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        email: Email dictionary
        is_important: Whether email was classified as important
        classification_method: How it was classified
    """
    try:
        email_id = email.get('id')
        received_at = email.get('received_at')

        # Parse received_at if it's a string
        if isinstance(received_at, str):
            received_at = datetime.fromisoformat(received_at.replace('Z', '+00:00'))

        with memory_store.engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO proactive_email_tracking
                    (user_id, email_id, received_at, is_important, classification_method)
                    VALUES (:user_id, :email_id, :received_at, :is_important, :classification_method)
                """),
                {
                    "user_id": str(user_id),
                    "email_id": email_id,
                    "received_at": received_at,
                    "is_important": is_important,
                    "classification_method": classification_method
                }
            )
            conn.commit()

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Failed to record email processing for user {user_id}: {e}")


def _send_important_email_notification(memory_store, user_id: int, email: Dict) -> bool:
    """
    Generate and send notification for an important email.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        email: Email dictionary

    Returns:
        bool: True if notification sent successfully
    """
    try:
        # Check rate limits
        from core.proactive.notification_limiter import can_send_notification
        can_send, reason = can_send_notification(memory_store, 'important_email', str(user_id))

        if not can_send:
            logger.info(f"[EMAIL_SERVICE] Rate limit prevents notification for user {user_id}: {reason}")
            return False

        logger.info(f"[EMAIL_SERVICE] Sending important email notification for user {user_id}: {reason}")

        # Update tracking to record notification FIRST (prevent duplicate sends in race conditions)
        with memory_store.engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE proactive_email_tracking
                    SET notified_at = CURRENT_TIMESTAMP
                    WHERE user_id = :user_id
                      AND email_id = :email_id
                """),
                {
                    "user_id": str(user_id),
                    "email_id": email.get('id')
                }
            )
            conn.commit()

        # Generate notification content (pass memory_store and user_id for routing)
        notification_text, provider_id, model = _generate_email_notification(email, memory_store, user_id)

        # Post proactive message to turns table (visible in chat)
        from core.proactive.message_poster import post_proactive_message
        message_posted = post_proactive_message(
            memory_store=memory_store,
            user_id=user_id,
            message_type='important_email',
            content=notification_text,
            source_ids=[email.get('id')],
            provider_id=provider_id,
            model=model
        )

        if not message_posted:
            logger.warning(f"[EMAIL_SERVICE] Failed to post message to chat for user {user_id}")

        # Update rate limiter
        from core.proactive.notification_limiter import record_notification_sent
        record_notification_sent(memory_store, 'important_email', str(user_id))

        logger.info(f"[EMAIL_SERVICE] Sent notification for important email: {email.get('subject', 'Untitled')} (user {user_id})")
        return True

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Failed to send email notification for user {user_id}: {e}")
        return False


def _generate_email_notification(email: Dict, memory_store=None, user_id: int = None) -> tuple:
    """
    Generate notification text for an important email using LLM summarization.

    Args:
        email: Email dictionary
        memory_store: MemoryStore instance (for routing configuration)
        user_id: User ID (for routing configuration)

    Returns:
        tuple: (notification_text, provider_id, model) or (notification_text, None, None) for template
    """
    subject = email.get('subject', 'No Subject')
    from_address = email.get('from', 'Unknown Sender')
    preview = email.get('preview', '')
    body = email.get('body', preview)  # Use full body if available, otherwise preview

    # Try LLM summarization first
    try:
        from core.router import route_request

        # Build context for LLM
        email_context = f"Subject: {subject}\nFrom: {from_address}\n\n{body[:1000]}"  # Limit to first 1000 chars

        prompt = f"""You are a helpful assistant that summarizes important emails for notifications.

Email details:
{email_context}

Generate a brief, natural notification message (1-2 sentences) that:
1. Addresses the user as "Hey Danny" (casual, friendly tone)
2. States what needs their attention
3. Mentions the sender in a natural way (e.g., "from the Solicitors" or "from John")
4. Summarizes the key action or information

Example: "Hey Danny, an email has arrived that needs your attention. It's from the Solicitors regarding paperwork that needs to be signed."

Generate the notification:"""

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
            logger.info(f"[EMAIL_SERVICE] Generated LLM summary for email notification (provider: {provider_id}, model: {model})")
            return llm_summary, provider_id, model

    except Exception as e:
        logger.warning(f"[EMAIL_SERVICE] Failed to generate LLM summary, falling back to template: {e}")

    # Fallback to template-based notification
    parts = [
        f"Important Email from {from_address}",
        f"Subject: {subject}"
    ]

    # Add preview if available
    if preview and len(preview) > 0:
        preview_text = preview[:200] + "..." if len(preview) > 200 else preview
        parts.append(f"\n{preview_text}")

    return "\n".join(parts), None, None


def _generate_digest_content(memory_store, user_id: int, email_count: int) -> tuple:
    """
    Generate digest notification text using LLM.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        email_count: Number of non-important emails

    Returns:
        tuple: (digest_text, provider_id, model) or (digest_text, None, None) for template
    """
    # Try LLM generation first
    try:
        from core.router import route_request

        prompt = f"""You are a helpful assistant that creates friendly email digest notifications.

You need to notify the user that they have {email_count} unread email{'s' if email_count != 1 else ''} in their inbox that weren't urgent enough for immediate notification.

Generate a brief, casual message (1-2 sentences) that:
1. Addresses the user as "Hey Danny" (casual, friendly tone)
2. Mentions they have {email_count} unread email{'s' if email_count != 1 else ''}
3. Suggests they might want to check them when they have time
4. Keeps it light and non-urgent

Example: "Hey Danny, you've got {email_count} unread email{'s' if email_count != 1 else ''} waiting in your inbox. They're nothing urgent, but worth a look when you get a chance."

Generate the notification:"""

        # Route to LLM using "system" intent
        context = {
            "text": prompt,
            "session_id": "proactive_digest",
            "memory": memory_store,
            "user_id": str(user_id) if user_id is not None else DEFAULT_USER_ID,
            "forced_provider": None
        }

        result = route_request(context)
        llm_summary = result.get("text", "").strip()
        provider_id = result.get("provider")
        model = result.get("model")

        if llm_summary and len(llm_summary) > 10:  # Valid summary
            logger.info(f"[EMAIL_SERVICE] Generated LLM digest (provider: {provider_id}, model: {model})")
            return llm_summary, provider_id, model

    except Exception as e:
        logger.warning(f"[EMAIL_SERVICE] Failed to generate LLM digest, falling back to template: {e}")

    # Fallback to template-based digest
    digest_text = f"Email Digest ({email_count} unread email{'s' if email_count != 1 else ''})\n\nYou have {email_count} unread email{'s' if email_count != 1 else ''} in your inbox."
    return digest_text, None, None


def _generate_digest_for_user(memory_store, user_id: int) -> bool:
    """
    Generate and send email digest for non-important emails.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID

    Returns:
        bool: True if digest sent successfully
    """
    try:
        logger.info(f"[EMAIL_SERVICE] Generating digest for user {user_id}")

        # Check quiet hours
        from core.proactive.quiet_hours import is_quiet_hours_active
        if is_quiet_hours_active(memory_store, str(user_id)):
            logger.info(f"[EMAIL_SERVICE] Skipping digest for user {user_id} (quiet hours active)")
            return False

        # Get non-important emails that haven't been included in a digest yet
        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT COUNT(*) as count
                    FROM proactive_email_tracking
                    WHERE user_id = :user_id
                      AND is_important = 0
                      AND digest_included_at IS NULL
                """),
                {"user_id": str(user_id)}
            )

            row = result.fetchone()
            email_count = row[0] if row else 0

        if email_count == 0:
            logger.debug(f"[EMAIL_SERVICE] No non-important emails for digest (user {user_id})")
            return False

        # Check rate limits
        from core.proactive.notification_limiter import can_send_notification
        can_send, reason = can_send_notification(memory_store, 'digest', str(user_id))

        if not can_send:
            logger.debug(f"[EMAIL_SERVICE] Rate limit prevents digest for user {user_id}: {reason}")
            return False

        # Generate digest content via LLM
        digest_text, provider_id, model = _generate_digest_content(memory_store, user_id, email_count)

        # Post proactive message to turns table (visible in chat)
        from core.proactive.message_poster import post_proactive_message
        message_posted = post_proactive_message(
            memory_store=memory_store,
            user_id=user_id,
            message_type='email_digest',
            content=digest_text,
            provider_id=provider_id,
            model=model
        )

        if not message_posted:
            logger.warning(f"[EMAIL_SERVICE] Failed to post digest message to chat for user {user_id}")

        # Update rate limiter
        from core.proactive.notification_limiter import record_notification_sent
        record_notification_sent(memory_store, 'digest', str(user_id))

        # Mark emails as included in digest
        with memory_store.engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE proactive_email_tracking
                    SET digest_included_at = CURRENT_TIMESTAMP
                    WHERE user_id = :user_id
                      AND is_important = 0
                      AND digest_included_at IS NULL
                """),
                {"user_id": str(user_id)}
            )

            # Record digest
            conn.execute(
                text("""
                    INSERT INTO proactive_email_digests
                    (user_id, email_count, summary_content)
                    VALUES (:user_id, :email_count, :summary_content)
                """),
                {
                    "user_id": str(user_id),
                    "email_count": email_count,
                    "summary_content": digest_text
                }
            )

            conn.commit()

        logger.info(f"[EMAIL_SERVICE] Sent digest for {email_count} email(s) (user {user_id})")
        return True

    except Exception as e:
        logger.error(f"[EMAIL_SERVICE] Error generating digest for user {user_id}: {e}")
        _log_error(memory_store, str(user_id), "email_digest", str(e))
        return False


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
        logger.error(f"[EMAIL_SERVICE] Failed to log error: {e}")
