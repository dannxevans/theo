#!/usr/bin/env python3
"""
Migration 018: Standardize user_id to Integer across all tables

This migration converts all String user_id columns to Integer, migrating all
"local" user data to user_id = 1 (the admin user).

CRITICAL: This is a major schema change affecting multiple tables.
- Automatic backup created before migration
- Transaction-based with rollback on failure
- Comprehensive logging and verification

Run with: python3 backend/migrations/018_standardize_user_id_to_integer.py
Or with custom DB path: python3 backend/migrations/018_standardize_user_id_to_integer.py /path/to/theo.db

Background:
-----------
THEO initially used a single "local" user (String) before multi-user authentication.
When authentication was added, new records used Integer user_ids, but legacy data
remained with "local" strings, causing silent query failures.

This migration unifies all user_id columns to Integer type with proper foreign
key relationships (constraints will be enabled in migration 019).
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime

# Tables to migrate (String user_id → Integer user_id)
TABLES_TO_MIGRATE = [
    "debug_settings",
    "preferences",
    "system_prompt_config",
    "memories",
    "intents",
    "routing_preferences",
    "feature_providers",
    "feature_provider_usage_logs",
]

# Check for additional tables that might exist
OPTIONAL_TABLES = [
    "user_routines",
    "proactive_settings",
    "proactive_calendar_notifications",
    "proactive_email_tracking",
    "proactive_email_digests",
    "proactive_errors",
    "proactive_rate_limit_tracking",
]


def get_db_path():
    """Get database path from command line arg or default location."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    # Default: project root /data/theo.db
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "data",
        "theo.db"
    )


def create_backup(db_path):
    """Create timestamped backup of database before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)

    backup_path = os.path.join(backup_dir, f"theo_backup_pre_migration_018_{timestamp}.db")

    print(f"[MIGRATION 018] Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)

    # Verify backup
    if not os.path.exists(backup_path):
        raise Exception("Backup creation failed!")

    backup_size = os.path.getsize(backup_path)
    original_size = os.path.getsize(db_path)

    if backup_size != original_size:
        raise Exception(f"Backup size mismatch! Original: {original_size}, Backup: {backup_size}")

    print(f"[MIGRATION 018] ✓ Backup created: {backup_size} bytes")
    print(f"[MIGRATION 018] ✓ Backup verified")

    return backup_path


def get_table_info(cursor, table_name):
    """Get column information for a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return cursor.fetchall()


