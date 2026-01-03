"""
Planning action handlers.

Provides handlers for context-aware planning:
- Analyzing activities and creating enriched calendar events
- Enriching calendar view with weather and traffic data
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging
import json

from .base_handler import BaseActionHandler
from core.planning_service import PlanningService


class PlanningHandlers(BaseActionHandler):
    """Handlers for context-aware planning actions."""

    def __init__(self, memory_store, action_router=None):
        """
        Initialize planning handlers.

        Args:
            memory_store: MemoryStore instance
            action_router: Optional ActionRouter instance
        """
        # Set memory directly since we don't have action_registry
        self.memory = memory_store
        self.action_registry = None
        self.confirmation_manager = None
        self.planning_service = PlanningService(memory_store)
        self.logger = logging.getLogger(__name__)

    def handle_planning_query(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle planning queries with context enrichment.

        Examples:
        - "I'm going shopping at Westfield tomorrow at 2pm"
        - "I have a meeting in London this afternoon"
        - "Planning to visit Manchester next Tuesday at 3pm"

        This will:
        1. Analyze the activity to extract location/time/type
        2. Fetch weather, traffic, and calendar context
        3. Create a confirmation with enriched data
        4. If approved, create calendar event with all context

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with confirmation or result
        """
        self.logger.info(f"[PLANNING] Handling planning query: {user_text}")

        # Analyze the activity
        activity_data = self.planning_service.analyze_activity(
            user_text, session_id, str(user_id)
        )

        if not activity_data or not activity_data.get("has_planning_intent"):
            # No valid planning intent detected - don't respond
            # Let the regular LLM handle this as normal conversation
            return None

        # Check for missing information
        missing_info = []
        if not activity_data.get("location"):
            missing_info.append("location")
        if not activity_data.get("time"):
            missing_info.append("time")

        if missing_info:
            missing_str = " and ".join(missing_info)
            return self._format_success_response(
                f"I'd be happy to help plan this! Could you provide the {missing_str}?",
                "planning"
            )

        # Fetch context (weather, traffic, calendar conflicts)
        context_data = self.planning_service.get_context_for_activity(
            activity_data, str(user_id)
        )

        # Create confirmation message with enriched context
        confirmation_msg = self._build_enriched_confirmation(
            activity_data, context_data
        )

        # Check if M365 is connected for calendar creation
        creds = self.memory.get_m365_credentials(user_id)
        if not creds:
            # No M365, just show the context
            return self._format_success_response(
                confirmation_msg + "\n\nNote: Connect Microsoft 365 to add this to your calendar.",
                "planning"
            )

        # Create confirmation for calendar event
        from core.confirmation_manager import ConfirmationManager
        conf_manager = ConfirmationManager(self.memory)

        # Prepare action params
        activity_time = datetime.fromisoformat(activity_data["time"])

        # Build enriched event body with weather/traffic context
        event_body = f"{activity_data['activity_type'].title()} at {activity_data['location']}\n\n"

        # Add weather info to body
        if context_data.get("weather"):
            weather = context_data["weather"]
            event_body += f"Weather: {weather.get('temperature')}°C, {weather.get('description')}\n"

        # Add traffic info to body
        if context_data.get("traffic"):
            traffic = context_data["traffic"]
            duration = traffic.get("duration_in_traffic_minutes", traffic.get("duration_minutes"))
            event_body += f"Travel time: {duration} minutes\n"

        # Add recommendations
        if self._format_recommendations(context_data):
            event_body += f"\n{self._format_recommendations(context_data)}"

        action_params = {
            "subject": f"{activity_data['activity_type'].title()} - {activity_data['location']}",
            "start_time": activity_data["time"],
            "end_time": (activity_time + timedelta(hours=1)).isoformat(),  # Default 1 hour
            "location": activity_data["location"],
            "description": event_body
        }

        # Create confirmation (enrichment data is already in the confirmation message)
        confirmation_result = conf_manager.create_confirmation(
            user_id=user_id,
            session_id=session_id,
            action_type="create_calendar_event",
            action_params=action_params,
            confirmation_message=confirmation_msg
        )

        confirmation_id = confirmation_result["confirmation_id"]

        self.logger.info(f"[PLANNING] Created confirmation {confirmation_id} with enriched context")

        return {
            "text": confirmation_msg,
            "provider": "action_router",
            "model": None,
            "task_type": "planning",
            "metadata": {
                "confirmation_id": confirmation_result["confirmation_id"],
                "action_id": confirmation_result["action_id"],
                "requires_confirmation": True,
                "confirmation_message": confirmation_msg,
                "action_type": "create_calendar_event",
                "action_category": "calendar"
            }
        }

    def _build_enriched_confirmation(
        self,
        activity_data: Dict[str, Any],
        context_data: Dict[str, Any]
    ) -> str:
        """Build confirmation message with weather/traffic/calendar context."""
        from datetime import datetime

        activity_time = datetime.fromisoformat(activity_data["time"])
        time_str = activity_time.strftime("%A, %B %d at %I:%M %p")

        # Build message with explicit line breaks
        lines = [
            "I can add this to your calendar:",
            "",
            f"📅 {activity_data['activity_type'].title()} at {activity_data['location']}",
            f"🕐 {time_str}"
        ]

        # Add weather context
        if context_data.get("weather"):
            weather = context_data["weather"]
            temp = weather.get("temperature", "?")
            desc = weather.get("description", "unknown")
            lines.append(f"☁️ Weather: {temp}°C, {desc}")

        # Add traffic context
        if context_data.get("traffic"):
            traffic = context_data["traffic"]
            duration = traffic.get("duration_in_traffic_minutes", traffic.get("duration_minutes"))
            delay = traffic.get("traffic_delay_minutes", 0)
            traffic_line = f"🚗 Travel time: {duration} minutes"
            if delay > 5:
                traffic_line += f" (+ {int(delay)} min delay)"
            lines.append(traffic_line)

        # Add calendar conflicts
        if context_data.get("calendar_conflicts"):
            conflicts = context_data["calendar_conflicts"]
            lines.append(f"⚠️ Calendar conflicts: {len(conflicts)} event(s) at this time")

        # Add recommendations
        if context_data.get("recommendations"):
            lines.append("💡 Recommendations:")
            for rec in context_data["recommendations"]:
                lines.append(f"   • {rec}")

        lines.append("")
        lines.append("Would you like me to add this to your calendar?")

        return "\n".join(lines)

    def _format_recommendations(self, context_data: Dict[str, Any]) -> str:
        """Format recommendations for calendar event body."""
        if not context_data.get("recommendations"):
            return ""

        recs = "\n".join(f"• {rec}" for rec in context_data["recommendations"])
        return f"Recommendations:\n{recs}"


from datetime import timedelta
