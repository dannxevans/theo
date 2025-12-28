"""
Action Router (Refactored).

Routes action requests to appropriate action providers.
Delegates to specialized handler modules for clean separation of concerns.

This is distinct from the LLM router (router.py):
- LLM router: Routes text generation requests to AI models
- Action router: Routes action execution requests to service providers
"""

from typing import Dict, Any
import logging

from .actions import CalendarHandlers, EmailHandlers, ConfirmationHandlers


class ActionRouter:
    """
    Routes action requests to appropriate providers.

    Responsibilities:
    1. Parse user intent from natural language
    2. Identify required action(s)
    3. Delegate to specialized handlers
    4. Return formatted response

    Flow:
    User: "What's on my calendar Tuesday?"
      → ActionRouter.route_action_request()
      → Delegate to CalendarHandlers.handle_read_calendar()
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

        # Initialize specialized handlers
        self.calendar_handlers = CalendarHandlers(
            action_registry,
            memory_store,
            confirmation_manager
        )
        self.email_handlers = EmailHandlers(
            action_registry,
            memory_store,
            confirmation_manager
        )
        self.confirmation_handlers = ConfirmationHandlers(
            action_registry,
            memory_store,
            confirmation_manager
        )

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

        # Delegate to specialized handlers
        handler_map = {
            # Calendar actions
            "read_calendar": self.calendar_handlers.handle_read_calendar,
            "book_appointment": self.calendar_handlers.handle_book_appointment,
            "update_appointment": self.calendar_handlers.handle_update_appointment,
            "cancel_appointment": self.calendar_handlers.handle_cancel_appointment,

            # Email actions
            "read_email": self.email_handlers.handle_read_email,
            "compose_email": self.email_handlers.handle_compose_email,

            # Confirmation actions
            "approve_confirmation": self.confirmation_handlers.handle_approve_confirmation,
            "reject_confirmation": self.confirmation_handlers.handle_reject_confirmation,
        }

        handler = handler_map.get(intent)
        if not handler:
            return {
                "text": f"I understand you want to {intent}, but that action isn't implemented yet.",
                "provider": "action_router",
                "model": None,
                "task_type": intent,
            }

        return handler(user_text, session_id, user_id, context)
