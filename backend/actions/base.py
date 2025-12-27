"""
Base class for action providers.

Action providers are distinct from LLM providers:
- LLM providers generate text responses
- Action providers execute external actions (calendar, email, bookings)

All action providers must inherit from ActionProvider and implement
the required methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime


class ActionProvider(ABC):
    """
    Base class for all action providers.

    Action providers handle external integrations and execute actions
    on behalf of the user (with confirmation).

    Attributes:
        name: Provider identifier (e.g., "m365", "google_calendar")
        capabilities: List of action types this provider supports
    """

    name = "base"
    capabilities: List[str] = []

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """
        Check if the provider is healthy and reachable.

        This method should perform a lightweight connectivity test
        (e.g., calling a simple API endpoint).

        Returns:
            dict with health status:
            {
                "healthy": bool,
                "status": str ("connected", "degraded", "error", "unknown"),
                "last_check": datetime,
                "error": str (optional, if unhealthy)
            }

        Example:
            >>> provider = M365Provider(...)
            >>> health = provider.check_health()
            >>> print(health["healthy"])
            True
        """
        pass

    @abstractmethod
    def validate_params(self, action_type: str, params: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate action parameters before execution.

        This should check:
        - Required fields are present
        - Field types are correct
        - Values are within valid ranges
        - Relationships between fields are valid

        Args:
            action_type: Type of action (e.g., "create_calendar_event")
            params: Dictionary of action parameters

        Returns:
            Tuple of (is_valid, error_message)
            - is_valid: True if params are valid, False otherwise
            - error_message: Error description if invalid, None if valid

        Example:
            >>> provider = M365Provider(...)
            >>> valid, error = provider.validate_params(
            ...     "create_calendar_event",
            ...     {"subject": "Meeting", "start_time": datetime.now()}
            ... )
            >>> print(valid)
            False
            >>> print(error)
            "Missing required field: end_time"
        """
        pass

    def supports_action(self, action_type: str) -> bool:
        """
        Check if this provider supports a given action type.

        Args:
            action_type: Action type to check (e.g., "read_calendar")

        Returns:
            True if this provider can handle this action type

        Example:
            >>> provider = M365Provider(...)
            >>> provider.supports_action("read_calendar")
            True
            >>> provider.supports_action("book_flight")
            False
        """
        return action_type in self.capabilities

    def get_capabilities(self) -> List[str]:
        """
        Get list of all capabilities this provider supports.

        Returns:
            List of action type strings

        Example:
            >>> provider = M365Provider(...)
            >>> caps = provider.get_capabilities()
            >>> print(caps)
            ['read_calendar', 'create_calendar_event', 'read_email', 'send_email']
        """
        return self.capabilities.copy()

    def __repr__(self) -> str:
        """String representation of the provider."""
        return f"<{self.__class__.__name__} name={self.name} capabilities={len(self.capabilities)}>"


class ActionProviderError(Exception):
    """
    Base exception for action provider errors.

    This should be raised when an action fails for any reason:
    - API connectivity issues
    - Authentication failures
    - Invalid parameters
    - Resource not found
    - Permission denied
    """
    pass


class ActionValidationError(ActionProviderError):
    """
    Exception raised when action parameters are invalid.

    This should be raised during validate_params() when parameters
    don't meet requirements.
    """
    pass


class ActionAuthenticationError(ActionProviderError):
    """
    Exception raised when authentication fails or tokens expire.

    This should be raised when:
    - Access tokens are expired
    - Refresh tokens are invalid
    - User has revoked access
    - Credentials are missing
    """
    pass


class ActionExecutionError(ActionProviderError):
    """
    Exception raised when action execution fails.

    This should be raised when the action itself fails:
    - API call returns error
    - Resource conflicts (e.g., calendar event overlap)
    - Rate limits exceeded
    - Service unavailable
    """
    pass
