"""
Planning service for context-aware activity planning.

Analyzes user activities and enriches them with weather, traffic, and calendar context.
Fetches data on-demand without caching.
"""

import logging
import re
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from core.weather_service import WeatherService
from core.traffic_service import TrafficService


class PlanningService:
    """Service for context-aware planning and activity enrichment."""

    def __init__(self, memory_store):
        """
        Initialize planning service.

        Args:
            memory_store: MemoryStore instance for accessing user data and preferences
        """
        self.memory = memory_store
        self.logger = logging.getLogger(__name__)

    def analyze_activity(self, user_text: str, session_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Analyze user text to detect planning intent and extract details.

        Args:
            user_text: User's message text
            session_id: Current session ID
            user_id: User ID

        Returns:
            Activity data dict or None if no planning intent detected

        Example response:
            {
                "has_planning_intent": True,
                "activity_type": "shopping",
                "location": "Westfield London",
                "time": "2024-01-15T14:00:00",
                "needs_weather": True,
                "needs_traffic": True,
                "needs_calendar_check": True
            }
        """
        text_lower = user_text.lower()

        # Check for planning keywords
        planning_keywords = [
            "going", "planning to", "want to", "need to", "will be",
            "meeting", "appointment", "shopping", "visit", "heading to",
            "tomorrow", "later", "this afternoon", "tonight"
        ]

        has_planning_intent = any(keyword in text_lower for keyword in planning_keywords)

        if not has_planning_intent:
            return None

        # Extract activity details
        location = self._extract_location(user_text)
        time_info = self._extract_time(user_text)
        activity_type = self._extract_activity_type(user_text)

        if not location and not time_info:
            self.logger.info("[PLANNING] Planning keywords detected but no location/time found")
            return None

        activity_data = {
            "has_planning_intent": True,
            "activity_type": activity_type,
            "location": location,
            "time": time_info,
            "needs_weather": location is not None,
            "needs_traffic": location is not None,
            "needs_calendar_check": time_info is not None,
            "original_text": user_text
        }

        self.logger.info(f"[PLANNING] Detected planning intent: {activity_type} at {location} on {time_info}")
        return activity_data

    def get_context_for_activity(self, activity_data: Dict[str, Any], user_id: str) -> Dict[str, Any]:
        """
        Fetch weather, traffic, and calendar context for an activity.

        Args:
            activity_data: Activity data from analyze_activity()
            user_id: User ID

        Returns:
            Enriched context dict

        Example response:
            {
                "weather": {...},
                "traffic": {...},
                "calendar_conflicts": [...],
                "recommendations": ["Bring an umbrella", "Allow extra 15 minutes for traffic"]
            }
        """
        context = {
            "weather": None,
            "traffic": None,
            "calendar_conflicts": [],
            "recommendations": []
        }

        # Fetch weather if needed
        if activity_data.get("needs_weather") and activity_data.get("location"):
            weather_data = self._fetch_weather(activity_data["location"], user_id)
            if weather_data:
                context["weather"] = weather_data
                # Add recommendations based on weather
                if "rain" in weather_data.get("description", "").lower():
                    context["recommendations"].append("Bring an umbrella - rain expected")
                temp = weather_data.get("temperature", 0)
                if temp < 5:
                    context["recommendations"].append("Dress warmly - cold weather expected")

        # Fetch traffic if needed
        if activity_data.get("needs_traffic") and activity_data.get("location"):
            traffic_data = self._fetch_traffic(activity_data, user_id)
            if traffic_data:
                context["traffic"] = traffic_data
                # Add recommendations based on traffic
                delay = traffic_data.get("traffic_delay_minutes", 0)
                if delay > 10:
                    context["recommendations"].append(
                        f"Heavy traffic - allow extra {int(delay)} minutes"
                    )

        # Check calendar conflicts if needed
        if activity_data.get("needs_calendar_check") and activity_data.get("time"):
            conflicts = self._check_calendar_conflicts(activity_data["time"], user_id)
            if conflicts:
                context["calendar_conflicts"] = conflicts
                context["recommendations"].append(
                    f"Calendar conflict: {len(conflicts)} event(s) at this time"
                )

        return context

    def enrich_calendar_view(self, calendar_events: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """
        Enrich calendar events with weather and traffic data.

        Args:
            calendar_events: List of calendar event dicts
            user_id: User ID

        Returns:
            Enriched calendar events with weather/traffic badges
        """
        enriched_events = []

        for event in calendar_events:
            enriched_event = event.copy()

            # Extract location from event
            location = event.get("location")
            start_time = event.get("start")

            if location and start_time:
                # Fetch weather for event location/time
                weather_data = self._fetch_weather(location, user_id)
                if weather_data:
                    enriched_event["weather"] = {
                        "temperature": weather_data.get("temperature"),
                        "description": weather_data.get("description"),
                        "icon": self._get_weather_icon(weather_data.get("description", ""))
                    }

                # Fetch traffic for event location
                # Note: Would need user's current location - simplified for now
                # traffic_data = self._fetch_traffic_to_event(location, start_time, user_id)

            enriched_events.append(enriched_event)

        return enriched_events

    def _extract_location(self, text: str) -> Optional[str]:
        """Extract location from user text."""
        # Time words to exclude from locations
        time_words = ["tomorrow", "today", "tonight", "morning", "afternoon", "evening", "later", "at", "pm", "am"]

        # Pattern: "at X", "to X", "in X"
        # Match capitalized location names (1-4 words)
        patterns = [
            # Specific endings like "London", "Mall", etc.
            r"(?:at|to|in)\s+([A-Z][A-Za-z\s]+(?:London|Mall|Center|Centre|Street|Avenue|Road|Oaks))",
            # General pattern: capture 1-4 capitalized words after at/to/in
            r"(?:at|to|in)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                location = match.group(1).strip()
                # Filter out time words and very short matches
                if location.lower() not in time_words and len(location) > 2:
                    return location

        return None

    def _extract_time(self, text: str) -> Optional[str]:
        """Extract time from user text."""
        text_lower = text.lower()
        now = datetime.utcnow()

        # Tomorrow
        if "tomorrow" in text_lower:
            tomorrow = now + timedelta(days=1)
            # Try to extract hour
            hour_match = re.search(r"(\d{1,2})\s*(?:am|pm|:00)", text_lower)
            if hour_match:
                hour = int(hour_match.group(1))
                if "pm" in text_lower and hour < 12:
                    hour += 12
                return tomorrow.replace(hour=hour, minute=0, second=0).isoformat()
            # Default to 2pm tomorrow
            return tomorrow.replace(hour=14, minute=0, second=0).isoformat()

        # Today/tonight/this afternoon
        if any(word in text_lower for word in ["today", "tonight", "this afternoon"]):
            if "tonight" in text_lower:
                return now.replace(hour=19, minute=0, second=0).isoformat()
            if "afternoon" in text_lower:
                return now.replace(hour=14, minute=0, second=0).isoformat()
            if "today" in text_lower:
                # Default to current time + 1 hour for "today"
                return (now + timedelta(hours=1)).replace(minute=0, second=0).isoformat()

        # Specific time patterns
        time_match = re.search(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text_lower)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            period = time_match.group(3)

            if period == "pm" and hour < 12:
                hour += 12
            elif period == "am" and hour == 12:
                hour = 0

            return now.replace(hour=hour, minute=minute, second=0).isoformat()

        return None

    def _extract_activity_type(self, text: str) -> str:
        """Extract activity type from user text."""
        text_lower = text.lower()

        activity_keywords = {
            "shopping": ["shopping", "shop", "buy", "mall"],
            "meeting": ["meeting", "appointment", "call"],
            "dining": ["dinner", "lunch", "breakfast", "eat"],
            "travel": ["flight", "train", "drive"],
            "event": ["concert", "show", "game", "event"],
        }

        for activity_type, keywords in activity_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return activity_type

        return "activity"

    def _fetch_weather(self, location: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch weather data for location."""
        try:
            prefs = self.memory.get_all(str(user_id))
            api_key = prefs.get("feature_provider_openweather_api_key")

            if not api_key:
                self.logger.warning("[PLANNING] OpenWeather API key not configured")
                return None

            weather_service = WeatherService(api_key)
            return weather_service.get_weather(location)

        except Exception as e:
            self.logger.error(f"[PLANNING] Failed to fetch weather: {e}")
            return None

    def _fetch_traffic(self, activity_data: Dict[str, Any], user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch traffic data for activity."""
        try:
            prefs = self.memory.get_all(str(user_id))
            api_key = prefs.get("feature_provider_here_api_key")

            if not api_key:
                self.logger.warning("[PLANNING] HERE API key not configured")
                return None

            # Get origin from user's home or work location
            origin = None
            home_location = prefs.get("home location")
            work_location = prefs.get("work location")

            # Use home location as default, fall back to work if home not set
            if home_location:
                origin = home_location
                self.logger.info(f"[PLANNING] Using home location as origin: {origin}")
            elif work_location:
                origin = work_location
                self.logger.info(f"[PLANNING] Using work location as origin: {origin}")
            else:
                # Fallback to Liverpool center if no location set
                origin = "53.4084,-2.9916"
                self.logger.warning("[PLANNING] No home/work location set, using Liverpool default")

            destination = activity_data.get("location")

            if not destination:
                return None

            traffic_service = TrafficService(api_key)
            departure_time = None
            if activity_data.get("time"):
                departure_time = datetime.fromisoformat(activity_data["time"])

            return traffic_service.get_traffic_estimate(
                origin=origin,
                destination=destination,
                departure_time=departure_time
            )

        except Exception as e:
            self.logger.error(f"[PLANNING] Failed to fetch traffic: {e}")
            return None

    def _check_calendar_conflicts(self, time_str: str, user_id: str) -> List[Dict[str, Any]]:
        """Check for calendar conflicts at specified time."""
        try:
            # Get M365 provider if available
            from actions.m365_provider import M365Provider

            creds = self.memory.get_m365_credentials(int(user_id))
            if not creds:
                self.logger.info("[PLANNING] M365 not connected, skipping calendar check")
                return []

            provider = M365Provider(
                access_token=creds["access_token"],
                refresh_token=creds["refresh_token"],
                expires_at=creds["expires_at"],
                user_id=int(user_id),
                memory_store=self.memory
            )

            # Get events for the day
            target_time = datetime.fromisoformat(time_str)
            start_of_day = target_time.replace(hour=0, minute=0, second=0)
            end_of_day = target_time.replace(hour=23, minute=59, second=59)

            events = provider.list_calendar_events(
                start_time=start_of_day.isoformat(),
                end_time=end_of_day.isoformat()
            )

            # Check for conflicts (events within 1 hour of target time)
            conflicts = []
            for event in events:
                event_start = datetime.fromisoformat(event["start"].replace("Z", "+00:00"))
                time_diff = abs((event_start - target_time).total_seconds() / 60)

                if time_diff < 60:  # Within 1 hour
                    conflicts.append({
                        "subject": event.get("subject"),
                        "start": event.get("start"),
                        "end": event.get("end"),
                        "time_diff_minutes": int(time_diff)
                    })

            return conflicts

        except Exception as e:
            self.logger.error(f"[PLANNING] Failed to check calendar: {e}")
            return []

    def _get_weather_icon(self, description: str) -> str:
        """Get emoji icon for weather description."""
        description_lower = description.lower()

        if "clear" in description_lower or "sunny" in description_lower:
            return "☀️"
        elif "cloud" in description_lower:
            return "☁️"
        elif "rain" in description_lower:
            return "🌧️"
        elif "snow" in description_lower:
            return "❄️"
        elif "storm" in description_lower or "thunder" in description_lower:
            return "⛈️"
        else:
            return "🌤️"
