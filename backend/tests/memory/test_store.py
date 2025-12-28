"""
Tests for MemoryStore initialization and database setup.

Tests core MemoryStore functionality and database schema.
"""

import pytest
from core.memory import MemoryStore


def test_memory_store_initialization(memory):
    """Test MemoryStore initializes correctly."""
    assert memory is not None
    assert memory.engine is not None
    assert memory.Session is not None


def test_memory_store_tables_exist(memory):
    """Test all required tables are created."""
    from sqlalchemy import inspect

    inspector = inspect(memory.engine)
    tables = inspector.get_table_names()

    # Check all required tables exist
    required_tables = [
        "users",
        "auth_sessions",
        "user_mode_config",
        "mode_settings",
        "work_mode_subtab_config",
        "debug_settings",
        "preferences",
        "system_prompt_config",
        "memories",
        "intents",
        "routing_preferences",
        "provider_metadata",
        "request_logs",
        "providers",
        "sessions",
        "summaries",
        "turns",
        "session_providers",
        "service_providers",
        "actions",
        "action_confirmations",
        "m365_credentials",
        "calendar_events_cache"
    ]

    for table in required_tables:
        assert table in tables, f"Table {table} not found in database"


def test_memory_store_engine(memory):
    """Test database engine is properly configured."""
    assert memory.engine is not None
    assert str(memory.engine.url).startswith("sqlite://")


def test_memory_store_session_factory(memory):
    """Test session factory creates sessions."""
    session = memory.Session()
    assert session is not None
    session.close()


def test_memory_store_tables_accessible(memory):
    """Test all table references are accessible."""
    assert memory.users is not None
    assert memory.auth_sessions is not None
    assert memory.memories is not None
    assert memory.intents is not None
    assert memory.providers is not None
    assert memory.sessions is not None
    assert memory.turns is not None


def test_memory_store_multiple_instances():
    """Test multiple MemoryStore instances work independently."""
    import tempfile
    import os

    db_fd1, db_path1 = tempfile.mkstemp()
    db_fd2, db_path2 = tempfile.mkstemp()

    memory1 = MemoryStore(f"sqlite:///{db_path1}")
    memory2 = MemoryStore(f"sqlite:///{db_path2}")

    # Store data in first instance
    memory1.remember("user1", "key", "value1")

    # Verify not in second instance
    prefs2 = memory2.get_all("user1")
    assert prefs2.get("key") != "value1"

    # Cleanup
    os.close(db_fd1)
    os.close(db_fd2)
    os.unlink(db_path1)
    os.unlink(db_path2)


def test_memory_store_persistence():
    """Test data persists across MemoryStore instances."""
    import tempfile
    import os

    db_fd, db_path = tempfile.mkstemp()

    # Create first instance and store data
    memory1 = MemoryStore(f"sqlite:///{db_path}")
    memory1.remember("user1", "persist_test", "persisted_value")

    # Create second instance with same database
    memory2 = MemoryStore(f"sqlite:///{db_path}")
    prefs = memory2.get_all("user1")

    assert prefs.get("persist_test") == "persisted_value"

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
