#!/usr/bin/env python3
"""
Migration 017: Add user_routines table

This migration creates a table for user-defined custom routines.

Run with: python3 backend/migrations/017_add_user_routines.py
Or with custom DB path: python3 backend/migrations/017_add_user_routines.py /path/to/theo.db
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

    print(f"[MIGRATION 017] Starting migration...")
    print(f"[MIGRATION 017] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 017] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_routines'
        """)

        if cursor.fetchone():
            print("[MIGRATION 017] ✓ user_routines table already exists, skipping")
            return True

        # Create user_routines table
        print("[MIGRATION 017] Creating user_routines table...")
        cursor.execute("""
            CREATE TABLE user_routines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                triggers TEXT NOT NULL,
                actions TEXT NOT NULL,
                consolidation_prompt TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for user_id lookups
        cursor.execute("""
            CREATE INDEX idx_user_routines_user_id
            ON user_routines(user_id)
        """)

        conn.commit()
        print("[MIGRATION 017] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 017] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
