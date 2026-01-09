"""
Database migrations and utilities.

DEPRECATED: S3 backup functionality has been removed (2026-01-06).
The application now runs on Unraid with native backup solutions.
This module is retained only for the migration runner (run_migrations).
"""
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseBackupManager:
    """
    DEPRECATED: S3 backup manager is no longer used.
    Kept for backwards compatibility but will not be instantiated.
    """
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
        "004_add_is_action_to_intents.py",
        "005_add_last_activity_to_sessions.py",
        "006_add_preferences_unique_constraint.py",
        "007_configurable_intents_and_session_timeout.py",
        "008_add_suitable_for_official_to_providers.py",
        "009_add_fallback_provider_to_routing.py",
        "010_add_circuit_breaker_cooldown.py",
        "011_add_feature_providers.py",
        "012_add_feature_provider_usage_logs.py",
        "013_add_planning_metadata.py",
        "014_add_proactive_settings.py",
        "015_add_proactive_tracking_tables.py",
        "016_add_routine_tracking.py",
        "017_add_user_routines.py",
        "018_1_cleanup_duplicate_preferences.py",  # Pre-migration cleanup
        "018_standardize_user_id_to_integer.py",
        "019_create_debug_logs.py",
        "020_add_api_keys.py",  # Add api_keys table for API key authentication
        "021_add_full_request_context.py",  # Add full_request_context column for LLM prompt debugging
        "022_add_whoop_integration.py",  # Add WHOOP integration tables (credentials, settings, tracking)
        "023_add_whoop_stress_notifications.py",  # Add stress notifications to WHOOP settings
        "024_add_stress_notification_time.py",  # Add stress notification time to WHOOP settings
        "025_add_oauth_config_to_feature_providers.py",  # Add OAuth config storage to feature providers
        "026_add_session_folders.py",  # Add session folders for organization and archiving
        "027_add_whoop_intent.py",  # Add WHOOP intent for fitness tracking queries
        "028_fix_good_night_routine_timeframe.py",  # Fix Good Night routine calendar timeframe (issue #328)
        "029_add_user_name_email.py",  # Add name and email columns to users table for user management
        "030_add_work_mode_ip_config.py",  # Add work_mode_ip_config table for IP-based Work Mode access control (issue #296)
        "031_add_plex_integration.py"  # Add Plex Media Server integration tables (credentials, settings, tracking) (issue #340)
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


def cleanup_test_users_silent(db_path):
    """
    Remove test users from database (non-interactive version for automatic cleanup).

    Args:
        db_path: Path to the SQLite database file
    """
    import sqlite3

    logger.info("[CLEANUP] Starting automatic test user cleanup")

    if not os.path.exists(db_path):
        logger.warning(f"[CLEANUP] Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Find test users
        cursor.execute("""
            SELECT id, username FROM users
            WHERE username LIKE 'testuser_%' OR username = 'testuser' OR username = 'voicetest_user'
        """)
        test_users = cursor.fetchall()

        if not test_users:
            logger.info("[CLEANUP] ✓ No test users found")
            return

        logger.info(f"[CLEANUP] Found {len(test_users)} test user(s) to clean up")

        # Delete test users and their related data
        for user_id, username in test_users:
            logger.info(f"[CLEANUP] Deleting test user: {username}")

            # Helper function to safely delete from a table
            def safe_delete(table_name):
                try:
                    cursor.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (user_id,))
                except sqlite3.OperationalError as e:
                    if "no such table" not in str(e):
                        raise

            # Delete user's related data (safely ignore missing tables)
            safe_delete("auth_sessions")
            safe_delete("api_keys")
            safe_delete("memories")
            safe_delete("sessions")
            safe_delete("preferences")
            safe_delete("intents")
            safe_delete("routing_preferences")
            safe_delete("feature_providers")
            safe_delete("debug_settings")
            safe_delete("system_prompt_config")
            safe_delete("mode_config")
            safe_delete("proactive_settings")
            safe_delete("user_routines")

            # Finally, delete the user
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()
        logger.info(f"[CLEANUP] ✓ Successfully deleted {len(test_users)} test user(s)")

    except Exception as e:
        logger.error(f"[CLEANUP] ✗ Cleanup failed: {e}")
        conn.rollback()

    finally:
        conn.close()


def init_database_backup():
    """
    Initialize database migrations on application startup.

    Note: S3 backup functionality has been removed as the application
    now runs exclusively on Unraid with native backup solutions.
    """
    from config import Config

    # Get configuration
    db_url = Config.DATABASE_URL

    # Extract database path from SQLite URL
    # Format: sqlite:///path/to/db.db
    if not db_url.startswith("sqlite:///"):
        logger.info("Not using SQLite, database migrations not applicable")
        return None

    db_path = db_url.replace("sqlite:///", "")

    logger.info("AWS S3 backups disabled - using Unraid native backup solutions")

    # Run migrations on fresh database or after restore
    # This ensures the database schema is up-to-date before the app starts using it
    if os.path.exists(db_path):
        logger.info("Running database migrations")
        run_migrations(db_path)

        # Run test user cleanup after migrations
        cleanup_test_users_silent(db_path)
    else:
        logger.info(f"Database not found at {db_path}, will be created on first use")

    return None
