"""
Action and Confirmation Operations.

Handles action creation, confirmation workflow, and action lifecycle management.
"""

import json
import logging
from datetime import datetime
from sqlalchemy import select, update, insert

from .base import BaseMemoryOperations


class ActionOperations(BaseMemoryOperations):
    """Action and confirmation management operations."""

    # =============================
    # Actions API
    # =============================

    def create_action(self, user_id, session_id, action_type, category,
                      intent_summary, service_provider_id=None, **kwargs):
        """
        Create a new action.

        Args:
            user_id: User ID
            session_id: Session ID
            action_type: Type of action (e.g., "book_appointment", "send_email")
            category: Action category (e.g., "calendar", "email")
            intent_summary: Human-readable summary of the intent
            service_provider_id: Optional service provider ID
            **kwargs: Additional fields (action_params, planned_execution_time, etc.)

        Returns:
            int: Action ID
        """
        # Serialize action_params to JSON if it's a dict
        action_params = kwargs.get("action_params")
        if action_params and isinstance(action_params, dict):
            action_params = json.dumps(action_params)

        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.actions).values(
                    user_id=user_id,
                    session_id=session_id,
                    action_type=action_type,
                    category=category,
                    intent_summary=intent_summary,
                    service_provider_id=service_provider_id,
                    action_params=action_params,
                    planned_execution_time=kwargs.get("planned_execution_time"),
                    status=kwargs.get("status", "pending"),
                    requires_confirmation=kwargs.get("requires_confirmation", True),
                    is_reversible=kwargs.get("is_reversible", False),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
            )
            return result.lastrowid

    def get_action(self, action_id):
        """
        Get an action by ID.

        Args:
            action_id: Action ID

        Returns:
            dict: Action data or None if not found
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.actions).where(self.actions.c.id == action_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_pending_actions(self, user_id):
        """
        Get all pending actions for a user.

        Args:
            user_id: User ID

        Returns:
            list: List of pending action dicts
        """
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(self.actions)
                .where(self.actions.c.user_id == user_id)
                .where(self.actions.c.status == "pending")
                .order_by(self.actions.c.created_at.desc())
            ).fetchall()
            return [dict(row._mapping) for row in rows]

    def update_action_status(self, action_id, status, **kwargs):
        """
        Update action status and related fields.

        Args:
            action_id: Action ID
            status: New status (pending, approved, executing, completed, rejected)
            **kwargs: Additional fields to update
        """
        with self.engine.begin() as conn:
            update_values = {"status": status, "updated_at": datetime.utcnow()}

            # Add timestamp based on status
            if status == "approved":
                update_values["approved_at"] = datetime.utcnow()
            elif status == "executing":
                update_values["initiated_at"] = datetime.utcnow()
            elif status == "completed":
                update_values["completed_at"] = datetime.utcnow()

            # Add any additional fields
            for key, value in kwargs.items():
                if value is not None:
                    update_values[key] = value

            conn.execute(
                update(self.actions)
                .where(self.actions.c.id == action_id)
                .values(**update_values)
            )

    def get_action_by_id(self, action_id):
        """
        Get an action by ID (alias for get_action).

        Args:
            action_id: Action ID

        Returns:
            dict: Action data or None if not found
        """
        return self.get_action(action_id)

    # =============================
    # Confirmations API
    # =============================

    def create_confirmation(self, action_id, confirmation_message, expires_at):
        """
        Create a confirmation request for an action.

        Args:
            action_id: Action ID
            confirmation_message: Message to show user
            expires_at: Confirmation expiration datetime

        Returns:
            int: Confirmation ID
        """
        with self.engine.begin() as conn:
            result = conn.execute(
                insert(self.action_confirmations).values(
                    action_id=action_id,
                    confirmation_message=confirmation_message,
                    presented_at=datetime.utcnow(),
                    expires_at=expires_at,
                    created_at=datetime.utcnow()
                )
            )
            return result.lastrowid

    def get_pending_confirmations(self, user_id):
        """
        Get all pending confirmations for a user.

        Args:
            user_id: User ID

        Returns:
            list: List of confirmation dicts with action data
        """
        with self.engine.begin() as conn:
            rows = conn.execute(
                select(
                    self.actions,
                    self.action_confirmations
                )
                .join(
                    self.action_confirmations,
                    self.actions.c.id == self.action_confirmations.c.action_id
                )
                .where(self.actions.c.user_id == user_id)
                .where(self.actions.c.status == "pending")
                .where(self.action_confirmations.c.user_response.is_(None))
            ).fetchall()

            return [dict(row._mapping) for row in rows]

    def update_confirmation_response(self, action_id, user_response, user_response_text=None):
        """
        Update confirmation with user response.

        Args:
            action_id: Action ID
            user_response: User response (approved, rejected)
            user_response_text: Optional user response text
        """
        with self.engine.begin() as conn:
            conn.execute(
                update(self.action_confirmations)
                .where(self.action_confirmations.c.action_id == action_id)
                .values(
                    user_response=user_response,
                    user_response_text=user_response_text,
                    responded_at=datetime.utcnow()
                )
            )

    def get_confirmation_by_id(self, confirmation_id):
        """
        Get a confirmation by ID with computed status.

        Args:
            confirmation_id: Confirmation ID

        Returns:
            dict: Confirmation data with computed status or None if not found
        """
        with self.engine.begin() as conn:
            row = conn.execute(
                select(self.action_confirmations)
                .where(self.action_confirmations.c.id == confirmation_id)
            ).fetchone()

            if not row:
                return None

            result = dict(row._mapping)

            # Add computed status field
            if result.get("user_response"):
                result["status"] = result["user_response"]
            elif result.get("expires_at") and result["expires_at"] < datetime.utcnow():
                result["status"] = "expired"
            else:
                result["status"] = "pending"

            return result

    def update_confirmation_status(self, confirmation_id, status, **kwargs):
        """
        Update confirmation status.

        Maps status to user_response field:
        - "approved" → user_response="approved"
        - "rejected" → user_response="rejected"
        - "expired" → user_response="expired"

        Args:
            confirmation_id: Confirmation ID
            status: New status
            **kwargs: Additional fields (e.g., responded_at)
        """
        with self.engine.begin() as conn:
            update_values = {"user_response": status}

            # Add responded_at if provided
            if "responded_at" in kwargs:
                update_values["responded_at"] = kwargs["responded_at"]

            conn.execute(
                update(self.action_confirmations)
                .where(self.action_confirmations.c.id == confirmation_id)
                .values(**update_values)
            )

    def update_turn_metadata(self, session_id, confirmation_id, approved):
        """
        Update the metadata of a turn to reflect approval/rejection status.

        Args:
            session_id: Session ID
            confirmation_id: Confirmation ID to find the turn
            approved: True if approved, False if rejected
        """
        with self.engine.begin() as conn:
            # Find the turn with this confirmation_id in metadata
            rows = conn.execute(
                select(
                    self.turns.c.id,
                    self.turns.c.metadata
                )
                .where(self.turns.c.session_id == session_id)
                .where(self.turns.c.metadata.isnot(None))
            ).fetchall()

            for row in rows:
                try:
                    metadata = json.loads(row.metadata) if row.metadata else None
                    if metadata and metadata.get('confirmation_id') == confirmation_id:
                        # Update the metadata
                        metadata['approved'] = approved
                        metadata['rejected'] = not approved

                        # Update the turn
                        conn.execute(
                            update(self.turns)
                            .where(self.turns.c.id == row.id)
                            .values(metadata=json.dumps(metadata))
                        )
                        logging.info(f"[MEMORY] Updated turn metadata for confirmation {confirmation_id}: approved={approved}")
                        break
                except (json.JSONDecodeError, KeyError) as e:
                    logging.warning(f"[MEMORY] Failed to parse turn metadata: {e}")
                    continue
