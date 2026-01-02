"""
Calendar action handlers.

Provides handlers for calendar-related actions:
- Reading calendar events
- Booking appointments
- Updating appointments
- Cancelling appointments
- External service booking assistance
"""

from typing import Dict, Any, List
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from datetime import datetime, timedelta
import logging
import re


def get_provider_company_name(provider_type: str) -> str:
    """
    Map provider type to company display name.

    Args:
        provider_type: Provider type (e.g., 'openai', 'anthropic', 'google', etc.)

    Returns:
        Company display name (e.g., 'OpenAI', 'Anthropic', 'Google', etc.')
    """
    company_mapping = {
        "openai": "OpenAI",
        "anthropic": "Anthropic",
        "google": "Google",
        "mistral": "Mistral",
        "grok": "xAI",
        "xai": "xAI",
    }
    return company_mapping.get(provider_type.lower(), provider_type.capitalize())

from .base_handler import BaseActionHandler
from .helpers import (
    parse_date_range,
    format_date_range,
    format_event_list,
    extract_event_with_llm,
    detect_service_category,
    find_optimal_slots,
    format_free_slots,
    parse_m365_datetime
)


class CalendarHandlers(BaseActionHandler):
    """Handlers for calendar-related actions."""

    def __init__(self, action_registry, memory_store, confirmation_manager=None):
        """Initialize calendar handlers."""
        super().__init__(action_registry, memory_store, confirmation_manager)
        self.logger = logging.getLogger(__name__)

    def handle_read_calendar(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle calendar reading requests.

        Examples:
        - "What's on my calendar Tuesday?"
        - "Am I free tomorrow afternoon?"
        - "Show me my schedule for next week"
        - "When is my flight?"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with calendar events
        """
        # Check if this is a flight/travel specific query
        user_text_lower = user_text.lower()
        is_flight_query = any(keyword in user_text_lower for keyword in ["flight", "train", "travel", "trip"])

        # Parse the request to extract date range
        date_range = parse_date_range(user_text)

        # For flight queries without specific dates, search next 3 months
        if not date_range and is_flight_query:
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=90)  # 3 months
        elif not date_range:
            return self._format_success_response(
                "I can check your calendar. Which dates would you like me to check? (e.g., 'this Tuesday', 'next week')",
                "read_calendar"
            )
        else:
            start_date, end_date = date_range

        # Get provider
        provider_result = self._get_provider("read_calendar", user_id)
        if not provider_result:
            return self._format_no_provider_response("read_calendar", "read_calendar", "calendar")

        provider_id, provider = provider_result

        # Execute read (no confirmation needed for read operations)
        try:
            events = provider.read_calendar(start_date, end_date)

            # Filter out past events - only show future events
            now = datetime.now()
            future_events = [
                e for e in events
                if e.get("start_time") and datetime.fromisoformat(
                    re.sub(r'\.(\d{6})\d+', r'.\1', e["start_time"]).replace("Z", "+00:00")
                ) > now
            ]

            # Enrich events with weather data
            try:
                from core.planning_service import PlanningService
                planning_service = PlanningService(self.memory)
                future_events = planning_service.enrich_calendar_view(future_events, str(user_id))
            except Exception as e:
                # If enrichment fails, continue without it
                self.logger.warning(f"[CALENDAR] Failed to enrich calendar: {e}")

            # If this is a flight query, filter to flight/travel events
            if is_flight_query:
                flight_keywords = ["flight", "train", "travel", "trip", "departure", "arrival", "airline", "airport"]
                flight_events = [
                    e for e in future_events
                    if any(keyword in e.get("subject", "").lower() for keyword in flight_keywords)
                ]

                if not flight_events:
                    response = "I couldn't find any flights or travel events in your calendar. If you have a booking confirmation, you can paste it and I'll add it to your calendar."
                elif len(flight_events) == 1:
                    event = flight_events[0]
                    response = f"Your flight is scheduled for:\n\n{format_event_list([event], show_date=True)}"
                else:
                    response = f"I found {len(flight_events)} upcoming flights/travel events:\n\n{format_event_list(flight_events, show_date=True)}"

                return {
                    "text": response,
                    "provider": "action_router",
                    "model": None,
                    "task_type": "read_calendar",
                    "metadata": {
                        "events_count": len(flight_events),
                        "date_range": [start_date.isoformat(), end_date.isoformat()],
                        "provider_id": provider_id,
                        "flight_query": True
                    }
                }

            # Format response for general calendar queries
            llm_provider_info = None  # Initialize to None for all cases

            if not future_events:
                date_str = format_date_range(start_date, end_date)
                response = f"You have no upcoming events {date_str}."
            else:
                # Check if this is a multi-day range (more than 1 day)
                is_multiday = (end_date - start_date).days > 1
                event_list = format_event_list(future_events, show_date=is_multiday)
                date_str = format_date_range(start_date, end_date)

                # Check if events have enrichment data (weather/traffic)
                has_enrichment = any(event.get("weather") or event.get("traffic") for event in future_events)

                if has_enrichment:
                    # Use LLM to generate friendly summary with enrichment context
                    response, llm_provider_info = self._generate_enriched_summary(
                        future_events, date_str, event_list, user_id
                    )
                else:
                    # Standard format without enrichment
                    response = f"Here are your upcoming events {date_str}:\n\n{event_list}"

            # Build response with appropriate provider attribution
            result = {
                "text": response,
                "metadata": {
                    "events_count": len(future_events),
                    "date_range": [start_date.isoformat(), end_date.isoformat()],
                    "provider_id": provider_id
                }
            }

            # If LLM was used for enrichment, attribute to the LLM provider
            if llm_provider_info:
                # Get the provider ID from llm_provider_info
                llm_provider_id = llm_provider_info.get("id", "")
                llm_model = llm_provider_info.get("model", "")

                # Look up the friendly provider name from the database
                provider_details = self.memory.get_provider(llm_provider_id)

                if provider_details:
                    friendly_name = provider_details.get("name", llm_provider_id)
                    provider_type = provider_details.get("type", "")
                else:
                    # Fallback if provider not found
                    friendly_name = llm_provider_id
                    provider_type = llm_provider_info.get("type", "")

                # Map provider type to company name for display
                company_name = get_provider_company_name(provider_type)

                # Set response fields for frontend display
                result["provider"] = llm_provider_id
                result["model"] = llm_model
                result["task_type"] = "summarise_calendar"
                result["metadata"]["llm_provider_type"] = company_name
                result["metadata"]["llm_provider_name"] = friendly_name
            else:
                # Otherwise attribute to action router
                result["provider"] = "action_router"
                result["model"] = None
                result["task_type"] = "read_calendar"

            return result

        except Exception as e:
            self._log_error("handle_read_calendar", e)
            return self._format_error_response(
                f"I encountered an error reading your calendar: {str(e)}",
                "read_calendar",
                str(e)
            )

    def _generate_enriched_summary(
        self,
        events: List[Dict[str, Any]],
        date_str: str,
        event_list: str,
        user_id: int = None
    ) -> tuple:
        """
        Use LLM to generate friendly summary of calendar events with enrichment data.
        Uses user's routing preferences to select the appropriate provider.

        Args:
            events: List of calendar events with weather/traffic enrichment
            date_str: Formatted date range string
            event_list: Pre-formatted bulleted event list
            user_id: User ID for routing preferences lookup

        Returns:
            Tuple of (summary_text, provider_info) where provider_info is a dict with 'name', 'type', 'id', 'model'
            or (summary_text, None) if no provider used
        """
        from core.router import route_request

        # Build enrichment context for LLM
        enrichment_details = []
        for event in events:
            details = {
                "subject": event.get("subject"),
                "location": event.get("location"),
                "start_time": event.get("start_time")
            }

            if event.get("weather"):
                weather = event.get("weather")
                details["weather"] = {
                    "temperature": weather.get("temperature"),
                    "description": weather.get("description")
                }

            if event.get("traffic"):
                traffic = event.get("traffic")
                details["traffic"] = {
                    "duration_minutes": traffic.get("duration_minutes"),
                    "traffic_delay_minutes": traffic.get("traffic_delay_minutes")
                }

            enrichment_details.append(details)

        # Create prompt for LLM
        prompt = f"""Generate a friendly, conversational summary of the user's calendar events with contextual advice.

Events:
{event_list}

Enrichment data:
{enrichment_details}

Generate a natural, helpful response that:
1. Mentions what events they have
2. Highlights important weather details (cold temperatures, rain, etc.)
3. Mentions traffic issues if present
4. Gives practical advice (dress warmly, bring umbrella, allow extra time, etc.)

Keep it concise (2-3 sentences max) and conversational."""

        try:
            # Use route_request to respect user's routing preferences
            # IMPORTANT: Use a system message to prevent the LLM from triggering intent classification
            system_message = "You are a calendar assistant. Respond ONLY with a friendly summary of the events. Do not ask questions or include any conversational elements that might trigger actions."

            router_context = {
                "text": prompt,
                "session_id": "calendar_enrichment",
                "memory": self.memory,
                "user_id": str(user_id) if user_id else DEFAULT_USER_ID,
                "forced_provider": None,
                "force_intent": "system",  # Use system intent for internal summarization (prevents infinite loop)
                "system_message": system_message
            }

            result = route_request(router_context)
            summary_text = result.get("text", "").strip()

            # Extract provider info from result
            # route_request returns "provider" (not "provider_id")
            provider_id = result.get("provider")

            provider_info = {
                "id": provider_id,
                "name": provider_id,
                "type": provider_id.split("-")[0] if provider_id else "unknown",
                "model": result.get("model")
            }

            return summary_text, provider_info

        except Exception as e:
            self.logger.warning(f"[CALENDAR] Failed to generate enriched summary: {e}")
            # Fallback to standard format
            return f"Here are your upcoming events {date_str}:\n\n{event_list}", None

    def handle_book_appointment(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle appointment booking requests.

        This handles two scenarios:
        1. External service bookings (haircut, doctor, etc.) - provides smart context
        2. Direct calendar events - creates event with confirmation

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with booking assistance or confirmation
        """
        # Check if confirmation manager is available
        if not self.confirmation_manager:
            return self._format_error_response(
                "The confirmation system is not initialized. Please contact support.",
                "book_appointment"
            )

        # Detect if this is a service booking (haircut, doctor, dentist, etc.)
        service_category = detect_service_category(user_text)

        if service_category:
            # Handle service booking with smart context
            return self.handle_service_booking(user_text, user_id, session_id, service_category)

        # Use LLM to extract event details from natural language
        event_details = extract_event_with_llm(user_text, user_id, self.memory)

        if not event_details:
            return self._format_error_response(
                "I couldn't understand the event details. Please include the event subject and time (e.g., 'add lunch with Sean at 1pm today').",
                "book_appointment"
            )

        # Get provider
        provider_result = self._get_provider("create_calendar_event", user_id)
        if not provider_result:
            return self._format_no_provider_response("create_calendar_event", "book_appointment", "calendar")

        provider_id, provider = provider_result

        # Build action parameters for create_calendar_event
        # Note: datetime objects will be serialized to ISO strings by ConfirmationManager
        action_params = {
            "subject": event_details["subject"],
            "start_time": event_details["start_time"].isoformat(),
            "end_time": event_details["end_time"].isoformat(),
        }

        if event_details.get("location"):
            action_params["location"] = event_details["location"]

        if event_details.get("description"):
            action_params["description"] = event_details["description"]

        # Format confirmation message
        start_str = event_details["start_time"].strftime("%B %d at %I:%M %p").replace(" 0", " ")
        end_str = event_details["end_time"].strftime("%I:%M %p").replace(" 0", " ")

        confirmation_message = f"Add '{event_details['subject']}' to your calendar on {start_str} to {end_str}?"

        # Create confirmation request
        try:
            confirmation = self.confirmation_manager.create_confirmation(
                user_id=user_id,
                session_id=session_id,
                action_type="create_calendar_event",
                action_params=action_params,
                confirmation_message=confirmation_message,
                provider_id=provider_id,
                expires_in_hours=24
            )

            # Convert expires_at datetime to ISO string for JSON serialization
            expires_at = confirmation.get("expires_at")
            if expires_at and hasattr(expires_at, 'isoformat'):
                expires_at = expires_at.isoformat()

            return {
                "text": f"{confirmation_message}\n\nI've created a confirmation request.",
                "provider": "action_router",
                "model": None,
                "task_type": "book_appointment",
                "metadata": {
                    "confirmation_id": confirmation["confirmation_id"],
                    "action_id": confirmation["action_id"],
                    "requires_confirmation": True,
                    "confirmation_message": confirmation_message,
                    "expires_at": expires_at,
                    "action_type": "create_calendar_event",
                    "action_category": "calendar"
                }
            }

        except Exception as e:
            self._log_error("handle_book_appointment", e)
            return self._format_error_response(
                f"I encountered an error creating the confirmation: {str(e)}",
                "book_appointment",
                str(e)
            )

    def handle_update_appointment(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle appointment update/move requests.

        Examples:
        - "move lunch with Sean to 3pm"
        - "reschedule my 2pm meeting to tomorrow"
        - "change my haircut to 4pm"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with update result
        """
        # Get provider
        provider_result = self._get_provider("update_calendar_event", user_id)
        if not provider_result:
            return self._format_no_provider_response("update_calendar_event", "update_appointment", "calendar")

        provider_id, provider = provider_result

        # Get today's events to find the one to update
        now = datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        try:
            events = provider.read_calendar(start_of_day, end_of_day)

            # Search for matching event
            user_text_lower = user_text.lower()
            matching_event = None

            for event in events:
                subject = event.get("subject", "").lower()
                if any(word in user_text_lower for word in subject.split() if len(word) > 3):
                    matching_event = event
                    break

            if not matching_event:
                return self._format_error_response(
                    f"I couldn't find an event matching '{user_text}' in your calendar today. Can you be more specific?",
                    "update_appointment"
                )

            # Extract new time from user request
            time_match = re.search(r'to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', user_text_lower)
            if not time_match:
                return self._format_error_response(
                    f"I couldn't understand the new time. Please specify the time (e.g., 'move lunch to 3pm').",
                    "update_appointment"
                )

            hour = int(time_match.group(1))
            minute = int(time_match.group(2) or 0)
            meridiem = time_match.group(3)

            # Convert to 24-hour format
            if meridiem == 'pm' and hour != 12:
                hour += 12
            elif meridiem == 'am' and hour == 12:
                hour = 0
            elif not meridiem and hour < 12:
                hour += 12

            # Calculate new start and end times
            # M365 provider returns start_time/end_time as ISO strings
            from dateutil import parser as date_parser
            old_start = date_parser.isoparse(matching_event["start_time"])
            old_end = date_parser.isoparse(matching_event["end_time"])
            duration = old_end - old_start

            new_start = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            new_end = new_start + duration

            # Create confirmation request
            if not self.confirmation_manager:
                return self._format_error_response(
                    "The confirmation system is not initialized.",
                    "update_appointment"
                )

            start_str = new_start.strftime("%B %d at %I:%M %p").replace(" 0", " ")
            end_str = new_end.strftime("%I:%M %p").replace(" 0", " ")
            confirmation_message = f"Move '{matching_event['subject']}' to {start_str} to {end_str}?"

            confirmation = self.confirmation_manager.create_confirmation(
                user_id=user_id,
                session_id=session_id,
                action_type="update_calendar_event",
                action_params={
                    "event_id": matching_event["id"],
                    "updates": {
                        "start": {
                            "dateTime": new_start.isoformat(),
                            "timeZone": "UTC"
                        },
                        "end": {
                            "dateTime": new_end.isoformat(),
                            "timeZone": "UTC"
                        }
                    }
                },
                confirmation_message=confirmation_message,
                provider_id=provider_id,
                expires_in_hours=24
            )

            # Convert expires_at datetime to ISO string
            expires_at = confirmation.get("expires_at")
            if expires_at and hasattr(expires_at, 'isoformat'):
                expires_at = expires_at.isoformat()

            return {
                "text": f"{confirmation_message}\n\nI've created a confirmation request.",
                "provider": "action_router",
                "model": None,
                "task_type": "update_appointment",
                "metadata": {
                    "confirmation_id": confirmation["confirmation_id"],
                    "action_id": confirmation["action_id"],
                    "requires_confirmation": True,
                    "confirmation_message": confirmation_message,
                    "expires_at": expires_at,
                    "action_type": "update_calendar_event",
                    "action_category": "calendar"
                }
            }

        except Exception as e:
            self._log_error("handle_update_appointment", e)
            return self._format_error_response(
                f"I encountered an error: {str(e)}",
                "update_appointment",
                str(e)
            )

    def handle_cancel_appointment(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle appointment cancellation requests.

        Examples:
        - "cancel lunch with Sean today"
        - "delete my 2pm meeting"
        - "remove haircut appointment"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with cancellation result
        """
        # Get provider
        provider_result = self._get_provider("delete_calendar_event", user_id)
        if not provider_result:
            return self._format_no_provider_response("delete_calendar_event", "cancel_appointment", "calendar")

        provider_id, provider = provider_result

        # Parse temporal references from user text
        now = datetime.now()
        user_text_lower = user_text.lower()

        # Determine date range based on user input
        if "tomorrow" in user_text_lower:
            start_of_day = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)
        elif "next week" in user_text_lower:
            start_of_day = (now + timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=7)
        elif "this week" in user_text_lower or "week" in user_text_lower:
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=7)
        else:
            # Default to today
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day = start_of_day + timedelta(days=1)

        try:
            events = provider.read_calendar(start_of_day, end_of_day)

            # Search for matching event
            user_text_lower = user_text.lower()
            matching_event = None

            for event in events:
                subject = event.get("subject", "").lower()
                # Check if any words from the event subject are in the user's request
                if any(word in user_text_lower for word in subject.split() if len(word) > 3):
                    matching_event = event
                    break

            if not matching_event:
                time_desc = "today"
                if "tomorrow" in user_text_lower:
                    time_desc = "tomorrow"
                elif "week" in user_text_lower:
                    time_desc = "this week"

                return self._format_error_response(
                    f"I couldn't find an event matching '{user_text}' in your calendar {time_desc}. Can you be more specific?",
                    "cancel_appointment"
                )

            # Create confirmation request for deletion
            if not self.confirmation_manager:
                return self._format_error_response(
                    "The confirmation system is not initialized.",
                    "cancel_appointment"
                )

            confirmation_message = f"Delete '{matching_event['subject']}' from your calendar?"

            confirmation = self.confirmation_manager.create_confirmation(
                user_id=user_id,
                session_id=session_id,
                action_type="delete_calendar_event",
                action_params={"event_id": matching_event["id"]},
                confirmation_message=confirmation_message,
                provider_id=provider_id,
                expires_in_hours=24
            )

            # Convert expires_at datetime to ISO string
            expires_at = confirmation.get("expires_at")
            if expires_at and hasattr(expires_at, 'isoformat'):
                expires_at = expires_at.isoformat()

            return {
                "text": f"{confirmation_message}\n\nI've created a confirmation request.",
                "provider": "action_router",
                "model": None,
                "task_type": "cancel_appointment",
                "metadata": {
                    "confirmation_id": confirmation["confirmation_id"],
                    "action_id": confirmation["action_id"],
                    "requires_confirmation": True,
                    "confirmation_message": confirmation_message,
                    "expires_at": expires_at,
                    "action_type": "delete_calendar_event",
                    "action_category": "calendar"
                }
            }

        except Exception as e:
            self._log_error("handle_cancel_appointment", e)
            return self._format_error_response(
                f"I encountered an error: {str(e)}",
                "cancel_appointment",
                str(e)
            )

    def handle_service_booking(
        self,
        user_text: str,
        user_id: int,
        session_id: str,
        service_category: str
    ) -> Dict:
        """
        Handle external service booking with calendar-aware suggestions.

        Flow:
        1. Check for configured service provider
        2. Read user's calendar for availability
        3. Suggest optimal booking times
        4. Provide booking link/instructions

        Args:
            user_text: User's request
            user_id: User ID
            session_id: Session ID
            service_category: Type of service (haircut, doctor, etc.)

        Returns:
            Response with booking assistance
        """
        import json

        # Check for service provider
        service_provider = self.memory.get_preferred_provider(user_id, service_category)

        if not service_provider:
            # No provider configured - offer to set one up
            return {
                "text": f"I don't have a {service_category} provider configured yet. "
                       f"Would you like to add one in Settings → Service Providers?",
                "provider": "action_router",
                "model": None,
                "task_type": "book_appointment",
                "metadata": {
                    "service_category": service_category,
                    "needs_configuration": True
                }
            }

        # Get provider details
        provider_name = service_provider.get("name", f"{service_category} provider")
        booking_method = service_provider.get("booking_method", "manual")

        # Parse additional metadata if present
        additional_metadata = service_provider.get("additional_metadata")
        if isinstance(additional_metadata, str):
            try:
                additional_metadata = json.loads(additional_metadata)
            except:
                additional_metadata = {}
        elif not additional_metadata:
            additional_metadata = {}

        # Get typical duration and travel time
        typical_duration = additional_metadata.get("typical_duration_minutes", 30)
        travel_time_home = additional_metadata.get("travel_time_from_home", 15)
        travel_time_office = additional_metadata.get("travel_time_from_office", 15)
        booking_url = additional_metadata.get("booking_url", service_provider.get("api_base_url"))

        # Read calendar to find availability
        # Look ahead 2 weeks
        today = datetime.now()
        end_date = today + timedelta(days=14)

        # Load M365 provider to read calendar
        self.action_registry.load_providers(user_id)
        calendar_providers = self.action_registry.get_providers_by_capability("read_calendar", user_id)

        calendar_events = []
        if calendar_providers:
            provider_id, provider = calendar_providers[0]
            try:
                calendar_events = provider.read_calendar(today, end_date)
            except Exception as e:
                logging.warning(f"[CALENDAR_HANDLERS] Failed to read calendar: {e}")

        # Find free slots
        free_slots = find_optimal_slots(
            calendar_events,
            start_date=today,
            end_date=end_date,
            duration_minutes=typical_duration + travel_time_home
        )

        # Build response
        if free_slots:
            slots_text = format_free_slots(free_slots[:5])  # Top 5 slots

            response_text = f"I found some good times for your {service_category} at {provider_name}:\n\n"
            response_text += slots_text
            response_text += f"\n\n"

            if booking_url:
                response_text += f"**Book here:** {booking_url}\n\n"
            else:
                response_text += f"Contact {provider_name} to book.\n\n"

            response_text += "Would you like me to add a reminder to your calendar once you've booked?"
        else:
            response_text = f"Your calendar is quite full! "
            response_text += f"You may want to check {provider_name} directly for availability.\n\n"

            if booking_url:
                response_text += f"**Book here:** {booking_url}"

        return {
            "text": response_text,
            "provider": "action_router",
            "model": None,
            "task_type": "book_appointment",
            "metadata": {
                "service_category": service_category,
                "provider_name": provider_name,
                "booking_url": booking_url,
                "suggested_slots": [slot.isoformat() for slot in free_slots[:5]] if free_slots else []
            }
        }
