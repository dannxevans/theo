"""
Confirmation Manager for Human-in-the-Loop Actions.

This module handles the confirmation workflow for all actions that require
user approval before execution. This is a core trust-building feature.

Flow:
1. Action is planned (e.g., "Book haircut at 5pm Tuesday")
2. ConfirmationManager creates confirmation request with:
   - Human-readable summary
   - Action details
   - Expiration time
3. User approves or rejects
4. On approval: Execute action via ActionRouter
5. On rejection: Cancel and log reason

Confirmation States:
- pending: Awaiting user decision
- approved: User confirmed, ready for execution
- rejected: User declined
- expired: Timeout (default 24 hours)
- executed: Action completed successfully
- failed: Action execution failed
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging


class ConfirmationManager:
    """
    Manages confirmation requests for actions requiring human approval.

    This class sits between the ActionRouter and ActionProviders,
    ensuring no write operations happen without explicit user consent.
    """

    def __init__(self, memory_store, action_router):
        """
        Initialize confirmation manager.

        Args:
            memory_store: MemoryStore instance for persistence
            action_router: ActionRouter instance for executing approved actions
        """
        self.memory = memory_store
        self.action_router = action_router

    def create_confirmation(
        self,
        user_id: int,
        session_id: str,
        action_type: str,
        action_params: Dict[str, Any],
        confirmation_message: str,
        provider_id: Optional[int] = None,
        expires_in_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Create a new confirmation request.

        This should be called by ActionRouter when planning a write action
        (create, update, delete, send).

        Args:
            user_id: User ID
            session_id: Session ID
            action_type: Type of action (e.g., "create_calendar_event")
            action_params: Parameters for the action
            confirmation_message: Human-readable summary for user
            provider_id: Service provider ID (optional)
            expires_in_hours: Hours until confirmation expires (default 24)

        Returns:
            Dictionary with confirmation details:
            {
                "confirmation_id": int,
                "action_id": int,
                "message": str,
                "expires_at": datetime,
                "status": "pending"
            }

        Example:
            >>> manager = ConfirmationManager(memory, router)
            >>> confirmation = manager.create_confirmation(
            ...     user_id=1,
            ...     session_id="session_123",
            ...     action_type="create_calendar_event",
            ...     action_params={
            ...         "subject": "Haircut",
            ...         "start_time": "2025-12-31T17:00:00",
            ...         "end_time": "2025-12-31T17:30:00",
            ...         "location": "Cuts Barber"
            ...     },
            ...     confirmation_message="Book haircut at Cuts Barber on Dec 31 at 5:00 PM?",
            ...     provider_id=1
            ... )
            >>> print(confirmation["message"])
            "Book haircut at Cuts Barber on Dec 31 at 5:00 PM?"
        """
        # Create action record
        action_id = self.memory.create_action(
            user_id=user_id,
            session_id=session_id,
            action_type=action_type,
            category=self._get_action_category(action_type),
            intent_summary=confirmation_message,  # Use confirmation message as summary
            service_provider_id=provider_id,
            action_params=action_params,
            status="pending",
        )

        # Create confirmation record
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

        confirmation_id = self.memory.create_confirmation(
            action_id=action_id,
            confirmation_message=confirmation_message,
            expires_at=expires_at,
        )

        logging.info(
            f"[CONFIRMATION] Created confirmation {confirmation_id} for action {action_id} (user {user_id})"
        )

        return {
            "confirmation_id": confirmation_id,
            "action_id": action_id,
            "message": confirmation_message,
            "expires_at": expires_at,
            "status": "pending",
        }

    def get_pending_confirmations(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all pending confirmations for a user.

        Args:
            user_id: User ID

        Returns:
            List of confirmation dictionaries with action details

        Example:
            >>> confirmations = manager.get_pending_confirmations(user_id=1)
            >>> for conf in confirmations:
            ...     print(f"{conf['id']}: {conf['message']}")
        """
        confirmations = self.memory.get_pending_confirmations(user_id)

        # Filter out expired confirmations
        now = datetime.utcnow()
        active_confirmations = []

        for conf in confirmations:
            if conf["expires_at"] < now:
                # Mark as expired
                self.memory.update_confirmation_status(
                    conf["id"], "expired", responded_at=now
                )
                self.memory.update_action_status(
                    conf["action_id"], "cancelled", error_message="Confirmation expired"
                )
                logging.info(f"[CONFIRMATION] Expired confirmation {conf['id']}")
            else:
                active_confirmations.append(conf)

        return active_confirmations

    def approve_confirmation(
        self, confirmation_id: int, user_id: int
    ) -> Dict[str, Any]:
        """
        Approve a confirmation and execute the action.

        Args:
            confirmation_id: Confirmation ID
            user_id: User ID (for authorization)

        Returns:
            Result dictionary:
            {
                "status": "success" | "error",
                "message": str,
                "action_result": dict (if successful)
            }

        Example:
            >>> result = manager.approve_confirmation(confirmation_id=123, user_id=1)
            >>> if result["status"] == "success":
            ...     print("Action executed successfully")
        """
        # Get confirmation details
        conf = self.memory.get_confirmation_by_id(confirmation_id)

        if not conf:
            return {
                "status": "error",
                "message": "Confirmation not found",
            }

        # Verify ownership
        action = self.memory.get_action_by_id(conf["action_id"])
        if not action or action["user_id"] != user_id:
            return {
                "status": "error",
                "message": "Unauthorized",
            }

        # Check if already responded
        if conf["status"] != "pending":
            return {
                "status": "error",
                "message": f"Confirmation already {conf['status']}",
            }

        # Check expiration
        if conf["expires_at"] < datetime.utcnow():
            self.memory.update_confirmation_status(
                confirmation_id, "expired", responded_at=datetime.utcnow()
            )
            return {
                "status": "error",
                "message": "Confirmation expired",
            }

        # Mark as approved
        self.memory.update_confirmation_status(
            confirmation_id, "approved", responded_at=datetime.utcnow()
        )

        self.memory.update_action_status(action["id"], "approved")

        logging.info(
            f"[CONFIRMATION] User {user_id} approved confirmation {confirmation_id}"
        )

        # Execute the action
        try:
            result = self._execute_action(action)

            # Mark action as completed
            self.memory.update_action_status(
                action["id"], "completed", result=result
            )

            logging.info(
                f"[CONFIRMATION] Action {action['id']} executed successfully"
            )

            return {
                "status": "success",
                "message": "Action executed successfully",
                "action_result": result,
            }

        except Exception as e:
            # Mark action as failed
            self.memory.update_action_status(
                action["id"], "failed", error_message=str(e)
            )

            logging.error(
                f"[CONFIRMATION] Action {action['id']} execution failed: {e}"
            )

            return {
                "status": "error",
                "message": f"Action execution failed: {str(e)}",
                "error": str(e),
            }

    def reject_confirmation(
        self, confirmation_id: int, user_id: int, reason: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Reject a confirmation request.

        Args:
            confirmation_id: Confirmation ID
            user_id: User ID (for authorization)
            reason: Optional reason for rejection

        Returns:
            Result dictionary:
            {
                "status": "success" | "error",
                "message": str
            }

        Example:
            >>> result = manager.reject_confirmation(
            ...     confirmation_id=123,
            ...     user_id=1,
            ...     reason="Time doesn't work for me"
            ... )
        """
        # Get confirmation details
        conf = self.memory.get_confirmation_by_id(confirmation_id)

        if not conf:
            return {
                "status": "error",
                "message": "Confirmation not found",
            }

        # Verify ownership
        action = self.memory.get_action_by_id(conf["action_id"])
        if not action or action["user_id"] != user_id:
            return {
                "status": "error",
                "message": "Unauthorized",
            }

        # Check if already responded
        if conf["status"] != "pending":
            return {
                "status": "error",
                "message": f"Confirmation already {conf['status']}",
            }

        # Mark as rejected
        self.memory.update_confirmation_status(
            confirmation_id, "rejected", responded_at=datetime.utcnow()
        )

        # Cancel the action
        cancel_reason = f"User rejected: {reason}" if reason else "User rejected"
        self.memory.update_action_status(
            action["id"], "cancelled", error_message=cancel_reason
        )

        logging.info(
            f"[CONFIRMATION] User {user_id} rejected confirmation {confirmation_id}: {cancel_reason}"
        )

        return {
            "status": "success",
            "message": "Confirmation rejected",
        }

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an approved action via the appropriate provider.

        Args:
            action: Action record from database

        Returns:
            Result dictionary from provider

        Raises:
            Exception: If action execution fails
        """
        action_type = action["action_type"]
        params = action.get("parameters", {})
        provider_id = action.get("provider_id")

        logging.info(
            f"[CONFIRMATION] Executing action {action['id']}: {action_type}"
        )

        # Get provider from registry
        from actions.action_registry import ActionProviderRegistry

        registry = ActionProviderRegistry(self.memory)
        registry.load_providers(action["user_id"])

        if provider_id:
            provider = registry.get_provider(provider_id)
            if not provider:
                raise Exception(f"Provider {provider_id} not found")
        else:
            # Find provider by capability
            providers = registry.get_providers_by_capability(
                action_type, action["user_id"]
            )
            if not providers:
                raise Exception(f"No provider found for {action_type}")
            provider_id, provider = providers[0]

        # Validate parameters
        valid, error = provider.validate_params(action_type, params)
        if not valid:
            raise Exception(f"Invalid parameters: {error}")

        # Execute based on action type
        if action_type == "create_calendar_event":
            result = provider.create_calendar_event(**params)
        elif action_type == "update_calendar_event":
            result = provider.update_calendar_event(**params)
        elif action_type == "delete_calendar_event":
            result = provider.delete_calendar_event(**params)
        elif action_type == "send_email":
            result = provider.send_email(**params)
        elif action_type == "draft_email":
            result = provider.draft_email(**params)
        else:
            raise Exception(f"Unsupported action type: {action_type}")

        return result

    def _get_action_category(self, action_type: str) -> str:
        """
        Map action type to category.

        Args:
            action_type: Action type (e.g., "create_calendar_event")

        Returns:
            Category string (e.g., "calendar", "email")
        """
        if "calendar" in action_type:
            return "calendar"
        elif "email" in action_type:
            return "email"
        elif "appointment" in action_type or "booking" in action_type:
            return "booking"
        else:
            return "other"
