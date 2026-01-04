"""
Tests for database backup initialization and S3 restore logic.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


def test_init_database_backup_auto_restore_enabled():
    """Test AUTO_RESTORE_S3=true triggers restore on startup."""
    import db_backup

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Mock environment and dependencies
        with patch.dict(os.environ, {
            'AUTO_RESTORE_S3': 'true',
            'THEO_S3_BACKUP_BUCKET': 'test-bucket',
            'ENV': 'prod'
        }):
            # Patch Config where it's imported (inside the function)
            with patch('config.Config') as mock_config:
                mock_config.DATABASE_URL = f'sqlite:///{db_path}'

                with patch('db_backup.DatabaseBackupManager') as mock_manager_class:
                    mock_manager = MagicMock()
                    mock_manager.restore_from_s3.return_value = True
                    mock_manager_class.return_value = mock_manager

                    with patch('db_backup.run_migrations'):
                        with patch('db_backup.logger') as mock_logger:
                            # Call init_database_backup
                            result = db_backup.init_database_backup()

                            # Verify AUTO_RESTORE_S3=true log was called (line 219)
                            mock_logger.info.assert_any_call(
                                "AUTO_RESTORE_S3=true, restoring database from S3 on startup..."
                            )

                            # Verify restore was called (line 220)
                            mock_manager.restore_from_s3.assert_called_once()

                            # Verify auto backup was setup (line 223)
                            mock_manager.setup_auto_backup.assert_called_once_with(interval_seconds=300)
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_init_database_backup_auto_restore_disabled():
    """Test AUTO_RESTORE_S3=false skips restore on startup."""
    import db_backup

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Mock environment with AUTO_RESTORE_S3=false
        with patch.dict(os.environ, {
            'AUTO_RESTORE_S3': 'false',
            'THEO_S3_BACKUP_BUCKET': 'test-bucket',
            'ENV': 'dev'
        }):
            with patch('config.Config') as mock_config:
                mock_config.DATABASE_URL = f'sqlite:///{db_path}'

                with patch('db_backup.DatabaseBackupManager') as mock_manager_class:
                    mock_manager = MagicMock()
                    mock_manager_class.return_value = mock_manager

                    with patch('db_backup.run_migrations'):
                        with patch('db_backup.logger') as mock_logger:
                            # Call init_database_backup
                            result = db_backup.init_database_backup()

                            # Verify skip log was called (line 222)
                            mock_logger.info.assert_any_call(
                                "AUTO_RESTORE_S3=False, skipping automatic S3 restore"
                            )

                            # Verify restore was NOT called
                            mock_manager.restore_from_s3.assert_not_called()

                            # Verify auto backup was NOT setup in dev environment
                            mock_manager.setup_auto_backup.assert_not_called()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_init_database_backup_no_s3_bucket():
    """Test behavior when S3 bucket is not configured."""
    import db_backup

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Mock environment without S3 bucket
        with patch.dict(os.environ, {
            'AUTO_RESTORE_S3': 'true',
            'ENV': 'dev'
        }, clear=True):
            # Ensure THEO_S3_BACKUP_BUCKET is not set
            if 'THEO_S3_BACKUP_BUCKET' in os.environ:
                del os.environ['THEO_S3_BACKUP_BUCKET']

            with patch('config.Config') as mock_config:
                mock_config.DATABASE_URL = f'sqlite:///{db_path}'

                with patch('db_backup.DatabaseBackupManager') as mock_manager_class:
                    mock_manager = MagicMock()
                    mock_manager_class.return_value = mock_manager

                    with patch('db_backup.run_migrations'):
                        with patch('db_backup.logger') as mock_logger:
                            # Call init_database_backup
                            result = db_backup.init_database_backup()

                            # Verify restore was not called when no S3 bucket
                            mock_manager.restore_from_s3.assert_not_called()

                            # Verify auto backup was not setup
                            mock_manager.setup_auto_backup.assert_not_called()
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_init_database_backup_prod_environment():
    """Test auto backup is enabled in production environment."""
    import db_backup

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name

    try:
        # Mock production environment
        with patch.dict(os.environ, {
            'AUTO_RESTORE_S3': 'false',
            'THEO_S3_BACKUP_BUCKET': 'test-bucket',
            'ENV': 'prod'
        }):
            with patch('config.Config') as mock_config:
                mock_config.DATABASE_URL = f'sqlite:///{db_path}'

                with patch('db_backup.DatabaseBackupManager') as mock_manager_class:
                    mock_manager = MagicMock()
                    mock_manager_class.return_value = mock_manager

                    with patch('db_backup.run_migrations'):
                        # Call init_database_backup
                        result = db_backup.init_database_backup()

                        # Verify auto backup was setup in prod (line 227-233)
                        mock_manager.setup_auto_backup.assert_called_once_with(interval_seconds=300)
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)
