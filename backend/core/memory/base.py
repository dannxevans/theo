"""
Base class for memory store operations.

Provides common functionality for database operations including
session management and shared utilities.
"""

from typing import Dict, Any
from sqlalchemy import Table
from sqlalchemy.orm import Session


class BaseMemoryOperations:
    """
    Base class for all memory store operation modules.

    Provides:
    - Access to database tables
    - Session management utilities
    - Common helper methods
    """

    def __init__(self, tables: Dict[str, Table], session_factory, engine):
        """
        Initialize base operations.

        Args:
            tables: Dictionary of table name to Table object
            session_factory: SQLAlchemy sessionmaker instance
            engine: SQLAlchemy engine instance
        """
        # Store engine and session factory
        self.engine = engine
        self.Session = session_factory

        # Store all tables
        self.users = tables["users"]
        self.auth_sessions = tables["auth_sessions"]
        self.user_mode_config = tables["user_mode_config"]
        self.mode_settings = tables["mode_settings"]
        self.work_mode_subtab_config = tables["work_mode_subtab_config"]
        self.debug_settings = tables["debug_settings"]
        self.preferences = tables["preferences"]
        self.system_prompt_config = tables["system_prompt_config"]
        self.memories = tables["memories"]
        self.intents = tables["intents"]
        self.routing_preferences = tables["routing_preferences"]
        self.provider_metadata = tables["provider_metadata"]
        self.request_logs = tables["request_logs"]
        self.providers = tables["providers"]
        self.sessions = tables["sessions"]
        self.summaries = tables["summaries"]
        self.turns = tables["turns"]
        self.session_providers = tables["session_providers"]
        self.service_providers = tables["service_providers"]
        self.actions = tables["actions"]
        self.action_confirmations = tables["action_confirmations"]
        self.m365_credentials = tables["m365_credentials"]
        self.calendar_events_cache = tables["calendar_events_cache"]

    def _get_connection(self):
        """
        Get database connection context manager.

        Returns:
            SQLAlchemy connection context manager
        """
        return self.engine.begin()

    def _execute(self, stmt):
        """
        Execute a statement and commit.

        Args:
            stmt: SQLAlchemy statement to execute

        Returns:
            Result of execution
        """
        session = self.Session()
        try:
            result = session.execute(stmt)
            session.commit()
            return result
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def _fetchone(self, stmt):
        """
        Execute a select statement and return one row.

        Args:
            stmt: SQLAlchemy select statement

        Returns:
            Row as dictionary or None
        """
        session = self.Session()
        try:
            result = session.execute(stmt)
            row = result.fetchone()
            if row:
                return dict(row._mapping)
            return None
        finally:
            session.close()

    def _fetchall(self, stmt):
        """
        Execute a select statement and return all rows.

        Args:
            stmt: SQLAlchemy select statement

        Returns:
            List of rows as dictionaries
        """
        session = self.Session()
        try:
            result = session.execute(stmt)
            rows = result.fetchall()
            return [dict(row._mapping) for row in rows]
        finally:
            session.close()
