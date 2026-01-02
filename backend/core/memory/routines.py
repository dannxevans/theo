"""
Routines-related database operations.

Handles user-defined routine CRUD operations.
"""

import logging
import json
from datetime import datetime
from sqlalchemy import Table, Column, Integer, String, Text, MetaData, select, insert, update, delete
from core.user_utils import normalize_user_id


class RoutineOperations:
    """Database operations for user routines."""

    def __init__(self, engine):
        """Initialize with database engine."""
        self.engine = engine
        meta = MetaData()

        # User routines table
        self.user_routines = Table(
            "user_routines",
            meta,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("user_id", String, nullable=False),
            Column("name", String, nullable=False),
            Column("triggers", Text, nullable=False),  # JSON array
            Column("actions", Text, nullable=False),  # JSON array
            Column("consolidation_prompt", Text),
            Column("enabled", Integer, nullable=False, default=1),
            Column("created_at", String),
            Column("updated_at", String),
        )

    def _get_connection(self):
        """Get database connection context manager."""
        return self.engine.begin()

    def get_user_routines(self, user_id):
        """
        Get all routines for a user.

        Args:
            user_id: User ID

        Returns:
            List of routine dicts
        """

        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            stmt = select(self.user_routines).where(
                self.user_routines.c.user_id == user_id
            )
            result = conn.execute(stmt)
            return [dict(row._mapping) for row in result]

    def get_user_routine(self, routine_id, user_id):
        """
        Get a specific routine.

        Args:
            routine_id: Routine ID
            user_id: User ID (for authorization)

        Returns:
            Routine dict or None
        """
        with self._get_connection() as conn:
            stmt = select(self.user_routines).where(
                (self.user_routines.c.id == routine_id) &
                (self.user_routines.c.user_id == user_id)
            )
            result = conn.execute(stmt).fetchone()
            return dict(result._mapping) if result else None

    def create_user_routine(self, user_id, name, triggers, actions, consolidation_prompt=""):
        """
        Create a new user routine.

        Args:
            user_id: User ID
            name: Routine name
            triggers: List of trigger phrases
            actions: List of action dicts
            consolidation_prompt: Optional consolidation prompt

        Returns:
            Created routine ID
        """

        user_id = normalize_user_id(user_id)

        with self._get_connection() as conn:
            now = datetime.utcnow().isoformat()

            stmt = insert(self.user_routines).values(
                user_id=user_id,
                name=name,
                triggers=json.dumps(triggers),
                actions=json.dumps(actions),
                consolidation_prompt=consolidation_prompt,
                enabled=1,
                created_at=now,
                updated_at=now
            )

            result = conn.execute(stmt)
            routine_id = result.lastrowid

            logging.info(f"[ROUTINES] Created routine {routine_id} for user {user_id}: {name}")
            return routine_id

    def update_user_routine(self, routine_id, user_id, name=None, triggers=None,
                           actions=None, consolidation_prompt=None, enabled=None):
        """
        Update a user routine.

        Args:
            routine_id: Routine ID
            user_id: User ID (for authorization)
            name: Optional new name
            triggers: Optional new triggers list
            actions: Optional new actions list
            consolidation_prompt: Optional new consolidation prompt
            enabled: Optional enabled state

        Returns:
            Success boolean
        """
        with self._get_connection() as conn:
            # Build update values
            values = {"updated_at": datetime.utcnow().isoformat()}

            if name is not None:
                values["name"] = name
            if triggers is not None:
                values["triggers"] = json.dumps(triggers)
            if actions is not None:
                values["actions"] = json.dumps(actions)
            if consolidation_prompt is not None:
                values["consolidation_prompt"] = consolidation_prompt
            if enabled is not None:
                values["enabled"] = 1 if enabled else 0

            stmt = update(self.user_routines).where(
                (self.user_routines.c.id == routine_id) &
                (self.user_routines.c.user_id == user_id)
            ).values(**values)

            conn.execute(stmt)

            logging.info(f"[ROUTINES] Updated routine {routine_id} for user {user_id}")
            return True

    def delete_user_routine(self, routine_id, user_id):
        """
        Delete a user routine.

        Args:
            routine_id: Routine ID
            user_id: User ID (for authorization)

        Returns:
            Success boolean
        """
        with self._get_connection() as conn:
            stmt = delete(self.user_routines).where(
                (self.user_routines.c.id == routine_id) &
                (self.user_routines.c.user_id == user_id)
            )

            conn.execute(stmt)

            logging.info(f"[ROUTINES] Deleted routine {routine_id} for user {user_id}")
            return True
