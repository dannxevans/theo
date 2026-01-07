"""
WHOOP Token Refresh Service

Proactively refreshes WHOOP OAuth tokens to prevent expiration.

Background:
- WHOOP access tokens expire after 1 hour (3600 seconds)
- Tokens must be refreshed before expiration to maintain access
- This service runs every 45 minutes to ensure tokens stay valid
- Operates independently of user activity and notification settings

Implementation:
- Finds all users with WHOOP credentials
- Refreshes tokens that are expired or will expire soon
- Logs success/failure for monitoring
- Gracefully handles errors without disrupting other services
"""

import logging
from core.user_utils import normalize_user_id

logger = logging.getLogger(__name__)


class WHOOPTokenRefreshService:
    """
    Proactive token refresh service for WHOOP integration.

    Ensures all users' WHOOP access tokens remain valid by refreshing
    them before expiration, regardless of user activity.
    """

    def __init__(self, memory_store):
        """
        Initialize the token refresh service.

        Args:
            memory_store: MemoryStore instance for database access
        """
        self.memory = memory_store
        logger.info("[WHOOP_TOKEN_REFRESH] Service initialized")

    def refresh_all_tokens(self):
        """
        Refresh WHOOP tokens for all users with active credentials.

        This method:
        1. Finds all users with WHOOP credentials
        2. Attempts to refresh each user's token
        3. Logs results for monitoring

        Designed to be called by scheduler every 45 minutes.
        """
        logger.info("[WHOOP_TOKEN_REFRESH] Starting proactive token refresh cycle")

        try:
            # Get all users with WHOOP credentials
            user_ids = self._get_whoop_users()

            if not user_ids:
                logger.info("[WHOOP_TOKEN_REFRESH] No users with WHOOP credentials found")
                return

            logger.info(f"[WHOOP_TOKEN_REFRESH] Found {len(user_ids)} user(s) with WHOOP credentials")

            # Refresh tokens for each user
            success_count = 0
            skip_count = 0
            error_count = 0

            for user_id in user_ids:
                try:
                    result = self._refresh_user_token(user_id)

                    if result == "refreshed":
                        success_count += 1
                    elif result == "skipped":
                        skip_count += 1
                    else:
                        error_count += 1

                except Exception as e:
                    logger.error(f"[WHOOP_TOKEN_REFRESH] Error refreshing token for user {user_id}: {e}")
                    error_count += 1

            # Log summary
            logger.info(
                f"[WHOOP_TOKEN_REFRESH] Refresh cycle complete: "
                f"{success_count} refreshed, {skip_count} skipped (still valid), "
                f"{error_count} errors"
            )

        except Exception as e:
            logger.error(f"[WHOOP_TOKEN_REFRESH] Error in refresh cycle: {e}", exc_info=True)

    def _get_whoop_users(self):
        """
        Get list of all user IDs with WHOOP credentials.

        Returns:
            list: User IDs with WHOOP integration enabled
        """
        from sqlalchemy import select

        try:
            with self.memory.engine.begin() as conn:
                # Get all user_ids from whoop_credentials table
                result = conn.execute(
                    select(self.memory.whoop_credentials.c.user_id)
                    .where(self.memory.whoop_credentials.c.is_valid == True)
                )

                user_ids = [row[0] for row in result]
                return user_ids

        except Exception as e:
            logger.error(f"[WHOOP_TOKEN_REFRESH] Failed to get WHOOP users: {e}")
            return []

    def _refresh_user_token(self, user_id):
        """
        Refresh WHOOP token for a specific user.

        Args:
            user_id: User ID to refresh token for

        Returns:
            str: "refreshed" if token was refreshed,
                 "skipped" if token still valid,
                 "error" if refresh failed
        """
        try:
            # Normalize user ID
            user_id = normalize_user_id(user_id)

            # Get current credentials
            creds = self.memory.get_whoop_credentials(user_id)

            if not creds:
                logger.warning(f"[WHOOP_TOKEN_REFRESH] No credentials found for user {user_id}")
                return "error"

            if not creds.get('is_valid'):
                logger.warning(f"[WHOOP_TOKEN_REFRESH] Invalid credentials for user {user_id}, skipping")
                return "error"

            # Use the existing refresh_whoop_token_if_needed method
            # This method checks expiration and only refreshes if needed
            logger.debug(f"[WHOOP_TOKEN_REFRESH] Checking token expiration for user {user_id}")

            updated_creds = self.memory.refresh_whoop_token_if_needed(user_id)

            if not updated_creds:
                logger.error(f"[WHOOP_TOKEN_REFRESH] Token refresh failed for user {user_id}")
                return "error"

            # Check if token was actually refreshed by comparing last_refreshed_at
            if updated_creds.get('last_refreshed_at') != creds.get('last_refreshed_at'):
                logger.info(f"[WHOOP_TOKEN_REFRESH] ✓ Token refreshed successfully for user {user_id}")
                return "refreshed"
            else:
                logger.debug(f"[WHOOP_TOKEN_REFRESH] Token still valid for user {user_id}, no refresh needed")
                return "skipped"

        except Exception as e:
            logger.error(f"[WHOOP_TOKEN_REFRESH] Exception refreshing token for user {user_id}: {e}")
            return "error"


# Standalone function for scheduler integration
def refresh_all_whoop_tokens(memory_store):
    """
    Refresh WHOOP tokens for all users.

    This function is called by the scheduler every 45 minutes.

    Args:
        memory_store: MemoryStore instance
    """
    service = WHOOPTokenRefreshService(memory_store)
    service.refresh_all_tokens()
