"""
Shared test fixtures for all tests.

Makes memory fixture available to all test files.
"""

import pytest
import os
import tempfile

from core.memory import MemoryStore


@pytest.fixture
def memory():
    """
    Create MemoryStore with in-memory SQLite database.
    """
    db_fd, db_path = tempfile.mkstemp()
    db_url = f"sqlite:///{db_path}"
    memory_store = MemoryStore(db_url)
    # Store db_url as an attribute for tests that need it
    memory_store.db_url = db_url

    yield memory_store

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
