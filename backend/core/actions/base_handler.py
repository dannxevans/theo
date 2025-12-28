"""
Base action handler.

Provides common functionality for all action handlers including:
- Provider access
- Response formatting
- Error handling
"""

from typing import Dict, Any, Optional
import logging


class BaseActionHandler:
    """
    Base class for action handlers.

    All action handlers should inherit from this class to get common
    functionality like provider registry access, memory store access,
    and standardized response formatting.
    """

    def __init__(self, action_registry, memory_store, confirmation_manager=None):
        """
        Initialize base handler.

        Args:
            action_registry: ActionProviderRegistry instance
            memory_store: MemoryStore instance
            confirmation_manager: ConfirmationManager instance (optional)
        """
        self.action_registry = action_registry
        self.memory = memory_store
        self.confirmation_manager = confirmation_manager

    def _get_provider(self, capability: str, user_id: int) -> Optional[tuple]:
        """
        Get provider for a specific capability.

        Args:
            capability: Required capability (e.g., "read_calendar")
            user_id: User ID

        Returns:
            Tuple of (provider_id, provider) or None if not found
        """
        self.action_registry.load_providers(user_id)
        providers = self.action_registry.get_providers_by_capability(capability, user_id)

        if not providers:
            return None

        return providers[0]

    def _format_success_response(
        self,
        text: str,
        task_type: str,
        metadata: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Format successful response.

        Args:
            text: Response text to user
            task_type: Type of action performed
            metadata: Additional metadata (optional)

        Returns:
            Standardized response dictionary
        """
        response = {
            "text": text,
            "provider": "action_router",
            "model": None,
            "task_type": task_type,
        }

        if metadata:
            response["metadata"] = metadata

        return response

    def _format_error_response(
        self,
        error_message: str,
        task_type: str,
        error_details: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format error response.

        Args:
            error_message: User-friendly error message
            task_type: Type of action that failed
            error_details: Technical error details (optional)

        Returns:
            Standardized error response dictionary
        """
        response = {
            "text": error_message,
            "provider": "action_router",
            "model": None,
            "task_type": task_type,
            "metadata": {
                "error": True
            }
        }

        if error_details:
            response["metadata"]["error_details"] = error_details

        return response

    def _format_no_provider_response(
        self,
        capability: str,
        task_type: str,
        friendly_name: str = "calendar"
    ) -> Dict[str, Any]:
        """
        Format response when no provider is available.

        Args:
            capability: Required capability
            task_type: Type of action
            friendly_name: Friendly name for the service

        Returns:
            Response prompting user to connect service
        """
        return {
            "text": f"I don't have access to your {friendly_name} yet. Would you like to connect your Microsoft 365 account?",
            "provider": "action_router",
            "model": None,
            "task_type": task_type,
            "metadata": {
                "error": "no_provider",
                "required_capability": capability
            }
        }

    def _log_error(self, handler_name: str, error: Exception):
        """
        Log error with consistent formatting.

        Args:
            handler_name: Name of the handler
            error: Exception that occurred
        """
        logging.error(f"[ACTION_HANDLER:{handler_name}] Error: {str(error)}")
