#!/usr/bin/env python3
"""
Migration 006: Add unique constraint to preferences table

This migration adds a unique constraint on (user_id, key) to the preferences table
to ensure each user can only have one value per preference key.

Run with: python3 backend/migrations/006_add_preferences_unique_constraint.py
Or with custom DB path: python3 backend/migrations/006_add_preferences_unique_constraint.py /path/to/theo.db
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

    print(f"[MIGRATION 006] Starting migration...")
    print(f"[MIGRATION 006] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 006] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if the unique constraint already exists
        cursor.execute("PRAGMA index_list(preferences)")
        indexes = cursor.fetchall()

        # Check if uq_user_preference index exists
        for index in indexes:
            if "uq_user_preference" in index[1]:
                print("[MIGRATION 006] ✓ Unique constraint already exists, skipping")
                return True

        print("[MIGRATION 006] Adding unique constraint to preferences table...")

        # SQLite doesn't support adding constraints to existing tables
        # We need to recreate the table

        # 1. Create new table with constraint
        cursor.execute("""
            CREATE TABLE preferences_new (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT,
                UNIQUE(user_id, key)
            )
        """)

        # 2. Copy data from old table
        cursor.execute("""
            INSERT INTO preferences_new (user_id, key, value, updated_at)
            SELECT user_id, key, value, updated_at
            FROM preferences
        """)

        # 3. Drop old table
        cursor.execute("DROP TABLE preferences")

        # 4. Rename new table
        cursor.execute("ALTER TABLE preferences_new RENAME TO preferences")

        conn.commit()
        print("[MIGRATION 006] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 006] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
