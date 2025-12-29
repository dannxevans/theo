"""
Classification Audit Logging

Tracks classification-related actions for OFFICIAL compliance accountability.
Logs session creation, exports, updates, and access with classification information.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import insert


class ClassificationAuditor:
    """Handles classification audit logging for OFFICIAL compliance"""

    def __init__(self, store):
        """
        Initialize the auditor with a memory store

        Args:
            store: MemoryStore instance with database connection
        """
        self.store = store
        self.classification_audit = store.tables["classification_audit"]

    def log_action(
        self,
        user_id: int,
        classification: str,
        action: str,
        session_id: Optional[str] = None,
        justification: Optional[str] = None
    ) -> int:
        """
        Log a classification-related action

        Args:
            user_id: ID of user performing the action
            classification: Classification level (e.g., 'OFFICIAL')
            action: Type of action ('create', 'export', 'update', 'access')
            session_id: Optional session ID if action is session-specific
            justification: Optional justification text (required for some actions)

        Returns:
            ID of the created audit log entry
        """
        stmt = insert(self.classification_audit).values(
            user_id=user_id,
            session_id=session_id,
            classification=classification,
            action=action,
            justification=justification,
            timestamp=datetime.utcnow()
        )

        result = self.store.conn.execute(stmt)
        self.store.conn.commit()

        return result.lastrowid

    def log_session_create(self, user_id: int, session_id: str, classification: str = "OFFICIAL"):
        """
        Log the creation of a new session with classification

        Args:
            user_id: ID of user creating the session
            session_id: ID of the created session
            classification: Classification level (defaults to 'OFFICIAL')
        """
        return self.log_action(
            user_id=user_id,
            classification=classification,
            action="create",
            session_id=session_id
        )

    def log_session_export(
        self,
        user_id: int,
        session_id: str,
        classification: str,
        justification: Optional[str] = None
    ):
        """
        Log the export of a session

        Args:
            user_id: ID of user exporting the session
            session_id: ID of the exported session
            classification: Classification level of the session
            justification: Optional justification for export
        """
        return self.log_action(
            user_id=user_id,
            classification=classification,
            action="export",
            session_id=session_id,
            justification=justification
        )

    def log_session_access(self, user_id: int, session_id: str, classification: str):
        """
        Log access to a classified session

        Args:
            user_id: ID of user accessing the session
            session_id: ID of the accessed session
            classification: Classification level of the session
        """
        return self.log_action(
            user_id=user_id,
            classification=classification,
            action="access",
            session_id=session_id
        )

    def log_classification_update(
        self,
        user_id: int,
        session_id: str,
        new_classification: str,
        justification: Optional[str] = None
    ):
        """
        Log a change to a session's classification

        Args:
            user_id: ID of user updating the classification
            session_id: ID of the session being updated
            new_classification: New classification level
            justification: Optional justification for the change
        """
        return self.log_action(
            user_id=user_id,
            classification=new_classification,
            action="update",
            session_id=session_id,
            justification=justification
        )

    def get_session_audit_trail(self, session_id: str) -> list:
        """
        Get audit trail for a specific session

        Args:
            session_id: ID of the session

        Returns:
            List of audit log entries for the session
        """
        from sqlalchemy import select

        stmt = (
            select(self.classification_audit)
            .where(self.classification_audit.c.session_id == session_id)
            .order_by(self.classification_audit.c.timestamp.desc())
        )

        result = self.store.conn.execute(stmt)
        return [dict(row._mapping) for row in result]

    def get_user_audit_trail(self, user_id: int, limit: int = 100) -> list:
        """
        Get recent audit trail for a user

        Args:
            user_id: ID of the user
            limit: Maximum number of entries to return (default 100)

        Returns:
            List of audit log entries for the user
        """
        from sqlalchemy import select

        stmt = (
            select(self.classification_audit)
            .where(self.classification_audit.c.user_id == user_id)
            .order_by(self.classification_audit.c.timestamp.desc())
            .limit(limit)
        )

        result = self.store.conn.execute(stmt)
        return [dict(row._mapping) for row in result]

    def get_classification_stats(self, user_id: Optional[int] = None) -> dict:
        """
        Get statistics about classification actions

        Args:
            user_id: Optional user ID to filter stats

        Returns:
            Dictionary with counts by action type and classification
        """
        from sqlalchemy import select, func

        table = self.classification_audit

        # Build base query
        if user_id:
            base_filter = table.c.user_id == user_id
        else:
            base_filter = True

        # Count by action
        action_counts = {}
        stmt = (
            select(
                table.c.action,
                func.count(table.c.id).label('count')
            )
            .where(base_filter)
            .group_by(table.c.action)
        )
        result = self.store.conn.execute(stmt)
        for row in result:
            action_counts[row.action] = row.count

        # Count by classification
        classification_counts = {}
        stmt = (
            select(
                table.c.classification,
                func.count(table.c.id).label('count')
            )
            .where(base_filter)
            .group_by(table.c.classification)
        )
        result = self.store.conn.execute(stmt)
        for row in result:
            classification_counts[row.classification] = row.count

        # Total count
        stmt = select(func.count(table.c.id)).where(base_filter)
        total = self.store.conn.execute(stmt).scalar()

        return {
            'total_actions': total,
            'by_action': action_counts,
            'by_classification': classification_counts
        }
