"""
WHOOP Workout Notification Service

Checks for new workout records and sends proactive summaries.
Includes medical guardrails - observational language only.
"""

import logging
from datetime import datetime
from typing import Optional

from core.memory import MemoryStore
from services.whoop_client import WHOOPClient

logger = logging.getLogger(__name__)


class WHOOPWorkoutService:
    """Service for WHOOP workout notifications."""

    def __init__(self, memory: MemoryStore):
        """
        Initialize WHOOP workout service.

        Args:
            memory: MemoryStore instance
        """
        self.memory = memory

    def check_and_notify(self, user_id: int) -> bool:
        """
        Check for new workout records and send notifications.

        Args:
            user_id: User ID

        Returns:
            bool: True if notification sent, False otherwise
        """
        try:
            # Check if workout notifications are enabled
            settings = self.memory.get_whoop_settings(user_id)
            if not settings or not settings.get('workout_notifications_enabled'):
                logger.debug(f"[WHOOP_WORKOUT] Workout notifications disabled for user {user_id}")
                return False

            # Get WHOOP credentials (with automatic token refresh)
            credentials = self.memory.refresh_whoop_token_if_needed(user_id)
            if not credentials or not credentials.get('is_valid'):
                logger.warning(f"[WHOOP_WORKOUT] No valid credentials for user {user_id}")
                return False

            # Create WHOOP client
            client = WHOOPClient(credentials['access_token'])

            # Get latest workout record
            workout = client.get_latest_workout()
            if not workout:
                logger.debug(f"[WHOOP_WORKOUT] No recent workout data for user {user_id}")
                return False

            workout_id = workout.get('id')
            if not workout_id:
                logger.warning(f"[WHOOP_WORKOUT] Workout record missing ID for user {user_id}")
                return False

            # Check if already notified
            if self.memory.has_whoop_data_been_notified(user_id, 'workout', workout_id):
                logger.debug(f"[WHOOP_WORKOUT] Already notified for workout {workout_id}")
                return False

            # Generate summary
            summary = self._generate_workout_summary(workout)

            # Send notification via message system
            self._send_notification(user_id, summary)

            # Mark as notified
            self.memory.track_whoop_data(user_id, 'workout', workout_id)

            logger.info(f"[WHOOP_WORKOUT] ✓ Sent workout notification for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"[WHOOP_WORKOUT] Error checking workout for user {user_id}: {e}")
            return False

    def _generate_workout_summary(self, workout: dict) -> str:
        """
        Generate observational workout summary with medical guardrails.

        Args:
            workout: Workout data from WHOOP API

        Returns:
            str: Summary text
        """
        # Extract key metrics
        score = workout.get('score', {})
        strain = score.get('strain', 0)
        avg_hr = score.get('average_heart_rate', 0)
        max_hr = score.get('max_heart_rate', 0)
        kilojoules = score.get('kilojoule', 0)

        # Duration in milliseconds, convert to minutes
        duration_ms = workout.get('score', {}).get('duration_milli', 0)
        duration_min = duration_ms / 1000 / 60

        # Sport ID and name
        sport_id = workout.get('sport_id', 0)
        sport_name = self._get_sport_name(sport_id)

        # Build observational summary (medical guardrails - no advice/diagnosis)
        summary = f"**Workout Summary**\n\n"
        summary += f"🏃 **Activity:** {sport_name}\n\n"
        summary += f"📊 **Metrics Observed:**\n"
        summary += f"- Strain: {strain:.1f}\n"
        summary += f"- Duration: {duration_min:.0f} minutes\n"

        if avg_hr:
            summary += f"- Average Heart Rate: {avg_hr:.0f} bpm\n"

        if max_hr:
            summary += f"- Max Heart Rate: {max_hr:.0f} bpm\n"

        if kilojoules:
            calories = kilojoules * 0.239  # Convert to calories
            summary += f"- Energy: {calories:.0f} calories\n"

        # Add timestamp
        end_time = workout.get('end')
        if end_time:
            summary += f"\n🕐 Workout ended: {self._format_timestamp(end_time)}"

        return summary

    def _get_sport_name(self, sport_id: int) -> str:
        """
        Map WHOOP sport ID to readable name.

        Args:
            sport_id: WHOOP sport identifier

        Returns:
            str: Sport name
        """
        # Common WHOOP sport IDs
        sport_map = {
            0: "Activity",
            1: "Running",
            16: "Baseball",
            17: "Basketball",
            18: "Rowing",
            19: "Fencing",
            20: "Field Hockey",
            21: "Football",
            22: "Golf",
            24: "Ice Hockey",
            25: "Lacrosse",
            27: "Rugby",
            28: "Sailing",
            29: "Skiing",
            30: "Soccer",
            31: "Softball",
            32: "Squash",
            33: "Swimming",
            34: "Tennis",
            35: "Track & Field",
            36: "Volleyball",
            37: "Water Polo",
            38: "Wrestling",
            39: "Boxing",
            42: "Dance",
            43: "Pilates",
            44: "Yoga",
            45: "Weightlifting",
            47: "Cross Country Skiing",
            48: "Functional Fitness",
            49: "Duathlon",
            51: "Gymnastics",
            52: "Hiking/Rucking",
            53: "Horseback Riding",
            55: "Kayaking",
            56: "Martial Arts",
            57: "Mountain Biking",
            59: "Powerlifting",
            60: "Rock Climbing",
            61: "Paddleboarding",
            62: "Triathlon",
            63: "Walking",
            64: "Surfing",
            65: "Elliptical",
            66: "Stair Climbing",
            70: "Meditation",
            71: "Other",
            73: "Diving",
            74: "Operations - Tactical",
            75: "Operations - Medical",
            76: "Operations - Flying",
            77: "Operations - Water",
            82: "Ultimate",
            83: "Climber",
            84: "Jumping Rope",
            85: "Australian Football",
            86: "Skateboarding",
            87: "Coaching",
            88: "Ice Bath",
            89: "Commuting",
            90: "Gaming",
            91: "Snowboarding",
            92: "Motocross",
            93: "Caddying",
            94: "Obstacle Course Racing",
            95: "Motor Racing",
            96: "HIIT",
            97: "Spin",
            98: "Jiu Jitsu",
            99: "Manual Labor",
            100: "Cricket",
            101: "Pickleball",
            102: "Inline Skating",
            103: "Box Fitness",
            104: "Spikeball",
            105: "Wheelchair Pushing",
            106: "Paddle Tennis",
            107: "Barre",
            108: "Stage Performance",
            109: "High Stress Work",
            110: "Parkour",
            111: "Gaelic Football",
            112: "Hurling/Camogie",
            121: "Cycling",
            125: "Swimming (Open Water)",
            126: "Breathwork",
        }

        return sport_map.get(sport_id, f"Activity (ID: {sport_id})")

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
            message_type="whoop_workout",
            content=summary,
            metadata={"source": "whoop", "data_type": "workout"}
        )
