"""
Database backup and restore utilities for S3
Automatically backs up SQLite database to S3 and restores on startup
"""
import os
import shutil
import logging
from pathlib import Path
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    def __init__(self, db_path: str, s3_bucket: str = None, s3_key: str = "theo/theo.db"):
        """
        Initialize database backup manager

        Args:
            db_path: Local path to SQLite database
            s3_bucket: S3 bucket name (if None, backups are disabled)
            s3_key: S3 object key for the database backup
        """
        self.db_path = Path(db_path)
        self.s3_bucket = s3_bucket
        self.s3_key = s3_key
        self.enabled = bool(s3_bucket)

        if self.enabled:
            self.s3_client = boto3.client('s3')
            logger.info(f"Database backups enabled to s3://{s3_bucket}/{s3_key}")
        else:
            logger.info("Database backups disabled (no S3 bucket configured)")

    def restore_from_s3(self):
        """Restore database from S3 if it exists"""
        if not self.enabled:
            return False

        try:
            # Create parent directory if it doesn't exist
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Download from S3
            logger.info(f"Attempting to restore database from s3://{self.s3_bucket}/{self.s3_key}")
            self.s3_client.download_file(
                self.s3_bucket,
                self.s3_key,
                str(self.db_path)
            )
            logger.info(f"Successfully restored database from S3")
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info("No existing database backup found in S3 (first deployment)")
            else:
                logger.error(f"Failed to restore database from S3: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error restoring database: {e}")
            return False

    def backup_to_s3(self):
        """Backup database to S3"""
        if not self.enabled:
            return False

        if not self.db_path.exists():
            logger.warning(f"Database file {self.db_path} does not exist, skipping backup")
            return False

        try:
            logger.info(f"Backing up database to s3://{self.s3_bucket}/{self.s3_key}")
            self.s3_client.upload_file(
                str(self.db_path),
                self.s3_bucket,
                self.s3_key
            )
            logger.info("Database backed up successfully to S3")
            return True

        except Exception as e:
            logger.error(f"Failed to backup database to S3: {e}")
            return False

    def setup_auto_backup(self, interval_seconds: int = 300):
        """
        Setup automatic periodic backups (every 5 minutes by default)

        This should be called in a background thread
        """
        import time
        import threading

        def backup_loop():
            while True:
                time.sleep(interval_seconds)
                self.backup_to_s3()

        if self.enabled:
            thread = threading.Thread(target=backup_loop, daemon=True)
            thread.start()
            logger.info(f"Started automatic database backup every {interval_seconds} seconds")


def run_migrations(db_path: str):
    """
    Run all pending database migrations

    Args:
        db_path: Path to the SQLite database file
    """
    import sys
    import importlib.util

    migrations_dir = Path(__file__).parent / "migrations"

    if not migrations_dir.exists():
        logger.warning(f"Migrations directory not found: {migrations_dir}")
        return False

    # Get all migration files in order
    migration_files = [
        "001_add_action_tables.py",
        "002_add_turns_metadata.py",
        "003_add_mode_to_sessions.py",
        "007_configurable_intents_and_session_timeout.py",
        "008_add_suitable_for_official_to_providers.py"
    ]

    # Filter to only existing files
    existing_migrations = []
    for filename in migration_files:
        filepath = migrations_dir / filename
        if filepath.exists():
            existing_migrations.append(filepath)

    if not existing_migrations:
        logger.info("No migration files found")
        return True

    logger.info(f"Running {len(existing_migrations)} migration(s)")

    # Run each migration
    all_success = True
    for filepath in existing_migrations:
        try:
            # Load the migration module
            spec = importlib.util.spec_from_file_location("migration", str(filepath))
            module = importlib.util.module_from_spec(spec)

            # Temporarily override sys.argv to pass db_path
            original_argv = sys.argv.copy()
            sys.argv = [sys.argv[0], db_path]

            try:
                spec.loader.exec_module(module)
                success = module.run_migration()
                if success:
                    logger.info(f"✓ Migration {filepath.name} completed")
                else:
                    logger.warning(f"⚠ Migration {filepath.name} skipped or failed")
                    all_success = False
            finally:
                # Restore original argv
                sys.argv = original_argv

        except Exception as e:
            logger.error(f"ERROR running migration {filepath.name}: {e}")
            all_success = False

    return all_success


def init_database_backup():
    """Initialize database backup/restore on application startup"""
    from config import Config

    # Get configuration
    db_url = Config.DATABASE_URL
    s3_bucket = os.getenv("THEO_S3_BACKUP_BUCKET")
    s3_key = os.getenv("THEO_S3_BACKUP_KEY", "theo/theo.db")

    # Extract database path from SQLite URL
    # Format: sqlite:///path/to/db.db
    if not db_url.startswith("sqlite:///"):
        logger.info("Not using SQLite, database backups not applicable")
        return None

    db_path = db_url.replace("sqlite:///", "")

    # Initialize backup manager
    manager = DatabaseBackupManager(db_path, s3_bucket, s3_key)

    # Restore from S3 on startup
    restored = manager.restore_from_s3()

    # Run migrations after restore (or on fresh database)
    # This ensures the database schema is up-to-date before the app starts using it
    if os.path.exists(db_path):
        logger.info("Running database migrations")
        run_migrations(db_path)

    # Setup automatic backups every 5 minutes
    manager.setup_auto_backup(interval_seconds=300)

    return manager
