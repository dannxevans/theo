"""
Proactive Message Poster

Posts proactive notifications to the turns table as system-initiated assistant messages.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def post_proactive_message(
    memory_store,
    user_id: int,
    message_type: str,
    content: str,
    source_ids: Optional[List[str]] = None,
    session_id: Optional[str] = None,
    provider_id: Optional[str] = None,
    model: Optional[str] = None
) -> Optional[int]:
    """
    Post a proactive notification message to the turns table.

    Messages are posted to the user's most recent Personal mode session.
    Each message can be dismissed individually using the turn_id.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID
        message_type: Type of proactive message ('calendar_reminder', 'important_email', 'email_digest')
        content: Message content to display
        source_ids: Optional list of source IDs (event_id, email_id, etc.)
        session_id: Optional session ID (finds most recent Personal session if not provided)
        provider_id: Optional provider ID (from LLM that generated the content)
        model: Optional model name (from LLM that generated the content)

    Returns:
        int: Turn ID if message posted successfully, None otherwise
    """
    try:
        # Get or find session
        if not session_id:
            session_id = _get_user_session(memory_store, user_id)
            if not session_id:
                logger.warning(f"[MESSAGE_POSTER] No Personal mode session found for user {user_id}")
                return None

        # Build metadata
        metadata = {
            "proactive": True,
            "type": message_type,
            "generated_at": datetime.utcnow().isoformat(),
            "dismissed": False
        }

        if source_ids:
            metadata["source_ids"] = source_ids

        # Use provided provider/model or fall back to system defaults
        final_provider_id = provider_id if provider_id else "system"
        final_model = model if model else "proactive-notification"

        # Post as assistant message
        turn_id = memory_store.save_turn(
            session_id=session_id,
            role="assistant",
            content=content,
            created_at=datetime.utcnow(),
            provider_id=final_provider_id,
            model=final_model,
            intent="proactive_notification",
            metadata=metadata,
            mode="personal",
            user_id=user_id
        )

        logger.info(f"[MESSAGE_POSTER] Posted {message_type} message (turn_id={turn_id}) to session {session_id} for user {user_id}")
        return turn_id

    except Exception as e:
        logger.error(f"[MESSAGE_POSTER] Failed to post proactive message for user {user_id}: {e}")
        return None


def _get_user_session(memory_store, user_id: int) -> Optional[str]:
    """
    Get the user's most recent Personal mode session.

    Args:
        memory_store: MemoryStore instance
        user_id: User ID

    Returns:
        str: Session ID or None if not found
    """
    try:
        from sqlalchemy import text

        with memory_store.engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id FROM sessions
                    WHERE user_id = :user_id
                      AND mode = 'personal'
                    ORDER BY updated_at DESC
                    LIMIT 1
                """),
                {"user_id": user_id}
            )

            row = result.fetchone()
            return row[0] if row else None

    except Exception as e:
        logger.error(f"[MESSAGE_POSTER] Error getting user session: {e}")
        return None


def dismiss_proactive_message(memory_store, turn_id: int, user_id: int) -> bool:
    """
    Dismiss a proactive notification by marking it as dismissed in metadata.

    Args:
        memory_store: MemoryStore instance
        turn_id: Turn ID to dismiss
        user_id: User ID (for validation)

    Returns:
        bool: True if dismissed successfully
    """
    try:
        from sqlalchemy import text
        import json

        with memory_store.engine.connect() as conn:
            # Get current turn and verify ownership through session
            result = conn.execute(
                text("""
                    SELECT t.metadata, s.user_id
                    FROM turns t
                    JOIN sessions s ON t.session_id = s.id
                    WHERE t.id = :turn_id
                """),
                {"turn_id": turn_id}
            )

            row = result.fetchone()
            if not row:
                logger.warning(f"[MESSAGE_POSTER] Turn {turn_id} not found")
                return False

            metadata_str, turn_user_id = row

            # Verify user owns this turn (session belongs to user)
            if turn_user_id != user_id:
                logger.warning(f"[MESSAGE_POSTER] User {user_id} attempted to dismiss turn {turn_id} owned by user {turn_user_id}")
                return False

            # Parse and update metadata
            metadata = json.loads(metadata_str) if metadata_str else {}

            # Only allow dismissing proactive messages
            if not metadata.get("proactive"):
                logger.warning(f"[MESSAGE_POSTER] Turn {turn_id} is not a proactive message")
                return False

            metadata["dismissed"] = True
            metadata["dismissed_at"] = datetime.utcnow().isoformat()

            # Update turn with new metadata
            conn.execute(
                text("""
                    UPDATE turns
                    SET metadata = :metadata
                    WHERE id = :turn_id
                """),
                {
                    "turn_id": turn_id,
                    "metadata": json.dumps(metadata)
                }
            )
            conn.commit()

            logger.info(f"[MESSAGE_POSTER] Dismissed proactive message (turn_id={turn_id}) for user {user_id}")
            return True

    except Exception as e:
        logger.error(f"[MESSAGE_POSTER] Failed to dismiss message {turn_id}: {e}")
        return False