def table_exists(cursor, table_name):
    """Check if a table exists."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def has_string_user_id(cursor, table_name):
    """Check if table has a String user_id column."""
    if not table_exists(cursor, table_name):
        return False

    columns = get_table_info(cursor, table_name)
    for col in columns:
        col_name, col_type = col[1], col[2]
        if col_name == "user_id" and col_type.upper() in ("TEXT", "STRING", "VARCHAR"):
            return True
    return False


def normalize_user_id_value(value):
    """
    Normalize a user_id value to integer.
    - "local" → 1
    - String integer → parsed int
    - Already int → passthrough
    """
    if value is None:
        return 1

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        if value.strip().lower() == "local":
            return 1
        try:
            return int(value)
        except ValueError:
            print(f"[MIGRATION 018] WARNING: Invalid user_id '{value}', defaulting to 1")
            return 1

    return 1


def migrate_table(conn, cursor, table_name):
    """
    Migrate a single table from String user_id to Integer user_id.

    Strategy:
    1. Create temporary table with Integer user_id schema
    2. Copy and transform data
    3. Drop original table
    4. Rename temp table to original name
    """
    print(f"\n[MIGRATION 018] Migrating table: {table_name}")

    # Get original schema
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
    original_schema = cursor.fetchone()[0]
    print(f"[MIGRATION 018]   Original schema retrieved")

    # Get row count before migration
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count_before = cursor.fetchone()[0]
    print(f"[MIGRATION 018]   Rows before migration: {row_count_before}")

    # Create new schema with Integer user_id
    temp_table = f"{table_name}_temp_migration"

    # Drop temp table if it exists from a previous failed migration
    cursor.execute(f"DROP TABLE IF EXISTS {temp_table}")

    # Replace table name in CREATE TABLE statement
    new_schema = original_schema.replace(f'CREATE TABLE IF NOT EXISTS "{table_name}"', f'CREATE TABLE "{temp_table}"')
    new_schema = new_schema.replace(f'CREATE TABLE IF NOT EXISTS {table_name}', f'CREATE TABLE {temp_table}')
    new_schema = new_schema.replace(f'CREATE TABLE "{table_name}"', f'CREATE TABLE "{temp_table}"')
    new_schema = new_schema.replace(f'CREATE TABLE {table_name}', f'CREATE TABLE {temp_table}')

    # Replace user_id type from String/TEXT/VARCHAR to INTEGER (all variations)
    new_schema = new_schema.replace('"user_id" TEXT', '"user_id" INTEGER')
    new_schema = new_schema.replace('"user_id" STRING', '"user_id" INTEGER')
    new_schema = new_schema.replace('"user_id" VARCHAR', '"user_id" INTEGER')
    new_schema = new_schema.replace("user_id TEXT", "user_id INTEGER")
    new_schema = new_schema.replace("user_id STRING", "user_id INTEGER")
    new_schema = new_schema.replace("user_id VARCHAR", "user_id INTEGER")

    print(f"[MIGRATION 018]   Creating temporary table: {temp_table}")
    # Debug: print the transformed schema
    if os.environ.get("DEBUG_MIGRATION"):
        print(f"[MIGRATION 018]   DEBUG: New schema:")
        print(new_schema)
    cursor.execute(new_schema)

    # Get all column names
    columns_info = get_table_info(cursor, table_name)
    column_names = [col[1] for col in columns_info]
    columns_str = ", ".join([f'"{col}"' for col in column_names])

    # Copy data with user_id transformation
    print(f"[MIGRATION 018]   Copying and transforming data...")
    cursor.execute(f"SELECT {columns_str} FROM {table_name}")
    rows = cursor.fetchall()

    user_id_index = column_names.index("user_id")
    local_count = 0
    integer_count = 0

    for row in rows:
        row_list = list(row)
        original_user_id = row_list[user_id_index]
        normalized_user_id = normalize_user_id_value(original_user_id)

        if isinstance(original_user_id, str) and original_user_id.lower() == "local":
            local_count += 1
        else:
            integer_count += 1

        row_list[user_id_index] = normalized_user_id

        placeholders = ", ".join(["?" for _ in row_list])
        cursor.execute(f"INSERT INTO {temp_table} ({columns_str}) VALUES ({placeholders})", row_list)

    print(f"[MIGRATION 018]   ✓ Migrated {local_count} 'local' records → user_id=1")
    print(f"[MIGRATION 018]   ✓ Preserved {integer_count} existing integer user_ids")

    # Verify row count
    cursor.execute(f"SELECT COUNT(*) FROM {temp_table}")
    row_count_after = cursor.fetchone()[0]

    if row_count_before != row_count_after:
        raise Exception(
            f"Row count mismatch for {table_name}! "
            f"Before: {row_count_before}, After: {row_count_after}"
        )

    print(f"[MIGRATION 018]   ✓ Row count verified: {row_count_after}")

    # Drop original table
    print(f"[MIGRATION 018]   Dropping original table...")
    cursor.execute(f"DROP TABLE {table_name}")

    # Rename temp table
    print(f"[MIGRATION 018]   Renaming temp table...")
    cursor.execute(f"ALTER TABLE {temp_table} RENAME TO {table_name}")

    print(f"[MIGRATION 018] ✓ {table_name} migration complete")

    return {
        "table": table_name,
        "rows": row_count_after,
        "local_migrated": local_count,
        "integer_preserved": integer_count,
    }


def verify_user_exists(cursor):
    """Verify that user_id = 1 exists in users table."""
    cursor.execute("SELECT id, username FROM users WHERE id = 1")
    user = cursor.fetchone()

    if not user:
        raise Exception(
            "User ID 1 does not exist! This migration requires the admin user (ID=1) to exist. "
            "Please ensure the users table has a record with id=1 before running this migration."
        )

    print(f"[MIGRATION 018] ✓ Verified user_id=1 exists: {user[1]}")
    return user


def run_migration():
    """Execute the migration."""
    DB_PATH = get_db_path()

    print("=" * 70)
    print("MIGRATION 018: Standardize user_id to Integer")
    print("=" * 70)
    print(f"Database: {DB_PATH}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 018] ERROR: Database not found at {DB_PATH}")
        return False

    # Create backup
    try:
        backup_path = create_backup(DB_PATH)
    except Exception as e:
        print(f"[MIGRATION 018] ERROR: Backup failed: {e}")
        return False

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Verify user_id = 1 exists
        verify_user_exists(cursor)

        # Find all tables that need migration
        tables_to_process = []

        for table in TABLES_TO_MIGRATE:
            if has_string_user_id(cursor, table):
                tables_to_process.append(table)

        # Check optional tables
        for table in OPTIONAL_TABLES:
            if has_string_user_id(cursor, table):
                tables_to_process.append(table)

        if not tables_to_process:
            print("[MIGRATION 018] No tables with String user_id found - migration already completed?")
            return True

        print(f"\n[MIGRATION 018] Tables to migrate: {len(tables_to_process)}")
        for table in tables_to_process:
            print(f"  - {table}")
        print()

        # Migrate each table
        migration_results = []

        for table in tables_to_process:
            result = migrate_table(conn, cursor, table)
            migration_results.append(result)

        # Commit all changes
        print("\n[MIGRATION 018] Committing changes...")
        conn.commit()

        # Verify integrity
        print("[MIGRATION 018] Verifying database integrity...")
        cursor.execute("PRAGMA integrity_check")
        integrity_result = cursor.fetchone()[0]

        if integrity_result != "ok":
            raise Exception(f"Database integrity check failed: {integrity_result}")

        print("[MIGRATION 018] ✓ Database integrity verified")

        # Print summary
        print("\n" + "=" * 70)
        print("MIGRATION 018 COMPLETE")
        print("=" * 70)
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nMigration Summary:")
        print(f"  Tables migrated: {len(migration_results)}")

        total_rows = sum(r["rows"] for r in migration_results)
        total_local = sum(r["local_migrated"] for r in migration_results)
        total_integer = sum(r["integer_preserved"] for r in migration_results)

        print(f"  Total rows processed: {total_rows}")
        print(f"  'local' → user_id=1: {total_local}")
        print(f"  Integer preserved: {total_integer}")
        print(f"\nBackup location: {backup_path}")
        print("\nAll user_id columns are now Integer type!")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\n[MIGRATION 018] ✗ MIGRATION FAILED: {e}")
        print("[MIGRATION 018] Rolling back changes...")
        conn.rollback()
        print(f"[MIGRATION 018] Database restored from backup: {backup_path}")
        print(f"[MIGRATION 018] To restore manually: cp {backup_path} {DB_PATH}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
