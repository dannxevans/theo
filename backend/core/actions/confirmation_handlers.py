"""
Confirmation action handlers.

Provides handlers for confirmation management:
- Approving pending confirmations
- Rejecting pending confirmations
"""

from typing import Dict
import logging

from .base_handler import BaseActionHandler


class ConfirmationHandlers(BaseActionHandler):
    """Handlers for confirmation-related actions."""

    def handle_approve_confirmation(
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
            return self._format_error_response(
                "The confirmation system is not initialized.",
                "approve_confirmation"
            )

        # Get pending confirmations for this user
        pending = self.confirmation_manager.get_pending_confirmations(user_id)

        if not pending:
            return self._format_success_response(
                "You don't have any pending confirmations to approve.",
                "approve_confirmation"
            )

        # Approve the most recent confirmation
        confirmation = pending[0]
        result = self.confirmation_manager.approve_confirmation(
            confirmation["id"], user_id
        )

        if result["status"] == "success":
            return {
                "text": f"✓ Approved! {result.get('message', 'Action completed successfully.')}",
                "provider": "action_router",
                "model": None,
                "task_type": "approve_confirmation",
                "metadata": {
                    "confirmation_id": confirmation["id"],
                    "approved": True
                }
            }
        else:
            return self._format_error_response(
                f"Failed to approve: {result.get('message', 'Unknown error')}",
                "approve_confirmation",
                result.get("message")
            )

    def handle_reject_confirmation(
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
            return self._format_error_response(
                "The confirmation system is not initialized.",
                "reject_confirmation"
            )

        # Get pending confirmations for this user
        pending = self.confirmation_manager.get_pending_confirmations(user_id)

        if not pending:
            return self._format_success_response(
                "You don't have any pending confirmations to reject.",
                "reject_confirmation"
            )

        # Reject the most recent confirmation
        confirmation = pending[0]
        result = self.confirmation_manager.reject_confirmation(
            confirmation["id"], user_id, reason="Rejected via chat"
        )

        if result["status"] == "success":
            return {
                "text": f"✗ Rejected. The action was cancelled.",
                "provider": "action_router",
                "model": None,
                "task_type": "reject_confirmation",
                "metadata": {
                    "confirmation_id": confirmation["id"],
                    "rejected": True
                }
            }
        else:
            return self._format_error_response(
                f"Failed to reject: {result.get('message', 'Unknown error')}",
                "reject_confirmation",
                result.get("message")
            )
