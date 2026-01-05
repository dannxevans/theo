"""
WHOOP action handlers.

Provides handlers for WHOOP fitness tracker queries:
- Sleep summary
- Recovery/stress data
- Workout history
"""

from typing import Dict, Any
from datetime import datetime, timedelta
import logging

from .base_handler import BaseActionHandler
from services.whoop_client import WHOOPClient


class WHOOPHandlers(BaseActionHandler):
    """Handlers for WHOOP-related actions."""

    def __init__(self, action_registry, memory_store, confirmation_manager=None):
        """Initialize WHOOP handlers."""
        super().__init__(action_registry, memory_store, confirmation_manager)
        self.logger = logging.getLogger(__name__)

    def handle_whoop(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle WHOOP queries.

        Examples:
        - "How did I sleep last night?"
        - "How recovered am I today?"
        - "How hard was my workout yesterday?"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with WHOOP data
        """
        user_text_lower = user_text.lower()

        # Check if WHOOP credentials exist
        credentials = self.memory.refresh_whoop_token_if_needed(user_id)
        if not credentials or not credentials.get('is_valid'):
            return self._format_success_response(
                "You haven't connected your WHOOP account yet. Go to Settings > Personal Actions > WHOOP to connect.",
                "whoop"
            )

        # Create WHOOP client
        client = WHOOPClient(credentials['access_token'])

        try:
            # Determine query type
            if any(keyword in user_text_lower for keyword in ["sleep", "slept", "rest", "bed"]):
                return self._handle_sleep_query(client, user_id)
            elif any(keyword in user_text_lower for keyword in ["recovery", "recovered", "hrv", "stress", "strain"]):
                return self._handle_recovery_query(client, user_id)
            elif any(keyword in user_text_lower for keyword in ["workout", "exercise", "training", "activity"]):
                return self._handle_workout_query(client, user_id)
            else:
                # Default to recovery summary
                return self._handle_recovery_query(client, user_id)

        except Exception as e:
            self.logger.error(f"[WHOOP] Error fetching WHOOP data: {e}")
            return self._format_error_response(
                f"Sorry, I couldn't fetch your WHOOP data. Error: {str(e)}",
                "whoop"
            )

    def _handle_sleep_query(self, client: WHOOPClient, user_id: int) -> Dict:
        """Handle sleep-related queries."""
        try:
            sleep = client.get_latest_sleep()
            if not sleep:
                return self._format_success_response(
                    "I couldn't find any recent sleep data from WHOOP.",
                    "whoop"
                )

            # Extract sleep metrics
            score = sleep.get('score', {})
            performance = score.get('sleep_performance_percentage', 0)
            efficiency = score.get('sleep_efficiency_percentage', 0)

            # Duration can be in score or at top level
            duration_ms = score.get('total_in_bed_time_milli') or sleep.get('total_in_bed_time_milli', 0)
            if not duration_ms:
                # Try calculating from start/end times
                start = sleep.get('start')
                end = sleep.get('end')
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                    except:
                        pass

            duration_hours = duration_ms / 1000 / 60 / 60 if duration_ms else 0

            # Build response
            response = f"**Last Night's Sleep**\n\n"
            response += f"Sleep Performance: {performance:.0f}%\n"
            response += f"Sleep Efficiency: {efficiency:.0f}%\n"
            response += f"Time in Bed: {duration_hours:.1f} hours\n"

            end_time = sleep.get('end')
            if end_time:
                dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                response += f"\nWoke up at: {dt.strftime('%I:%M %p')}"

            # Process through lightweight LLM
            processed_response = self._process_with_llm(response, user_id)

            return self._format_success_response(processed_response, "whoop")

        except Exception as e:
            self.logger.error(f"[WHOOP] Error fetching sleep data: {e}")
            return self._format_error_response(
                f"Sorry, I couldn't fetch your sleep data: {str(e)}",
                "whoop"
            )

    def _handle_recovery_query(self, client: WHOOPClient, user_id: int) -> Dict:
        """Handle recovery/stress-related queries."""
        try:
            recovery = client.get_latest_recovery()
            if not recovery:
                return self._format_success_response(
                    "I couldn't find any recent recovery data from WHOOP.",
                    "whoop"
                )

            # Extract recovery metrics
            recovery_score = recovery.get('recovery_score', 0)
            hrv = recovery.get('hrv_rmssd_milli', 0)
            resting_hr = recovery.get('resting_heart_rate', 0)
            spo2 = recovery.get('spo2_percentage', 0)

            # Build response
            response = f"**Today's Recovery**\n\n"
            response += f"Recovery Score: {recovery_score:.0f}%\n"

            if hrv:
                response += f"HRV (RMSSD): {hrv:.1f} ms\n"
            if resting_hr:
                response += f"Resting HR: {resting_hr:.0f} bpm\n"
            if spo2:
                response += f"Blood Oxygen: {spo2:.1f}%\n"

            # Interpretation
            if recovery_score >= 67:
                interpretation = "\nYour body appears well-recovered and ready for training."
            elif recovery_score >= 34:
                interpretation = "\nYour recovery is moderate. Consider your activity level accordingly."
            else:
                interpretation = "\nYour recovery metrics suggest your body may benefit from additional rest."

            response += interpretation

            # Process through lightweight LLM
            processed_response = self._process_with_llm(response, user_id)

            return self._format_success_response(processed_response, "whoop")

        except Exception as e:
            self.logger.error(f"[WHOOP] Error fetching recovery data: {e}")
            return self._format_error_response(
                f"Sorry, I couldn't fetch your recovery data: {str(e)}",
                "whoop"
            )

    def _handle_workout_query(self, client: WHOOPClient, user_id: int) -> Dict:
        """Handle workout-related queries."""
        try:
            workout = client.get_latest_workout()
            if not workout:
                return self._format_success_response(
                    "I couldn't find any recent workout data from WHOOP.",
                    "whoop"
                )

            # Extract workout metrics
            score = workout.get('score', {})
            strain = score.get('strain', 0)
            avg_hr = score.get('average_heart_rate', 0)
            max_hr = score.get('max_heart_rate', 0)
            kilojoules = score.get('kilojoule', 0)
            calories = kilojoules * 0.239 if kilojoules else 0

            # Duration can be in score or at top level, and in different formats
            duration_ms = score.get('duration_milli') or workout.get('duration_milli', 0)
            if not duration_ms:
                # Try calculating from start/end times
                start = workout.get('start')
                end = workout.get('end')
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
                    except:
                        pass

            duration_min = duration_ms / 1000 / 60 if duration_ms else 0

            # Sport ID
            sport_id = workout.get('sport_id', 0)
            sport_name = self._get_sport_name(sport_id)

            # Build response
            response = f"**Last Workout**\n\n"
            response += f"Activity: {sport_name}\n"
            response += f"Strain: {strain:.1f}\n"
            response += f"Duration: {duration_min:.0f} minutes\n"

            if avg_hr:
                response += f"Avg HR: {avg_hr:.0f} bpm\n"
            if max_hr:
                response += f"Max HR: {max_hr:.0f} bpm\n"
            if calories:
                response += f"Calories: {calories:.0f}\n"

            end_time = workout.get('end')
            if end_time:
                dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                response += f"\nCompleted: {dt.strftime('%I:%M %p on %b %d')}"

            # Process through lightweight LLM
            processed_response = self._process_with_llm(response, user_id)

            return self._format_success_response(processed_response, "whoop")

        except Exception as e:
            self.logger.error(f"[WHOOP] Error fetching workout data: {e}")
            return self._format_error_response(
                f"Sorry, I couldn't fetch your workout data: {str(e)}",
                "whoop"
            )

    def _get_sport_name(self, sport_id: int) -> str:
        """Map WHOOP sport ID to readable name."""
        sport_map = {
            0: "Activity", 1: "Running", 16: "Baseball", 17: "Basketball",
            18: "Rowing", 19: "Fencing", 20: "Field Hockey", 21: "Football",
            22: "Golf", 24: "Ice Hockey", 25: "Lacrosse", 27: "Rugby",
            28: "Sailing", 29: "Skiing", 30: "Soccer", 31: "Softball",
            32: "Squash", 33: "Swimming", 34: "Tennis", 35: "Track & Field",
            36: "Volleyball", 37: "Water Polo", 38: "Wrestling", 39: "Boxing",
            42: "Dance", 43: "Pilates", 44: "Yoga", 45: "Weightlifting",
            47: "Cross Country Skiing", 48: "Functional Fitness", 49: "Duathlon",
            51: "Gymnastics", 52: "Hiking/Rucking", 53: "Horseback Riding",
            55: "Kayaking", 56: "Martial Arts", 57: "Mountain Biking",
            59: "Powerlifting", 60: "Rock Climbing", 61: "Paddleboarding",
            62: "Triathlon", 63: "Walking", 64: "Surfing", 65: "Elliptical",
            66: "Stair Climbing", 70: "Meditation", 71: "Other", 73: "Diving",
            96: "HIIT", 97: "Spin", 98: "Jiu Jitsu", 100: "Cricket",
            101: "Pickleball", 121: "Cycling"
        }
        return sport_map.get(sport_id, f"Activity (ID: {sport_id})")

    def _process_with_llm(self, raw_data: str, user_id: int) -> str:
        """
        Process raw WHOOP data through lightweight LLM for natural language output.

        Args:
            raw_data: Raw WHOOP data summary
            user_id: User ID for routing

        Returns:
            str: Processed natural language summary
        """
        try:
            from core.router import route_request

            prompt = f"""You are presenting WHOOP data to the user. Convert this technical data into a brief, friendly, conversational summary.

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

            self.logger.info(f"[WHOOP] Processed query response via lightweight LLM")
            return processed_text

        except Exception as e:
            self.logger.error(f"[WHOOP] LLM processing failed: {e}, using raw data")
            return raw_data
