"""
WHOOP Sleep Notification Service

Checks for new sleep records and sends proactive summaries.
Includes medical guardrails - observational language only.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from core.memory import MemoryStore
from services.whoop_client import WHOOPClient

logger = logging.getLogger(__name__)


class WHOOPSleepService:
    """Service for WHOOP sleep notifications."""

    def __init__(self, memory: MemoryStore):
        """
        Initialize WHOOP sleep service.

        Args:
            memory: MemoryStore instance
        """
        self.memory = memory

    def check_and_notify(self, user_id: int) -> bool:
        """
        Check for new sleep records and send notifications.

        Args:
            user_id: User ID

        Returns:
            bool: True if notification sent, False otherwise
        """
        try:
            # Check if sleep notifications are enabled
            settings = self.memory.get_whoop_settings(user_id)
            if not settings or not settings.get('sleep_notifications_enabled'):
                logger.debug(f"[WHOOP_SLEEP] Sleep notifications disabled for user {user_id}")
                return False

            # Get WHOOP credentials (with automatic token refresh)
            credentials = self.memory.refresh_whoop_token_if_needed(user_id)
            if not credentials or not credentials.get('is_valid'):
                logger.warning(f"[WHOOP_SLEEP] No valid credentials for user {user_id}")
                return False

            # Create WHOOP client
            client = WHOOPClient(credentials['access_token'])

            # Get latest sleep record
            sleep = client.get_latest_sleep()
            if not sleep:
                logger.debug(f"[WHOOP_SLEEP] No recent sleep data for user {user_id}")
                return False

            sleep_id = sleep.get('id')
            if not sleep_id:
                logger.warning(f"[WHOOP_SLEEP] Sleep record missing ID for user {user_id}")
                return False

            # Check if already notified
            if self.memory.has_whoop_data_been_notified(user_id, 'sleep', sleep_id):
                logger.debug(f"[WHOOP_SLEEP] Already notified for sleep {sleep_id}")
                return False

            # Get associated recovery data
            sleep_with_recovery = client.get_sleep_with_recovery(sleep_id)
            if not sleep_with_recovery:
                logger.debug(f"[WHOOP_SLEEP] No recovery data for sleep {sleep_id}")
                return False

            # Generate summary
            summary = self._generate_sleep_summary(sleep_with_recovery)

            # Send notification via message system
            self._send_notification(user_id, summary)

            # Mark as notified
            self.memory.track_whoop_data(user_id, 'sleep', sleep_id)

            logger.info(f"[WHOOP_SLEEP] ✓ Sent sleep notification for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[WHOOP_SLEEP] Error checking sleep for user {user_id}: {e}")
            return False

    def _generate_sleep_summary(self, data: dict) -> str:
        """
        Generate observational sleep summary with medical guardrails.

        Args:
            data: Combined sleep and recovery data

        Returns:
            str: Summary text
        """
        sleep = data.get('sleep', {})
        recovery = data.get('recovery', {})

        # Extract key metrics
        score = sleep.get('score', {})
        sleep_performance = score.get('sleep_performance_percentage', 0)
        sleep_efficiency = score.get('sleep_efficiency_percentage', 0)

        # Duration in milliseconds, convert to hours
        total_duration_ms = sleep.get('score', {}).get('total_in_bed_time_milli', 0)
        total_hours = total_duration_ms / 1000 / 60 / 60

        # Recovery metrics
        recovery_score = recovery.get('score', {}).get('recovery_score', 0)
        hrv = recovery.get('score', {}).get('hrv_rmssd_milli', 0)
        resting_hr = recovery.get('score', {}).get('resting_heart_rate', 0)

        # Build observational summary (medical guardrails - no advice/diagnosis)
        summary = f"**Sleep Summary**\n\n"
        summary += f"📊 **Metrics Observed:**\n"
        summary += f"- Sleep Performance: {sleep_performance:.0f}%\n"
        summary += f"- Sleep Efficiency: {sleep_efficiency:.0f}%\n"
        summary += f"- Total Time in Bed: {total_hours:.1f} hours\n"

        if recovery_score:
            summary += f"\n💚 **Recovery Data:**\n"
            summary += f"- Recovery Score: {recovery_score:.0f}%\n"

        if hrv:
            summary += f"- HRV (RMSSD): {hrv:.1f} ms\n"

        if resting_hr:
            summary += f"- Resting Heart Rate: {resting_hr:.0f} bpm\n"

        # Add timestamp
        end_time = sleep.get('end')
        if end_time:
            summary += f"\n🕐 Sleep ended: {self._format_timestamp(end_time)}"

        return summary

    def _format_timestamp(self, iso_timestamp: str) -> str:
        """Format ISO timestamp to readable format."""
        try:
            dt = datetime.fromisoformat(iso_timestamp.replace('Z', '+00:00'))
            return dt.strftime('%I:%M %p on %B %d')
        except:
            return iso_timestamp

    def _send_notification(self, user_id: int, summary: str):
        """
        Send notification to user via message system.

        Args:
            user_id: User ID
            summary: Summary text to send
        """
        # Store as a pending message in the database
        # This will be picked up by the chat interface
        self.memory.store_proactive_message(
            user_id=user_id,
            category="health",
            message_type="whoop_sleep",
            content=summary,
            metadata={"source": "whoop", "data_type": "sleep"}
        )
