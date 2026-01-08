#!/usr/bin/env python3
"""
Migration 029: Add name and email columns to users table

This migration adds optional name and email fields to the users table to support:
- User profile information in the user management system
- Identifying users by name instead of just username
- Contact information for administrative purposes

Run with: python3 backend/migrations/029_add_user_name_email.py
Or with custom DB path: python3 backend/migrations/029_add_user_name_email.py /path/to/theo.db
"""

import sqlite3
import os
import sys

# Determine database path
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

def run_migration():
    """Execute the migration."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 029] Starting migration...")
    print(f"[MIGRATION 029] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 029] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if users table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='users'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 029] ERROR: users table does not exist")
            return False

        # Check if columns already exist
        cursor.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in cursor.fetchall()]

        columns_to_add = []
        if "name" not in columns:
            columns_to_add.append(("name", "TEXT"))
        if "email" not in columns:
            columns_to_add.append(("email", "TEXT"))

        if not columns_to_add:
            print("[MIGRATION 029] ✓ Columns already exist, skipping")
            return True

        # Add the new columns
        for column_name, column_type in columns_to_add:
            print(f"[MIGRATION 029] Adding column: {column_name}")
            cursor.execute(f"""
                ALTER TABLE users
                ADD COLUMN {column_name} {column_type}
            """)

        conn.commit()
        print("[MIGRATION 029] ✓ Migration completed successfully")
        print("[MIGRATION 029] Added name and email columns to users table")
        print("[MIGRATION 029] Both columns are nullable (optional)")
        return True

    except Exception as e:
        print(f"[MIGRATION 029] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
