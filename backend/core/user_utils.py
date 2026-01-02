"""
User ID Normalization Utilities

This module provides utilities for handling user_id normalization during the
migration from String to Integer user_id types across the THEO database.

Background:
-----------
THEO initially used a single "local" user (String) before implementing multi-user
authentication. When authentication was added, new records used Integer user_ids,
but legacy data remained with "local" strings, causing silent query failures.

This module provides safe conversion functions to normalize user_id values to
integers, enabling backwards compatibility during the migration period.
"""

import logging
from typing import Any, Optional

# Default user ID for unauthenticated/legacy users
DEFAULT_USER_ID = 1

logger = logging.getLogger(__name__)


def normalize_user_id(user_id: Any, default: int = DEFAULT_USER_ID) -> int:
    """
    Normalize a user_id to an integer, handling various input types.

    This function safely converts user_id values from different formats to
    integers, providing backwards compatibility during the String → Integer
    migration period.

    Conversion rules:
    - Integer → passthrough (already correct type)
    - "local" string → 1 (legacy user)
    - String integer (e.g., "123") → parsed to int
    - None → default (typically 1)
    - Empty string → default
    - Other strings → warning + default

    Args:
        user_id: The user_id to normalize (can be int, str, or None)
        default: The default user_id to use for None/invalid values (default: 1)

    Returns:
        int: Normalized user_id

    Examples:
        >>> normalize_user_id(1)
        1
        >>> normalize_user_id("local")
        1
        >>> normalize_user_id("123")
        123
        >>> normalize_user_id(None)
        1
        >>> normalize_user_id("", default=5)
        5
    """
    # Already an integer - passthrough
    if isinstance(user_id, int):
        logger.debug(f"normalize_user_id: Integer passthrough: {user_id}")
        return user_id

    # None - use default
    if user_id is None:
        logger.debug(f"normalize_user_id: None → {default}")
        return default

    # String handling
    if isinstance(user_id, str):
        # Empty string - use default
        if not user_id.strip():
            logger.debug(f"normalize_user_id: Empty string → {default}")
            return default

        # Legacy "local" user - convert to default
        if user_id.strip().lower() == "local":
            logger.debug(f"normalize_user_id: 'local' → {default}")
            return default

        # Try parsing as integer string
        try:
            parsed_id = int(user_id)
            logger.debug(f"normalize_user_id: String integer '{user_id}' → {parsed_id}")
            return parsed_id
        except ValueError:
            logger.warning(
                f"normalize_user_id: Invalid string user_id '{user_id}', "
                f"using default {default}"
            )
            return default

    # Unexpected type - log warning and use default
    logger.warning(
        f"normalize_user_id: Unexpected type {type(user_id).__name__} "
        f"for user_id '{user_id}', using default {default}"
    )
    return default


def ensure_user_exists(memory, user_id: int) -> bool:
    """
    Verify that a user_id exists in the database.

    This is a safety check to prevent foreign key violations when the
    foreign key constraints are enabled in Phase 6.

    Args:
        memory: MemoryStore instance
        user_id: Integer user_id to verify

    Returns:
        bool: True if user exists, False otherwise

    Example:
        >>> from core.memory.store import MemoryStore
        >>> memory = MemoryStore()
        >>> ensure_user_exists(memory, 1)
        True
        >>> ensure_user_exists(memory, 999)
        False
    """
    try:
        from sqlalchemy import select

        with memory.engine.connect() as conn:
            result = conn.execute(
                select(memory.users.c.id).where(memory.users.c.id == user_id)
            )
            exists = result.fetchone() is not None

            if not exists:
                logger.warning(f"User ID {user_id} does not exist in database")

            return exists

    except Exception as e:
        logger.error(f"Error checking user existence: {e}")
        return False


def get_user_id_from_token(memory, token: Optional[str]) -> int:
    """
    Extract user_id from an authentication token.

    This helper function is useful in route handlers to get the authenticated
    user_id or fall back to the default user for unauthenticated requests.

    Args:
        memory: MemoryStore instance
        token: Authentication token (from Authorization header)

    Returns:
        int: Authenticated user_id or DEFAULT_USER_ID if not authenticated

    Example:
        >>> from flask import request
        >>> auth_header = request.headers.get("Authorization")
        >>> token = auth_header.split(" ")[1] if auth_header else None
        >>> user_id = get_user_id_from_token(memory, token)
    """
    if not token:
        logger.debug("No token provided, using DEFAULT_USER_ID")
        return DEFAULT_USER_ID

    try:
        from datetime import datetime

        session = memory.get_auth_session(token)
        if session and session.get("expires_at"):
            # Check if session is still valid
            if session["expires_at"] >= datetime.utcnow():
                user_id = session.get("user_id")
                if user_id:
                    logger.debug(f"Valid token for user_id: {user_id}")
                    return normalize_user_id(user_id)
            else:
                logger.debug("Token expired, using DEFAULT_USER_ID")
        else:
            logger.debug("Invalid session, using DEFAULT_USER_ID")

    except Exception as e:
        logger.error(f"Error extracting user_id from token: {e}")

    return DEFAULT_USER_ID
