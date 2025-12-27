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
            "update_appointment": self._handle_update_appointment,
            "cancel_appointment": self._handle_cancel_appointment,
            "read_email": self._handle_read_email,
            "compose_email": self._handle_compose_email,
            "approve_confirmation": self._handle_approve_confirmation,
            "reject_confirmation": self._handle_reject_confirmation,
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
        date_range = self._parse_date_range(user_text)

        # For flight queries without specific dates, search next 3 months
        if not date_range and is_flight_query:
            from datetime import datetime, timedelta
            start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=90)  # 3 months
        elif not date_range:
            return {
                "text": "I can check your calendar. Which dates would you like me to check? (e.g., 'this Tuesday', 'next week')",
                "provider": "action_router",
                "task_type": "read_calendar",
            }
        else:
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

            # Filter out past events - only show future events
            from datetime import datetime
            now = datetime.now()
            future_events = [
                e for e in events
                if e.get("start_time") and datetime.fromisoformat(
                    re.sub(r'\.(\d{6})\d+', r'.\1', e["start_time"]).replace("Z", "+00:00")
                ) > now
            ]

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
                    response = f"Your flight is scheduled for:\n\n{self._format_event_list([event], show_date=True)}"
                else:
                    response = f"I found {len(flight_events)} upcoming flights/travel events:\n\n{self._format_event_list(flight_events, show_date=True)}"

                return {
                    "text": response,
                    "provider": "action_router",
                    "task_type": "read_calendar",
                    "metadata": {
                        "events_count": len(flight_events),
                        "date_range": [start_date.isoformat(), end_date.isoformat()],
                        "provider_id": provider_id,
                        "flight_query": True
                    }
                }

            # Format response for general calendar queries
            if not future_events:
                date_str = self._format_date_range(start_date, end_date)
                response = f"You have no upcoming events {date_str}."
            else:
                # Check if this is a multi-day range (more than 1 day)
                is_multiday = (end_date - start_date).days > 1
                event_list = self._format_event_list(future_events, show_date=is_multiday)
                date_str = self._format_date_range(start_date, end_date)
                response = f"Here are your upcoming events {date_str}:\n\n{event_list}"

            return {
                "text": response,
                "provider": "action_router",
                "task_type": "read_calendar",
                "metadata": {
                    "events_count": len(future_events),
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
            return {
                "text": "The confirmation system is not initialized. Please contact support.",
                "provider": "action_router",
                "task_type": "book_appointment",
            }

        # Detect if this is a service booking (haircut, doctor, dentist, etc.)
        service_category = self._detect_service_category(user_text)

        if service_category:
            # Handle service booking with smart context
            return self._handle_service_booking(user_text, user_id, session_id, service_category)

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

    def _handle_update_appointment(
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
        # Load providers for this user
        self.action_registry.load_providers(user_id)

        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("update_calendar_event", user_id)

        if not providers:
            return {
                "text": "I don't have access to your calendar yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "update_appointment",
            }

        provider_id, provider = providers[0]

        # Get today's events to find the one to update
        from datetime import datetime, timedelta
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
                return {
                    "text": f"I couldn't find an event matching '{user_text}' in your calendar today. Can you be more specific?",
                    "provider": "action_router",
                    "task_type": "update_appointment",
                }

            # Extract new time from user request
            import re
            time_match = re.search(r'to\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', user_text_lower)
            if not time_match:
                return {
                    "text": f"I couldn't understand the new time. Please specify the time (e.g., 'move lunch to 3pm').",
                    "provider": "action_router",
                    "task_type": "update_appointment",
                }

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
                return {
                    "text": "The confirmation system is not initialized.",
                    "provider": "action_router",
                    "task_type": "update_appointment",
                }

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
            logging.error(f"[ACTION_ROUTER] Failed to update appointment: {e}")
            return {
                "text": f"I encountered an error: {str(e)}",
                "provider": "action_router",
                "task_type": "update_appointment",
            }

    def _handle_cancel_appointment(
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
        # Load providers for this user
        self.action_registry.load_providers(user_id)

        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("delete_calendar_event", user_id)

        if not providers:
            return {
                "text": "I don't have access to your calendar yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "cancel_appointment",
            }

        provider_id, provider = providers[0]

        # Get today's events to find the one to cancel
        from datetime import datetime, timedelta
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
                # Check if any words from the event subject are in the user's request
                if any(word in user_text_lower for word in subject.split() if len(word) > 3):
                    matching_event = event
                    break

            if not matching_event:
                return {
                    "text": f"I couldn't find an event matching '{user_text}' in your calendar today. Can you be more specific?",
                    "provider": "action_router",
                    "task_type": "cancel_appointment",
                }

            # Create confirmation request for deletion
            if not self.confirmation_manager:
                return {
                    "text": "The confirmation system is not initialized.",
                    "provider": "action_router",
                    "task_type": "cancel_appointment",
                }

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
            logging.error(f"[ACTION_ROUTER] Failed to cancel appointment: {e}")
            return {
                "text": f"I encountered an error: {str(e)}",
                "provider": "action_router",
                "task_type": "cancel_appointment",
            }

    def _handle_read_email(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle email read operations.

        Examples:
        - "Show me my unread emails"
        - "unread email summary"
        - "check my inbox"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with email operation result
        """
        # Load providers for this user
        self.action_registry.load_providers(user_id)

        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("read_email", user_id)

        if not providers:
            return {
                "text": "I don't have access to your email yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "read_email",
                "metadata": {
                    "error": "no_provider",
                    "required_capability": "read_email"
                }
            }

        provider_id, provider = providers[0]

        # Determine if user wants to read a specific email or get a summary
        user_text_lower = user_text.lower()

        # Check if user wants to read a specific email (e.g., "read me the solicitors email")
        is_specific_email = any(keyword in user_text_lower for keyword in ["read me", "read the", "show me the", "open the"])

        try:
            # Fetch emails
            filter_unread = "unread" in user_text_lower

            if filter_unread:
                emails = provider.read_email(folder="inbox", top=20, filter_query="isRead eq false")
                logging.info(f"[ACTION_ROUTER] Fetched {len(emails)} unread emails with filter 'isRead eq false'")
            else:
                emails = provider.read_email(folder="inbox", top=50)
                logging.info(f"[ACTION_ROUTER] Fetched {len(emails)} emails (no filter)")

            if not emails:
                msg = "You have no unread emails." if filter_unread else "Your inbox is empty."
                return {
                    "text": msg,
                    "provider": "action_router",
                    "task_type": "read_email",
                    "metadata": {
                        "email_count": 0,
                        "filter_unread": filter_unread
                    }
                }

            # If user wants a specific email, search for it
            if is_specific_email:
                return self._read_specific_email(user_text, emails, user_id)

            # Otherwise, generate AI summary of emails
            summary = self._generate_email_summary(emails, user_id, filter_unread)

            return {
                "text": summary,
                "provider": "action_router",
                "task_type": "read_email",
                "metadata": {
                    "email_count": len(emails),
                    "filter_unread": filter_unread
                }
            }

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Email read failed: {e}")
            return {
                "text": f"I encountered an error reading your emails: {str(e)}",
                "provider": "action_router",
                "task_type": "read_email",
                "metadata": {
                    "error": str(e)
                }
            }

    def _read_specific_email(
        self,
        user_text: str,
        emails: list,
        user_id: int
    ) -> Dict:
        """
        Read a specific email based on user's description.

        Args:
            user_text: User's request (e.g., "read me the solicitors email")
            emails: List of email dictionaries to search
            user_id: User ID

        Returns:
            Response dictionary with email content
        """
        import re

        # Extract keywords from user request to find matching email
        user_text_lower = user_text.lower()

        # Remove common phrases to get the actual search terms
        # Use word boundaries to avoid removing parts of words
        import re
        search_text = user_text_lower

        # Remove action phrases at the beginning
        search_text = re.sub(r'\b(read me|read the|show me|show me the|open the|can you)\b', '', search_text)
        search_text = re.sub(r'\b(the|email|from)\b', '', search_text)
        search_text = search_text.strip()

        logging.info(f"[ACTION_ROUTER] Searching for specific email with keywords: '{search_text}'")

        # Search for matching email by subject, sender, or preview
        matching_email = None
        for email in emails:
            subject = email.get("subject", "").lower()
            sender = email.get("from", "").lower()
            preview = email.get("preview", "").lower()

            # Check if search terms appear in subject, sender, or preview
            if search_text in subject or search_text in sender or search_text in preview:
                matching_email = email
                break

            # Also check if individual words match (require at least 2 words to match)
            search_words = [w for w in search_text.split() if len(w) > 3]
            if len(search_words) >= 2:
                matches = sum(1 for word in search_words if word in subject or word in sender or word in preview)
                if matches >= 2:
                    matching_email = email
                    break
            elif search_words:
                # Single significant word - still check
                if any(word in subject or word in sender or word in preview for word in search_words):
                    matching_email = email
                    break

        if not matching_email:
            return {
                "text": f"I couldn't find an email matching '{search_text}'. Can you be more specific?",
                "provider": "action_router",
                "task_type": "read_email",
            }

        # Get the M365 provider to fetch full email body
        self.action_registry.load_providers(user_id)
        providers = self.action_registry.get_providers_by_capability("read_email", user_id)

        if not providers:
            return {
                "text": "Failed to access email provider.",
                "provider": "action_router",
                "task_type": "read_email",
            }

        provider_id, provider = providers[0]

        # Fetch full email body
        try:
            email_id = matching_email.get("id")
            body = provider.get_email_body(email_id)
        except Exception as e:
            logging.warning(f"[ACTION_ROUTER] Failed to fetch full email body: {e}")
            body = matching_email.get("preview", "No content available")

        # Format the email for display
        subject = matching_email.get("subject", "No subject")
        sender = matching_email.get("from", "Unknown")
        received = matching_email.get("received_at", "")

        response_text = f"**Email from {sender}**\n\n"
        response_text += f"**Subject:** {subject}\n\n"
        if received:
            response_text += f"**Received:** {received}\n\n"
        response_text += f"**Content:**\n{body}"

        return {
            "text": response_text,
            "provider": "action_router",
            "task_type": "read_email",
            "metadata": {
                "email_id": matching_email.get("id"),
                "subject": subject,
                "sender": sender
            }
        }

    def _handle_compose_email(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle email composition and reply operations.

        Examples:
        - "reply to the email 'this is a test' with details about my calendar"
        - "send an email to john@example.com about the meeting"
        - "draft an email to the team"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with compose/reply result
        """
        # Load providers for this user
        self.action_registry.load_providers(user_id)

        # Check if this is a reply or new email
        is_reply = "reply" in user_text.lower() or "respond" in user_text.lower()

        if is_reply:
            return self._handle_email_reply(user_text, session_id, user_id, context)
        else:
            return self._handle_email_send(user_text, session_id, user_id, context)

    def _handle_email_reply(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle replying to an email.

        Steps:
        1. Extract email subject/identifier from user text
        2. Search for matching email in inbox
        3. Generate reply body using LLM (with calendar context if requested)
        4. Create confirmation for sending reply
        """
        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("read_email", user_id)

        if not providers:
            return {
                "text": "I don't have access to your email yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "compose_email",
                "metadata": {
                    "error": "no_provider",
                    "required_capability": "reply_email"
                }
            }

        provider_id, provider = providers[0]

        # Extract email identifier (subject search)
        # Look for quoted text or "email about X" or "email from X"
        import re
        subject_match = re.search(r"['\"]([^'\"]+)['\"]", user_text)

        if not subject_match:
            return {
                "text": "I couldn't identify which email to reply to. Please specify the email subject in quotes (e.g., \"reply to 'this is a test'\").",
                "provider": "action_router",
                "task_type": "compose_email",
            }

        search_subject = subject_match.group(1)
        logging.info(f"[ACTION_ROUTER] Searching for email with subject: {search_subject}")

        try:
            # Read recent emails to find the one to reply to
            emails = provider.read_email(folder="inbox", top=50)

            # Find matching email by subject
            matching_email = None
            for email in emails:
                if search_subject.lower() in email.get("subject", "").lower():
                    matching_email = email
                    break

            if not matching_email:
                return {
                    "text": f"I couldn't find an email with subject containing '{search_subject}'. Please check the subject and try again.",
                    "provider": "action_router",
                    "task_type": "compose_email",
                }

            # Extract what to include in reply (e.g., "with details about my calendar")
            reply_context = user_text.lower()
            include_calendar = "calendar" in reply_context or "schedule" in reply_context

            # Generate reply body using LLM
            reply_body = self._generate_reply_body(
                user_text,
                matching_email,
                user_id,
                include_calendar
            )

            if not reply_body:
                return {
                    "text": "I couldn't generate a reply. Please try rephrasing your request.",
                    "provider": "action_router",
                    "task_type": "compose_email",
                }

            # Create confirmation for sending reply
            if not self.confirmation_manager:
                return {
                    "text": "The confirmation system is not initialized.",
                    "provider": "action_router",
                    "task_type": "compose_email",
                }

            confirmation_message = f"Reply to '{matching_email.get('subject')}' from {matching_email.get('from')}?"
            preview = reply_body[:200] + "..." if len(reply_body) > 200 else reply_body

            confirmation = self.confirmation_manager.create_confirmation(
                user_id=user_id,
                session_id=session_id,
                action_type="reply_email",
                action_params={
                    "email_id": matching_email["id"],
                    "body": reply_body,
                    "content_type": "HTML"
                },
                confirmation_message=f"{confirmation_message}\n\nPreview:\n{preview}",
                provider_id=provider_id,
                expires_in_hours=24
            )

            # Convert expires_at datetime to ISO string
            expires_at = confirmation.get("expires_at")
            if expires_at and hasattr(expires_at, 'isoformat'):
                expires_at = expires_at.isoformat()

            return {
                "text": f"{confirmation_message}\n\nPreview:\n{preview}\n\nI've created a confirmation request.",
                "provider": "action_router",
                "task_type": "compose_email",
                "metadata": {
                    "confirmation_id": confirmation["confirmation_id"],
                    "action_id": confirmation["action_id"],
                    "requires_confirmation": True,
                    "confirmation_message": confirmation_message,
                    "expires_at": expires_at,
                    "action_type": "reply_email",
                    "action_category": "email"
                }
            }

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Email reply failed: {e}")
            return {
                "text": f"I encountered an error preparing the reply: {str(e)}",
                "provider": "action_router",
                "task_type": "compose_email",
                "metadata": {
                    "error": str(e)
                }
            }

    def _handle_email_send(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle composing and sending a new email.

        Examples:
        - "send an email to john@example.com saying I'll be late"
        - "email danny@example.com about the meeting tomorrow"
        """
        # Find M365 provider
        providers = self.action_registry.get_providers_by_capability("send_email", user_id)

        if not providers:
            return {
                "text": "I don't have access to your email yet. Would you like to connect your Microsoft 365 account?",
                "provider": "action_router",
                "task_type": "compose_email",
                "metadata": {
                    "error": "no_provider",
                    "required_capability": "send_email"
                }
            }

        provider_id, provider = providers[0]

        # Extract recipient email address
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_matches = re.findall(email_pattern, user_text)

        # Also look for names in quotes or after "to"
        name_pattern = r'(?:to|email)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        name_matches = re.findall(name_pattern, user_text)

        recipient = None
        if email_matches:
            recipient = email_matches[0]
        elif name_matches:
            recipient_name = name_matches[0]

            # Check if user is referring to themselves
            user_name_fact = None
            try:
                facts = self.memory.get_facts(user_id)
                for fact in facts:
                    if fact.get("key", "").lower() in ["my name", "name"]:
                        user_name_fact = fact.get("value", "").lower()
                        break
            except:
                pass

            if user_name_fact and recipient_name.lower() == user_name_fact:
                # User wants to email themselves - get their M365 email
                try:
                    creds = self.memory.get_m365_credentials(user_id)
                    if creds and creds.get("user_principal_name"):
                        recipient = creds["user_principal_name"]
                        logging.info(f"[ACTION_ROUTER] Resolved self-reference '{recipient_name}' to {recipient}")
                except Exception as e:
                    logging.warning(f"[ACTION_ROUTER] Failed to get user's email: {e}")

            if not recipient:
                # Future enhancement: check M365 contacts/people API
                return {
                    "text": f"I found the name '{recipient_name}' but don't have their email address. Please provide the email address (e.g., '{recipient_name.lower().replace(' ', '.')}@example.com').",
                    "provider": "action_router",
                    "task_type": "compose_email",
                }

        if not recipient:
            return {
                "text": "I couldn't identify the recipient. Please specify an email address (e.g., 'send an email to john@example.com').",
                "provider": "action_router",
                "task_type": "compose_email",
            }

        # Generate email subject and body using LLM
        subject, body = self._generate_new_email_body(user_text, recipient, user_id)

        if not subject or not body:
            return {
                "text": "I couldn't generate the email content. Please try again or provide more details.",
                "provider": "action_router",
                "task_type": "compose_email",
            }

        # Create draft in M365 first
        try:
            draft_result = provider.draft_email(
                to=[recipient],
                subject=subject,
                body=body,
                content_type="HTML"
            )
            draft_id = draft_result.get("draft_id")
            logging.info(f"[ACTION_ROUTER] Created draft email {draft_id}")
        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Failed to create draft: {e}")
            return {
                "text": f"Failed to create email draft: {str(e)}",
                "provider": "action_router",
                "task_type": "compose_email",
            }

        # Create confirmation for sending the draft
        confirmation_result = self.confirmation_manager.create_confirmation(
            user_id=user_id,
            session_id=session_id,
            action_type="send_draft_email",
            provider_id=provider_id,
            action_params={
                "draft_id": draft_id
            },
            confirmation_message=f"Send email '{subject}' to {recipient}?"
        )

        if not confirmation_result:
            return {
                "text": "Failed to create confirmation for email.",
                "provider": "action_router",
                "task_type": "compose_email",
            }

        # Extract just the integer ID for JSON serialization
        confirmation_id = confirmation_result["confirmation_id"]

        # Strip HTML for preview display
        body_preview = body.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
        import re
        body_preview = re.sub('<[^<]+?>', '', body_preview)

        # Return confirmation request with metadata for UI widget
        return {
            "text": f"**Draft email to {recipient}:**\n\n**Subject:** {subject}\n\n**Message:**\n{body_preview}\n\n",
            "provider": "action_router",
            "task_type": "compose_email",
            "metadata": {
                "requires_confirmation": True,
                "confirmation_id": confirmation_id,
                "recipient": recipient,
                "subject": subject,
                "draft_id": draft_id,
                "action_category": "email",
                "confirmation_message": f"Send email '{subject}' to {recipient}?"
            }
        }

    def _generate_reply_body(
        self,
        user_request: str,
        original_email: Dict,
        user_id: int,
        include_calendar: bool = False
    ) -> str:
        """
        Generate email reply body using LLM.

        Args:
            user_request: Original user request
            original_email: Email being replied to
            user_id: User ID
            include_calendar: Whether to include calendar information

        Returns:
            Generated reply body (HTML)
        """
        from providers.openai import OpenAIProvider
        from core.provider_registry import ProviderRegistry

        try:
            # Get OpenAI provider
            registry = ProviderRegistry(self.memory)
            provider_cfg = registry.get_by_type("openai")

            if not provider_cfg or not provider_cfg.get("api_key"):
                logging.warning("[ACTION_ROUTER] No OpenAI provider available for email generation")
                return None

            provider = OpenAIProvider(
                api_key=provider_cfg["api_key"],
                base_url=provider_cfg.get("base_url"),
                model=provider_cfg.get("model") or "gpt-4o-mini"
            )

            # Get user's name from memory facts
            user_name = None
            try:
                facts = self.memory.get_facts(user_id)
                for fact in facts:
                    if fact.get("key", "").lower() in ["my name", "name"]:
                        user_name = fact.get("value")
                        logging.info(f"[ACTION_ROUTER] Found user name in facts: {user_name}")
                        break
            except Exception as e:
                logging.warning(f"[ACTION_ROUTER] Failed to fetch user name from facts: {e}")

            # Build context
            context_parts = []

            # Add user's name if available
            if user_name:
                context_parts.append(f"User's name: {user_name}")

            # Add original email context
            context_parts.append(f"Original email from: {original_email.get('from')}")
            context_parts.append(f"Subject: {original_email.get('subject')}")
            context_parts.append(f"Preview: {original_email.get('preview', '')}")

            # Add calendar context if requested
            calendar_info = ""
            if include_calendar:
                # Get this week's calendar events
                from datetime import datetime, timedelta
                now = datetime.now()
                start_of_week = now - timedelta(days=now.weekday())
                end_of_week = start_of_week + timedelta(days=7)

                # Load providers and get calendar
                self.action_registry.load_providers(user_id)
                calendar_providers = self.action_registry.get_providers_by_capability("read_calendar", user_id)

                if calendar_providers:
                    _, cal_provider = calendar_providers[0]
                    try:
                        events = cal_provider.read_calendar(start_of_week, end_of_week)
                        # Filter future events
                        future_events = [
                            e for e in events
                            if e.get("start_time") and datetime.fromisoformat(
                                re.sub(r'\.(\d{6})\d+', r'.\1', e["start_time"]).replace("Z", "+00:00")
                            ) > now
                        ]

                        if future_events:
                            calendar_info = "\n\nUser's calendar this week:\n"
                            for event in future_events[:10]:  # Limit to 10 events
                                start_str = event.get("start_time", "")
                                if start_str:
                                    start_time = datetime.fromisoformat(
                                        re.sub(r'\.(\d{6})\d+', r'.\1', start_str).replace("Z", "+00:00")
                                    )
                                    day_date = start_time.strftime("%A, %B %d at %I:%M %p")
                                    calendar_info += f"- {event.get('subject')} on {day_date}\n"
                    except Exception as e:
                        logging.warning(f"[ACTION_ROUTER] Failed to fetch calendar for reply: {e}")

            context_text = "\n".join(context_parts) + calendar_info

            # Construct prompt
            system_prompt = """You are an email assistant helping the user compose a reply.

Generate a professional, friendly email reply based on the user's instructions.

Guidelines:
1. Be concise and professional
2. Use proper email formatting (greeting, body, closing)
3. If calendar information is provided, incorporate it naturally
4. Match the tone of the original email
5. Return ONLY the email body (no subject line)
6. Format as plain text (we'll convert to HTML)
7. IMPORTANT: If the user's name is provided, use it in the sign-off (e.g., "Best regards,\nDanny"). Never use placeholders like "[Your Name]"."""

            user_prompt = f"""User request: {user_request}

{context_text}

Generate a reply email body:"""

            response = provider.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            reply_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

            # Convert to simple HTML
            reply_html = reply_text.replace("\n", "<br>\n")

            logging.info(f"[ACTION_ROUTER] Generated reply body ({len(reply_html)} chars)")
            return reply_html

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Reply generation failed: {e}")
            return None

    def _generate_new_email_body(
        self,
        user_request: str,
        recipient: str,
        user_id: int
    ) -> tuple:
        """
        Generate new email subject and body using LLM.

        Args:
            user_request: Original user request
            recipient: Email recipient
            user_id: User ID

        Returns:
            Tuple of (subject, body_html) or (None, None) if generation fails
        """
        from providers.openai import OpenAIProvider
        from core.provider_registry import ProviderRegistry

        try:
            # Get OpenAI provider
            registry = ProviderRegistry(self.memory)
            provider_cfg = registry.get_by_type("openai")

            if not provider_cfg or not provider_cfg.get("api_key"):
                logging.warning("[ACTION_ROUTER] No OpenAI provider available for email generation")
                return None

            provider = OpenAIProvider(
                api_key=provider_cfg["api_key"],
                base_url=provider_cfg.get("base_url"),
                model=provider_cfg.get("model") or "gpt-4o-mini"
            )

            # Get user's name from memory facts
            user_name = None
            try:
                facts = self.memory.get_facts(user_id)
                for fact in facts:
                    if fact.get("key", "").lower() in ["my name", "name"]:
                        user_name = fact.get("value")
                        logging.info(f"[ACTION_ROUTER] Found user name in facts: {user_name}")
                        break
            except Exception as e:
                logging.warning(f"[ACTION_ROUTER] Failed to fetch user name from facts: {e}")

            # Build context
            context_parts = []

            # Add user's name if available
            if user_name:
                context_parts.append(f"Sender's name: {user_name}")

            context_parts.append(f"Recipient: {recipient}")

            context_text = "\n".join(context_parts)

            # Construct prompt
            system_prompt = """You are an email assistant helping the user compose a new email.

Generate a professional, friendly email based on the user's instructions.

Your response must be in this EXACT format:
SUBJECT: [concise subject line based on email content]
BODY:
[email body with greeting, content, and closing]

Guidelines:
1. Generate a concise, relevant subject line that summarizes the email content
2. Use proper email formatting (greeting, body, closing)
3. Match an appropriate tone for the context
4. Format as plain text (we'll convert to HTML)
5. CRITICAL: Always include the sender's name after the closing (e.g., "Best regards,\nDanny" NOT "Best regards,"). Never use placeholders like "[Your Name]", "Theo", or leave it blank."""

            # Build user prompt with explicit name instruction if available
            name_instruction = ""
            if user_name:
                name_instruction = f"\n\nIMPORTANT: The email MUST be signed with the sender's name: {user_name}"

            user_prompt = f"""User request: {user_request}

{context_text}{name_instruction}

Generate the email with subject and body:"""

            response = provider.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            response_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

            # Parse subject and body from response
            subject = None
            body = None

            import re
            subject_match = re.search(r'SUBJECT:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
            if subject_match:
                subject = subject_match.group(1).strip()

            body_match = re.search(r'BODY:\s*(.+)', response_text, re.IGNORECASE | re.DOTALL)
            if body_match:
                body = body_match.group(1).strip()

            if not subject or not body:
                logging.error(f"[ACTION_ROUTER] Failed to parse subject/body from LLM response")
                return None, None

            # Convert to simple HTML
            body_html = body.replace("\n", "<br>\n")

            logging.info(f"[ACTION_ROUTER] Generated email: subject='{subject}' body=({len(body_html)} chars)")
            return subject, body_html

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Email generation failed: {e}")
            return None, None

    def _generate_email_summary(self, emails: list, user_id: int, unread_only: bool = False) -> str:
        """
        Generate an AI summary of emails using LLM.

        Args:
            emails: List of email dictionaries
            user_id: User ID for context
            unread_only: Whether these are unread emails only

        Returns:
            AI-generated summary of emails
        """
        from providers.openai import OpenAIProvider
        from core.provider_registry import ProviderRegistry

        try:
            # Get OpenAI provider for summarization
            registry = ProviderRegistry(self.memory)
            provider_cfg = registry.get_by_type("openai")

            if not provider_cfg or not provider_cfg.get("api_key"):
                # Fallback to basic formatting if no LLM available
                logging.warning("[ACTION_ROUTER] No OpenAI provider available, using basic email list")
                return self._format_email_list(emails, unread_only)

            provider = OpenAIProvider(
                api_key=provider_cfg["api_key"],
                base_url=provider_cfg.get("base_url"),
                model=provider_cfg.get("model") or "gpt-4o-mini"
            )

            # Build email context for LLM
            email_context = []
            for email in emails:
                email_context.append(
                    f"From: {email.get('from', 'Unknown')}\n"
                    f"Subject: {email.get('subject', 'No subject')}\n"
                    f"Preview: {email.get('preview', '')}\n"
                    f"Received: {email.get('received_at', '')}"
                )

            emails_text = "\n\n---\n\n".join(email_context)

            # Construct summarization prompt
            filter_text = "unread " if unread_only else ""
            logging.info(f"[ACTION_ROUTER] Generating summary for {len(emails)} {filter_text}emails")
            system_prompt = f"""You are an email assistant. Provide a brief, conversational summary of the user's {filter_text}emails.

Rules:
1. Start with EXACTLY the count I give you (e.g., "You have 4 unread emails" if I provide 4 emails)
2. Group by theme/sender when possible (e.g., "2 from your team about the project")
3. Mention only the MOST important or urgent items
4. Maximum 2-3 sentences total
5. Be natural and conversational
6. Avoid dates, order numbers, and excessive detail
7. CRITICAL: Use the EXACT email count - do not estimate or round

Example: "You have 4 unread emails. Most are newsletters and notifications. There's an urgent message from Sarah about tomorrow's meeting."

Focus on what matters. Be concise."""

            user_prompt = f"Here are EXACTLY {len(emails)} {filter_text}emails. Provide a brief summary starting with 'You have {len(emails)} {filter_text}emails':\n\n{emails_text}"

            response = provider.chat(
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Extract text from response
            summary_text = response.strip() if isinstance(response, str) else response.get("text", "").strip()

            logging.info(f"[ACTION_ROUTER] Generated email summary for {len(emails)} emails")
            return summary_text

        except Exception as e:
            logging.error(f"[ACTION_ROUTER] Email summary generation failed: {e}")
            # Fallback to basic formatting
            return self._format_email_list(emails, unread_only)

    def _format_email_list(self, emails: list, unread_only: bool = False) -> str:
        """
        Format emails as a basic list (fallback when LLM unavailable).

        Args:
            emails: List of email dictionaries
            unread_only: Whether these are unread emails only

        Returns:
            Formatted string with email list
        """
        filter_text = "unread " if unread_only else ""
        header = f"You have {len(emails)} {filter_text}email{'s' if len(emails) != 1 else ''}:\n\n"

        formatted = []
        for email in emails[:10]:  # Limit to first 10
            subject = email.get("subject", "No subject")
            sender = email.get("from", "Unknown")
            formatted.append(f"• {subject} (from {sender})")

        if len(emails) > 10:
            formatted.append(f"\n...and {len(emails) - 10} more")

        return header + "\n".join(formatted)

    # =============================
    # Confirmation Actions
    # =============================

    def _handle_approve_confirmation(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle natural language approval of pending confirmations.

        Examples:
        - "approve"
        - "yes"
        - "looks good"
        - "go ahead"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with approval result
        """
        if not self.confirmation_manager:
            return {
                "text": "The confirmation system is not initialized.",
                "provider": "action_router",
                "task_type": "approve_confirmation",
            }

        # Get pending confirmations for this user
        pending = self.confirmation_manager.get_pending_confirmations(user_id)

        if not pending:
            return {
                "text": "You don't have any pending confirmations to approve.",
                "provider": "action_router",
                "task_type": "approve_confirmation",
            }

        # Approve the most recent confirmation
        confirmation = pending[0]
        result = self.confirmation_manager.approve_confirmation(
            confirmation["id"], user_id
        )

        if result["status"] == "success":
            return {
                "text": f"✓ Approved! {result.get('message', 'Action completed successfully.')}",
                "provider": "action_router",
                "task_type": "approve_confirmation",
                "metadata": {
                    "confirmation_id": confirmation["id"],
                    "approved": True
                }
            }
        else:
            return {
                "text": f"Failed to approve: {result.get('message', 'Unknown error')}",
                "provider": "action_router",
                "task_type": "approve_confirmation",
                "metadata": {
                    "error": result.get("message")
                }
            }

    def _handle_reject_confirmation(
        self,
        user_text: str,
        session_id: str,
        user_id: int,
        context: Dict
    ) -> Dict:
        """
        Handle natural language rejection of pending confirmations.

        Examples:
        - "reject"
        - "no"
        - "cancel"
        - "nevermind"

        Args:
            user_text: User's input text
            session_id: Session ID
            user_id: User ID
            context: Full request context

        Returns:
            Response dictionary with rejection result
        """
        if not self.confirmation_manager:
            return {
                "text": "The confirmation system is not initialized.",
                "provider": "action_router",
                "task_type": "reject_confirmation",
            }

        # Get pending confirmations for this user
        pending = self.confirmation_manager.get_pending_confirmations(user_id)

        if not pending:
            return {
                "text": "You don't have any pending confirmations to reject.",
                "provider": "action_router",
                "task_type": "reject_confirmation",
            }

        # Reject the most recent confirmation
        confirmation = pending[0]
        result = self.confirmation_manager.reject_confirmation(
            confirmation["id"], user_id, reason="Rejected via chat"
        )

        if result["status"] == "success":
            return {
                "text": f"✗ Rejected. The action was cancelled.",
                "provider": "action_router",
                "task_type": "reject_confirmation",
                "metadata": {
                    "confirmation_id": confirmation["id"],
                    "rejected": True
                }
            }
        else:
            return {
                "text": f"Failed to reject: {result.get('message', 'Unknown error')}",
                "provider": "action_router",
                "task_type": "reject_confirmation",
                "metadata": {
                    "error": result.get("message")
                }
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

    def _format_event_list(self, events: list, show_date: bool = False) -> str:
        """
        Format a list of events for display.

        Args:
            events: List of event dictionaries
            show_date: If True, include day and date for each event (for multi-day ranges)

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
            time_str = "Time TBD"
            start_time = None

            logging.info(f"[ACTION_ROUTER] Formatting event: {event.get('subject')}, start_time='{start_time_str}', type={type(start_time_str)}")

            if start_time_str:
                try:
                    # Handle both ISO format with and without timezone
                    if isinstance(start_time_str, str):
                        # Microsoft Graph API returns fractional seconds with 7 digits, but Python only supports 6
                        # e.g., "2025-12-27T15:00:00.0000000" -> "2025-12-27T15:00:00.000000"
                        time_str_cleaned = re.sub(r'\.(\d{6})\d+', r'.\1', start_time_str)
                        time_str_cleaned = time_str_cleaned.replace("Z", "+00:00")

                        start_time = datetime.fromisoformat(time_str_cleaned)
                        time_str = start_time.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")
                        logging.info(f"[ACTION_ROUTER] Parsed time successfully: {time_str}")
                except Exception as e:
                    logging.warning(f"[ACTION_ROUTER] Failed to parse start time '{start_time_str}': {e}")

            # Build event line - keep subject and time on same line
            subject = event.get("subject", "Untitled Event")
            location = event.get("location")

            # Format: • Subject at Time • Location
            # If show_date=True (multi-day range), prepend day and date
            if show_date and start_time:
                day_date = start_time.strftime("%A, %B %d")  # e.g., "Monday, December 27"
                event_line = f"**{day_date}**\n• {subject}"
            else:
                event_line = f"• {subject}"

            if time_str != "Time TBD":
                event_line += f" at {time_str}"

            if location:
                event_line += f" • {location}"

            # Add attendees on next line if present
            attendees = event.get("attendees", [])
            if attendees and len(attendees) > 0:
                attendee_count = len(attendees)
                event_line += f"\n  {attendee_count} attendee{'s' if attendee_count > 1 else ''}"

            formatted.append(event_line)

        return "\n\n".join(formatted)

    def _detect_service_category(self, user_text: str) -> str:
        """
        Detect if user is requesting a service booking (haircut, doctor, etc.).

        Args:
            user_text: User's input text

        Returns:
            Service category (haircut, doctor, dentist) or empty string if none detected
        """
        text_lower = user_text.lower()

        # Service keywords mapping
        service_patterns = {
            "haircut": ["haircut", "hair cut", "barber", "salon", "trim", "hairstyle"],
            "doctor": ["doctor", "physician", "gp", "medical appointment", "checkup"],
            "dentist": ["dentist", "dental", "teeth cleaning", "tooth"],
            "massage": ["massage", "spa", "therapist"],
            "gym": ["gym", "personal trainer", "fitness", "workout session"]
        }

        for category, keywords in service_patterns.items():
            if any(keyword in text_lower for keyword in keywords):
                return category

        return ""

    def _handle_service_booking(
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
        from datetime import timedelta

        # Check for service provider
        service_provider = self.memory.get_preferred_provider(user_id, service_category)

        if not service_provider:
            # No provider configured - offer to set one up
            return {
                "text": f"I don't have a {service_category} provider configured yet. "
                       f"Would you like to add one in Settings → Service Providers?",
                "provider": "action_router",
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
                logging.warning(f"[ACTION_ROUTER] Failed to read calendar: {e}")

        # Find free slots
        free_slots = self._find_optimal_slots(
            calendar_events,
            start_date=today,
            end_date=end_date,
            duration_minutes=typical_duration + travel_time_home
        )

        # Build response
        if free_slots:
            slots_text = self._format_free_slots(free_slots[:5])  # Top 5 slots

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
            "task_type": "book_appointment",
            "metadata": {
                "service_category": service_category,
                "provider_name": provider_name,
                "booking_url": booking_url,
                "suggested_slots": [slot.isoformat() for slot in free_slots[:5]] if free_slots else []
            }
        }

    def _find_optimal_slots(
        self,
        calendar_events: list,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 60,
        preferred_hours: tuple = (9, 18)  # 9am to 6pm
    ) -> list:
        """
        Find optimal free time slots in the user's calendar.

        Args:
            calendar_events: List of existing calendar events
            start_date: Start of search range
            end_date: End of search range
            duration_minutes: Required duration for slot
            preferred_hours: Tuple of (start_hour, end_hour) for preferred times

        Returns:
            List of datetime objects representing optimal start times
        """
        from datetime import timedelta

        free_slots = []
        current_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while current_date <= end_date:
            # Skip past dates
            if current_date.date() < datetime.now().date():
                current_date += timedelta(days=1)
                continue

            # Only check weekdays (Monday=0, Sunday=6)
            if current_date.weekday() >= 5:  # Saturday or Sunday
                current_date += timedelta(days=1)
                continue

            # Check each hour in preferred range
            for hour in range(preferred_hours[0], preferred_hours[1]):
                slot_start = current_date.replace(hour=hour, minute=0)
                slot_end = slot_start + timedelta(minutes=duration_minutes)

                # Check if slot conflicts with any event
                is_free = True
                for event in calendar_events:
                    event_start = event.get("start_time")
                    event_end = event.get("end_time")

                    if isinstance(event_start, str):
                        # Normalize M365 datetime format (handle 7-digit microseconds)
                        event_start = self._parse_m365_datetime(event_start)
                    if isinstance(event_end, str):
                        event_end = self._parse_m365_datetime(event_end)

                    # Check for overlap
                    if (slot_start < event_end and slot_end > event_start):
                        is_free = False
                        break

                if is_free and slot_start > datetime.now():
                    free_slots.append(slot_start)

            current_date += timedelta(days=1)

        # Sort by closeness to preferred times (favor early afternoon)
        def time_score(dt):
            # Prefer 1pm-3pm (13-15)
            hour = dt.hour
            if 13 <= hour < 15:
                return 0  # Best
            elif 15 <= hour < 17:
                return 1  # Good
            elif 11 <= hour < 13:
                return 2  # Morning
            else:
                return 3  # Other

        free_slots.sort(key=time_score)
        return free_slots

    def _format_free_slots(self, slots: list) -> str:
        """
        Format free time slots for display.

        Args:
            slots: List of datetime objects

        Returns:
            Formatted string with suggested times
        """
        if not slots:
            return "No free slots found."

        formatted = []
        for i, slot in enumerate(slots, 1):
            day = slot.strftime("%A, %B %d")
            time = slot.strftime("%I:%M %p").lstrip("0")
            formatted.append(f"{i}. {day} at {time}")

        return "\n".join(formatted)

    def _parse_m365_datetime(self, dt_string: str) -> datetime:
        """
        Parse M365 datetime strings which may have 7-digit microseconds.

        M365 Graph API returns formats like:
        - 2025-12-28T15:00:00.0000000
        - 2025-12-28T15:00:00Z

        Args:
            dt_string: ISO format datetime string

        Returns:
            datetime object
        """
        import re

        # Remove 'Z' timezone indicator
        dt_string = dt_string.replace('Z', '+00:00')

        # Regex to find and truncate microseconds to 6 digits (Python's limit)
        # Match: .0000000 (7 digits) and replace with .000000 (6 digits)
        dt_string = re.sub(r'\.(\d{6})\d+', r'.\1', dt_string)

        try:
            return datetime.fromisoformat(dt_string)
        except ValueError as e:
            # If still fails, log and try without microseconds
            logging.warning(f"[ACTION_ROUTER] Failed to parse datetime '{dt_string}': {e}")
            # Remove microseconds entirely
            dt_string = re.sub(r'\.\d+', '', dt_string)
            return datetime.fromisoformat(dt_string)
