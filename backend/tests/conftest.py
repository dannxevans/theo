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
    memory_store = MemoryStore(f"sqlite:///{db_path}")

    yield memory_store

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)
