#!/usr/bin/env python3
"""
Migration 005: Add last_activity_at column to auth_sessions table

This migration adds the last_activity_at column to track session activity
and enable inactivity-based session timeout.

Run with: python3 backend/migrations/005_add_last_activity_to_sessions.py
Or with custom DB path: python3 backend/migrations/005_add_last_activity_to_sessions.py /path/to/theo.db
"""

import sqlite3
import os
import sys
from datetime import datetime

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

    print(f"[MIGRATION 005] Starting migration...")
    print(f"[MIGRATION 005] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 005] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if last_activity_at column already exists
        cursor.execute("PRAGMA table_info(auth_sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        if "last_activity_at" in columns:
            print("[MIGRATION 005] ✓ last_activity_at column already exists, skipping")
            return True

        # Add last_activity_at column to auth_sessions table
        print("[MIGRATION 005] Adding last_activity_at column to auth_sessions table...")
        cursor.execute("""
            ALTER TABLE auth_sessions
            ADD COLUMN last_activity_at TEXT
        """)

        # Set last_activity_at to created_at for existing sessions
        print("[MIGRATION 005] Initializing last_activity_at for existing sessions...")
        cursor.execute("""
            UPDATE auth_sessions
            SET last_activity_at = created_at
            WHERE last_activity_at IS NULL
        """)

        conn.commit()
        print("[MIGRATION 005] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 005] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
