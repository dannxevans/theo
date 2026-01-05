"""
WHOOP Stress Notification Service

Checks for new recovery/stress data and sends daily summaries.
Stress is derived from HRV trends in recovery data.
Includes medical guardrails - observational language only.
"""

import logging
from datetime import datetime, time
from typing import Optional

from core.memory import MemoryStore
from services.whoop_client import WHOOPClient

logger = logging.getLogger(__name__)


class WHOOPStressService:
    """Service for WHOOP stress/recovery notifications."""

    def __init__(self, memory: MemoryStore):
        """
        Initialize WHOOP stress service.

        Args:
            memory: MemoryStore instance
        """
        self.memory = memory

    def check_and_notify(self, user_id: int) -> bool:
        """
        Check for new recovery/stress data and send notifications.
        Typically sent in the afternoon (matching WHOOP app behavior).

        Args:
            user_id: User ID

        Returns:
            bool: True if notification sent, False otherwise
        """
        try:
            logger.info(f"[WHOOP_STRESS] Starting stress check for user {user_id}")

            # Check if stress notifications are enabled
            settings = self.memory.get_whoop_settings(user_id)
            if not settings or not settings.get('stress_notifications_enabled'):
                logger.info(f"[WHOOP_STRESS] Stress notifications disabled for user {user_id} (settings: {settings})")
                return False

            logger.info(f"[WHOOP_STRESS] Settings OK, checking credentials...")

            # Get WHOOP credentials (with automatic token refresh)
            credentials = self.memory.refresh_whoop_token_if_needed(user_id)
            if not credentials or not credentials.get('is_valid'):
                logger.warning(f"[WHOOP_STRESS] No valid credentials for user {user_id}")
                return False

            logger.info(f"[WHOOP_STRESS] Credentials OK, fetching recovery data from WHOOP API...")

            # Create WHOOP client
            client = WHOOPClient(credentials['access_token'])

            # Get latest recovery record
            recovery = client.get_latest_recovery()
            if not recovery:
                logger.info(f"[WHOOP_STRESS] No recent recovery data for user {user_id}")
                return False

            logger.info(f"[WHOOP_STRESS] Recovery data found, checking ID...")

            recovery_id = recovery.get('id')
            if not recovery_id:
                logger.warning(f"[WHOOP_STRESS] Recovery record missing ID for user {user_id}")
                return False

            logger.info(f"[WHOOP_STRESS] Recovery ID: {recovery_id}, checking if already notified...")

            # Check if already notified
            if self.memory.is_whoop_data_tracked(recovery_id):
                logger.info(f"[WHOOP_STRESS] Already notified for recovery {recovery_id}")
                return False

            logger.info(f"[WHOOP_STRESS] Not yet notified, generating summary...")

            # Generate summary
            summary = self._generate_stress_summary(recovery)

            logger.info(f"[WHOOP_STRESS] Sending notification...")

            # Send notification via message system
            self._send_notification(user_id, summary)

            # Mark as notified
            self.memory.track_whoop_data(user_id, 'stress', recovery_id)

            logger.info(f"[WHOOP_STRESS] ✓ Sent stress notification for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[WHOOP_STRESS] Error checking stress for user {user_id}: {e}", exc_info=True)
            return False

    def _generate_stress_summary(self, recovery: dict) -> str:
        """
        Generate observational stress/recovery summary with medical guardrails.

        Args:
            recovery: Recovery data from WHOOP API (already the score dict)

        Returns:
            str: Summary text
        """
        # Debug: log the recovery data structure
        logger.info(f"[WHOOP_STRESS] Recovery data structure: {recovery}")

        # Recovery data is already the score dict from get_latest_recovery()
        # Recovery metrics
        recovery_score = recovery.get('recovery_score', 0)
        hrv_rmssd = recovery.get('hrv_rmssd_milli', 0)
        resting_hr = recovery.get('resting_heart_rate', 0)
        spo2 = recovery.get('spo2_percentage', 0)
        skin_temp = recovery.get('skin_temp_celsius', 0)

        logger.info(f"[WHOOP_STRESS] Extracted values - recovery_score: {recovery_score}, hrv: {hrv_rmssd}, hr: {resting_hr}")

        # User calibrating data (for context)
        user_calibrating = recovery.get('user_calibrating', False)

        # Build observational summary (medical guardrails - no advice/diagnosis)
        summary = f"**Daily Recovery & Stress Summary**\n\n"

        if user_calibrating:
            summary += "📊 **Note:** Your WHOOP is still calibrating to your baseline.\n\n"

        summary += f"💚 **Recovery Score:** {recovery_score:.0f}%\n\n"

        summary += f"📊 **Key Metrics:**\n"

        if hrv_rmssd:
            summary += f"- **HRV (RMSSD):** {hrv_rmssd:.1f} ms\n"
            summary += f"  Heart Rate Variability - a measure often associated with stress and recovery\n\n"

        if resting_hr:
            summary += f"- **Resting Heart Rate:** {resting_hr:.0f} bpm\n\n"

        if spo2:
            summary += f"- **Blood Oxygen (SpO2):** {spo2:.1f}%\n\n"

        if skin_temp:
            summary += f"- **Skin Temperature:** {skin_temp:.1f}°C\n\n"

        # Interpret recovery score (observational only)
        if recovery_score >= 67:
            interpretation = "Your recovery metrics suggest your body is well-recovered."
        elif recovery_score >= 34:
            interpretation = "Your recovery metrics suggest moderate recovery."
        else:
            interpretation = "Your recovery metrics suggest your body may need additional rest."

        summary += f"💡 **Observation:** {interpretation}\n"

        # Add timestamp
        created_at = recovery.get('created_at')
        if created_at:
            summary += f"\n🕐 Data from: {self._format_timestamp(created_at)}"

        # Medical disclaimer
        summary += "\n\n⚠️ *This is observational data only. Not medical advice. Consult healthcare professionals for health concerns.*"

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
        Uses lightweight LLM to process raw data into natural language.

        Args:
            user_id: User ID
            summary: Summary text to send (raw data)
        """
        # Process summary through lightweight LLM for natural language
        processed_content = self._process_with_llm(summary, user_id)

        # Store as a proactive message in the turns table
        from core.proactive.message_poster import post_proactive_message

        post_proactive_message(
            memory_store=self.memory,
            user_id=user_id,
            message_type="whoop_stress",
            content=processed_content,
            provider_id="whoop",
            model="whoop-stress-notification"
        )

    def _process_with_llm(self, raw_data: str, user_id: int) -> str:
        """
        Process raw WHOOP data through lightweight LLM for natural language output.

        Args:
            raw_data: Raw recovery data summary
            user_id: User ID for routing

        Returns:
            str: Processed natural language summary
        """
        try:
            from core.router import route_request

            prompt = f"""You are presenting WHOOP recovery data to the user. Convert this technical data into a brief, friendly, conversational summary.

Guidelines:
- Be concise (2-3 sentences max)
- Use natural language, avoid bullet points
- Focus on what the data means for their day
- Maintain medical guardrails - use observational language only
- Do NOT give medical advice or diagnosis
- Keep the tone friendly and supportive

Raw data:
{raw_data}

Present this data in a natural, conversational way:"""

            router_context = {
                "text": prompt,
                "user_id": user_id,
                "force_intent": "system",  # Use lightweight LLM
                "memory": self.memory
            }

            result = route_request(router_context)
            processed_text = result.get("text", raw_data)

            logger.info(f"[WHOOP_STRESS] Processed notification via lightweight LLM")
            return processed_text

        except Exception as e:
            logger.error(f"[WHOOP_STRESS] LLM processing failed: {e}, using raw data")
            return raw_data
