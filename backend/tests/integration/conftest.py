"""
Configuration for integration tests.

Ensures database migrations are run before tests execute.
"""

import pytest
import sys
import os
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from config import Config


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """Run migrations before any tests execute."""
    # Import migration runner
    migrations_dir = backend_dir / "migrations"
    sys.path.insert(0, str(migrations_dir))

    from run_migrations import run_all_migrations

    # Extract database path from DATABASE_URL
    db_url = Config.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")

        # Override sys.argv to pass db_path to migration runner
        original_argv = sys.argv.copy()
        sys.argv = [sys.argv[0], db_path]

        try:
            print(f"\n[TEST SETUP] Running migrations on {db_path}")
            success = run_all_migrations()
            if not success:
                pytest.exit("Failed to run migrations", 1)
        finally:
            sys.argv = original_argv

    yield

    # No cleanup - keep test database for inspection
