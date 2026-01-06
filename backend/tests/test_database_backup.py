"""
Tests for database migrations initialization.

Note: S3 backup functionality has been removed (2026-01-06).
These tests now verify that migrations run correctly without S3 dependencies.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


def test_init_database_backup_runs_migrations():
    """Test that init_database_backup runs migrations when database exists."""
    import db_backup

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        with patch('config.Config') as mock_config:
            mock_config.DATABASE_URL = f'sqlite:///{db_path}'

            with patch('db_backup.run_migrations') as mock_migrations:
                with patch('db_backup.logger') as mock_logger:
                    # Call init_database_backup
                    result = db_backup.init_database_backup()

                    # Verify S3 backups disabled message
                    mock_logger.info.assert_any_call(
                        "AWS S3 backups disabled - using Unraid native backup solutions"
                    )

                    # Verify migrations were called
                    mock_logger.info.assert_any_call("Running database migrations")
                    mock_migrations.assert_called_once_with(db_path)

                    # Verify returns None (no backup manager)
                    assert result is None
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_init_database_backup_no_database():
    """Test behavior when database file doesn't exist yet."""
    import db_backup

    db_path = '/tmp/nonexistent_db_for_test.db'

    # Ensure DB doesn't exist
    if os.path.exists(db_path):
        os.unlink(db_path)

    try:
        with patch('config.Config') as mock_config:
            mock_config.DATABASE_URL = f'sqlite:///{db_path}'

            with patch('db_backup.run_migrations') as mock_migrations:
                with patch('db_backup.logger') as mock_logger:
                    # Call init_database_backup
                    result = db_backup.init_database_backup()

                    # Verify S3 backups disabled message
                    mock_logger.info.assert_any_call(
                        "AWS S3 backups disabled - using Unraid native backup solutions"
                    )

                    # Verify message about missing database
                    mock_logger.info.assert_any_call(
                        f"Database not found at {db_path}, will be created on first use"
                    )

                    # Verify migrations were NOT called (no DB file)
                    mock_migrations.assert_not_called()

                    # Verify returns None
                    assert result is None
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_init_database_backup_non_sqlite():
    """Test behavior with non-SQLite database URL."""
    import db_backup

    with patch('config.Config') as mock_config:
        mock_config.DATABASE_URL = 'postgresql://localhost/testdb'

        with patch('db_backup.run_migrations') as mock_migrations:
            with patch('db_backup.logger') as mock_logger:
                # Call init_database_backup
                result = db_backup.init_database_backup()

                # Verify appropriate log message
                mock_logger.info.assert_called_once_with(
                    "Not using SQLite, database migrations not applicable"
                )

                # Verify migrations were NOT called
                mock_migrations.assert_not_called()

                # Verify returns None
                assert result is None
