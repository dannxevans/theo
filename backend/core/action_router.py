"""
Action Router.

Routes action requests to appropriate action providers.
Handles the action planning and execution workflow.

This is distinct from the LLM router (router.py):
- LLM router: Routes text generation requests to AI models
- Action router: Routes action execution requests to service providers
"""

from typing import Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
import re


class ActionRouter:
    """
    Routes action requests to appropriate providers.

    Responsibilities:
    1. Parse user intent from natural language
    2. Identify required action(s)
    3. Find capable provider(s)
    4. Plan action execution
    5. Create confirmation request (for human-in-the-loop)
    6. Return plan to user

    Flow:
    User: "What's on my calendar Tuesday?"
      → ActionRouter.route_action_request()
      → _handle_read_calendar()
      → Parse date ("Tuesday")
      → Find M365 provider
      → Execute read_calendar()
      → Return formatted events
    """

    def __init__(self, action_registry, memory_store, confirmation_manager=None):
        """
        Initialize action router.

        Args:
            action_registry: ActionProviderRegistry instance
            memory_store: MemoryStore instance
            confirmation_manager: ConfirmationManager instance (optional, set later)
        """
        self.action_registry = action_registry
        self.memory = memory_store
        self.confirmation_manager = confirmation_manager

    def route_action_request(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for action routing.

        Args:
            context: Request context containing:
                - text: User input text
                - session_id: Session ID
                - user_id: User ID (from auth)
                - intent: Classified intent (e.g., "read_calendar")

        Returns:
            Response dictionary with:
                - text: Response to user
                - provider: Provider used ("action_router" or specific provider)
                - model: None (no LLM used)
                - task_type: Action type performed
                - metadata: Additional action metadata

        Example:
            >>> context = {
            ...     "text": "What's on my calendar tomorrow?",
            ...     "session_id": "session_123",
            ...     "user_id": 1,
            ...     "intent": "read_calendar"
            ... }
            >>> result = router.route_action_request(context)
            >>> print(result["text"])
            "You have 3 events tomorrow: Meeting at 9am, Lunch at 12pm, ..."
        """
        user_text = context.get("text", "")
        session_id = context.get("session_id")
        user_id = context.get("user_id", 1)  # Default to user 1 if not authenticated
        intent = context.get("intent")

        logging.info(f"[ACTION_ROUTER] Routing action request: {intent}")

        # Delegate to specific action handlers
        handlers = {
            "read_calendar": self._handle_read_calendar,
            "book_appointment": self._handle_book_appointment,
            "manage_email": self._handle_manage_email,
        }

        handler = handlers.get(intent)
        if not handler:
            return {
                "text": f"I understand you want to {intent}, but that action isn't implemented yet.",
                "provider": "action_router",
                "model": None,
                "task_type": intent,
            }

        return handler(user_text, session_id, user_id, context)

    # =============================
    # Calendar Actions
    # =============================

    def _handle_read_calendar(
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

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with calendar events
        """
        # Parse the request to extract date range
        date_range = self._parse_date_range(user_text)

        if not date_range:
            return {
                "text": "I can check your calendar. Which dates would you like me to check? (e.g., 'this Tuesday', 'next week')",
                "provider": "action_router",
                "task_type": "read_calendar",
            }

        start_date, end_date = date_range

        # Load providers for this user
        self.action_registry.load_providers(user_id)

        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("read_calendar", user_id)

        if not providers:
            return {
                "text": "I don't have access to your calendar yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "read_calendar",
                "metadata": {
                    "error": "no_provider",
                    "required_capability": "read_calendar"
                }
            }

        provider_id, provider = providers[0]

        # Execute read (no confirmation needed for read operations)
        try:
            events = provider.read_calendar(start_date, end_date)

            # Format response
            if not events:
                date_str = self._format_date_range(start_date, end_date)
                response = f"You have no events scheduled {date_str}."
            else:
                event_list = self._format_event_list(events)
                date_str = self._format_date_range(start_date, end_date)
                response = f"Here are your upcoming events {date_str}:\n\n{event_list}"

            return {
                "text": response,
                "provider": f"m365_calendar_{provider_id}",
                "task_type": "read_calendar",
                "metadata": {
                    "events_count": len(events),
                    "date_range": [start_date.isoformat(), end_date.isoformat()],
                    "provider_id": provider_id
                }
            }

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Calendar read failed: {e}")
            return {
                "text": f"I encountered an error reading your calendar: {str(e)}",
                "provider": "m365_calendar",
                "task_type": "read_calendar",
                "metadata": {
                    "error": str(e)
                }
            }

    def _handle_book_appointment(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle appointment booking requests.

        This follows the haircut booking example from requirements:
        1. Parse booking request (subject, time, attendees)
        2. Find calendar provider
        3. Create confirmation request for user approval
        4. Return confirmation details

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with confirmation request
        """
        # Check if confirmation manager is available
        if not self.confirmation_manager:
            return {
                "text": "The confirmation system is not initialized. Please contact support.",
                "provider": "action_router",
                "task_type": "book_appointment",
            }

        # Use LLM to extract event details from natural language
        event_details = self._extract_event_with_llm(user_text, user_id)

        if not event_details:
            return {
                "text": "I couldn't understand the event details. Please include the event subject and time (e.g., 'add lunch with Sean at 1pm today').",
                "provider": "action_router",
                "task_type": "book_appointment",
            }

        # Load providers for this user
        self.action_registry.load_providers(user_id)

        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("create_calendar_event", user_id)

        if not providers:
            return {
                "text": "I don't have access to your calendar yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "book_appointment",
                "metadata": {
                    "error": "no_provider",
                    "required_capability": "create_calendar_event"
                }
            }

        provider_id, provider = providers[0]

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
            logging.error(f"[ACTION_ROUTER] Failed to create confirmation: {e}")
            return {
                "text": f"I encountered an error creating the confirmation: {str(e)}",
                "provider": "action_router",
                "task_type": "book_appointment",
                "metadata": {
                    "error": str(e)
                }
            }

    def _handle_manage_email(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle email operations.

        Examples:
        - "Show me my unread emails"
        - "Draft an email to John about the project"
        - "Send that email"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with email operation result
        """
        # For now, return placeholder
        # TODO: Implement email operations in Phase 7
        return {
            "text": "Email management is under development and will be ready in Phase 7.",
            "provider": "action_router",
            "task_type": "manage_email",
        }

    # =============================
    # Event Parsing Helpers
    # =============================

    def _extract_event_with_llm(self, user_text: str, user_id: int) -> Optional[Dict]:
        """
        Use LLM to extract structured event details from natural language.

        Args:
            user_text: User's natural language request
            user_id: User ID for context

        Returns:
            Dictionary with parsed event details or None if extraction fails
        """
        from providers.openai import OpenAIProvider
        from core.provider_registry import ProviderRegistry
        import json

        # Get OpenAI provider for parsing
        try:
            registry = ProviderRegistry(self.memory)
            provider_cfg = registry.get_by_type("openai")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # Fallback to basic parsing if no LLM available
                logging.warning("[ACTION_ROUTER] No OpenAI provider available, using basic parsing")
                return self._parse_event_details(user_text)

            provider = OpenAIProvider(
                api_key=provider_cfg["api_key"],
                base_url=provider_cfg.get("base_url"),
                model=provider_cfg.get("model") or "gpt-4o-mini"
            )

            # Construct extraction prompt
            system_prompt = """You are a calendar event parser. Extract structured event information from user requests.

Return ONLY a JSON object with these fields:
- subject: Short, clear event title (e.g., "Lunch with Sean", "Team Meeting")
- start_time: ISO datetime string (e.g., "2025-12-27T13:00:00")
- end_time: ISO datetime string (1 hour after start if not specified)
- location: Optional location string
- description: Optional additional details

Rules:
1. Make the subject concise and professional
2. Use the current date/time as reference for relative times
3. Default duration is 1 hour unless specified
4. Return ONLY valid JSON, no other text"""

            current_time = datetime.now().isoformat()
            user_prompt = f"Current time: {current_time}\n\nUser request: {user_text}\n\nExtract event details as JSON:"

            response = provider.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Parse LLM response (OpenAI provider returns string directly)
            response_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

            # Try to extract JSON from response (LLM might add markdown code blocks)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            event_data = json.loads(response_text)

            # Convert ISO strings to datetime objects
            if "start_time" in event_data:
                event_data["start_time"] = datetime.fromisoformat(event_data["start_time"])
            if "end_time" in event_data:
                event_data["end_time"] = datetime.fromisoformat(event_data["end_time"])

            logging.info(f"[ACTION_ROUTER] LLM extracted event: {event_data.get('subject')}")
            return event_data

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] LLM extraction failed: {e}")
            # Fallback to basic parsing
            return self._parse_event_details(user_text)

    def _parse_event_details(self, text: str) -> Optional[Dict]:
        """
        Parse event details from natural language.

        Extracts:
        - subject: Event title/description
        - start_time: When the event starts
        - end_time: When the event ends (defaults to 1 hour after start)
        - location: Optional location

        Examples:
        - "add lunch with Sean at 1pm today"
          → {"subject": "lunch with Sean", "start_time": today@13:00, "end_time": today@14:00}
        - "schedule meeting tomorrow at 3pm for 2 hours"
          → {"subject": "meeting", "start_time": tomorrow@15:00, "end_time": tomorrow@17:00}

        Args:
            text: User input text

        Returns:
            Dictionary with event details or None if parsing fails
        """
        text_l = text.lower()
        now = datetime.now()

        # Parse time first
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text_l)
        if not time_match:
            # Try to find "at" followed by time words
            return None

        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)

        # Convert to 24-hour format
        if meridiem == 'pm' and hour != 12:
            hour += 12
        elif meridiem == 'am' and hour == 12:
            hour = 0
        elif not meridiem and hour < 12:
            # Assume PM for times like "1:00" without AM/PM
            hour += 12

        # Parse date (today, tomorrow, specific day)
        date_base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        if "tomorrow" in text_l:
            date_base = date_base + timedelta(days=1)
        elif "today" not in text_l:
            # Check for day of week
            days_of_week = {
                "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                "friday": 4, "saturday": 5, "sunday": 6
            }
            for day_name, day_num in days_of_week.items():
                if day_name in text_l:
                    days_ahead = day_num - now.weekday()
                    if days_ahead <= 0:
                        days_ahead += 7
                    date_base = date_base + timedelta(days=days_ahead)
                    break

        start_time = date_base

        # Parse duration (defaults to 1 hour)
        duration_hours = 1
        duration_match = re.search(r'for (\d+)\s*(hour|hr)', text_l)
        if duration_match:
            duration_hours = int(duration_match.group(1))

        end_time = start_time + timedelta(hours=duration_hours)

        # Parse subject - extract text before time indicators
        # Remove common action words
        subject_text = text
        for pattern in ['add', 'create', 'schedule', 'book', 'set up', 'make an?']:
            subject_text = re.sub(f'\\b{pattern}\\b', '', subject_text, flags=re.IGNORECASE)

        # Remove time references
        subject_text = re.sub(r'\bat\s+\d{1,2}(?::\d{2})?\s*(am|pm)?', '', subject_text, flags=re.IGNORECASE)
        subject_text = re.sub(r'\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', '', subject_text, flags=re.IGNORECASE)
        subject_text = re.sub(r'\bto my calendar\b', '', subject_text, flags=re.IGNORECASE)
        subject_text = re.sub(r'\bfor \d+\s*(hour|hr)s?\b', '', subject_text, flags=re.IGNORECASE)

        # Clean up whitespace
        subject = ' '.join(subject_text.split()).strip()

        if not subject:
            subject = "Event"

        return {
            "subject": subject,
            "start_time": start_time,
            "end_time": end_time,
        }

    # =============================
    # Date Parsing Helpers
    # =============================

    def _parse_date_range(self, text: str) -> Optional[Tuple[datetime, datetime]]:
        """
        Parse natural language date references.

        Supported formats:
        - "tomorrow"
        - "this Tuesday", "next Tuesday"
        - "this week", "next week"
        - "today"
        - "Monday", "Tuesday", etc.

        Args:
            text: User input text

        Returns:
            Tuple of (start_date, end_date) or None if no date found

        Examples:
            >>> router = ActionRouter(...)
            >>> start, end = router._parse_date_range("What's on Tuesday?")
            >>> print(start.strftime("%A"))
            "Tuesday"
        """
        text_l = text.lower()
        now = datetime.now()

        # "today"
        if "today" in text_l:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59)
            return (start, end)

        # "tomorrow"
        if "tomorrow" in text_l:
            tomorrow = now + timedelta(days=1)
            start = tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start.replace(hour=23, minute=59, second=59)
            return (start, end)

        # Day of week (Monday, Tuesday, etc.)
        days_of_week = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6
        }

        for day_name, day_num in days_of_week.items():
            if day_name in text_l:
                # Calculate next occurrence of this day
                days_ahead = day_num - now.weekday()
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7

                # Check for "next" modifier
                if "next" in text_l:
                    days_ahead += 7

                target_date = now + timedelta(days=days_ahead)
                start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end = start.replace(hour=23, minute=59, second=59)
                return (start, end)

        # "this week"
        if "this week" in text_l:
            # Monday to Sunday of current week
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return (start, end)

        # "next week"
        if "next week" in text_l:
            # Monday to Sunday of next week
            start = now - timedelta(days=now.weekday()) + timedelta(weeks=1)
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
            return (start, end)

        # Default: next 7 days
        start = now
        end = now + timedelta(days=7)
        return (start, end)

    def _format_date_range(self, start_date: datetime, end_date: datetime) -> str:
        """
        Format date range for human-readable output.

        Args:
            start_date: Start of range
            end_date: End of range

        Returns:
            Formatted string like "on Tuesday, Dec 26" or "from Dec 26-28"

        Examples:
            >>> start = datetime(2025, 12, 26)
            >>> end = datetime(2025, 12, 26, 23, 59, 59)
            >>> print(router._format_date_range(start, end))
            "on Friday, December 26"
        """
        # Same day
        if start_date.date() == end_date.date():
            return f"on {start_date.strftime('%A, %B %d')}"

        # Multiple days in same month
        if start_date.month == end_date.month:
            return f"from {start_date.strftime('%B %d')} to {end_date.strftime('%d')}"

        # Different months
        return f"from {start_date.strftime('%B %d')} to {end_date.strftime('%B %d')}"

    def _format_event_list(self, events: list) -> str:
        """
        Format a list of events for display.

        Args:
            events: List of event dictionaries

        Returns:
            Formatted string with event details

        Example:
            >>> events = [
            ...     {"subject": "Meeting", "start_time": "2025-12-26T09:00:00", "location": "Office"}
            ... ]
            >>> print(router._format_event_list(events))
            "• Meeting\n  9:00 AM • Office"
        """
        formatted = []

        for event in events:
            # Parse start time
            start_time_str = event.get("start_time", "")
            try:
                start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
                time_str = start_time.strftime("%I:%M %p").lstrip("0")
            except:
                time_str = "Time TBD"

            # Build event line
            subject = event.get("subject", "Untitled Event")
            location = event.get("location")

            event_line = f"• **{subject}**"
            details = []

            if time_str != "Time TBD":
                details.append(time_str)

            if location:
                details.append(location)

            if details:
                event_line += f"\n  {' • '.join(details)}"

            # Add attendees if present
            attendees = event.get("attendees", [])
            if attendees and len(attendees) > 0:
                attendee_count = len(attendees)
                event_line += f"\n  {attendee_count} attendee{'s' if attendee_count > 1 else ''}"

            formatted.append(event_line)

        return "\n\n".join(formatted)
