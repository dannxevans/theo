#!/usr/bin/env python3
"""
Migration 016: Add routine tracking columns to turns table

This migration adds columns to track routine executions:
- routine_name: Name of the routine executed (e.g., "good_morning")
- routine_actions: JSON array of actions executed in the routine

Run with: python3 backend/migrations/016_add_routine_tracking.py
Or with custom DB path: python3 backend/migrations/016_add_routine_tracking.py /path/to/theo.db
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

    print(f"[MIGRATION 016] Starting migration...")
    print(f"[MIGRATION 016] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 016] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]

        columns_to_add = []
        if "routine_name" not in columns:
            columns_to_add.append("routine_name")
        if "routine_actions" not in columns:
            columns_to_add.append("routine_actions")

        if not columns_to_add:
            print("[MIGRATION 016] ✓ Routine tracking columns already exist, skipping")
            return True

        # Add columns
        for column in columns_to_add:
            print(f"[MIGRATION 016] Adding {column} column to turns table...")
            cursor.execute(f"""
                ALTER TABLE turns
                ADD COLUMN {column} TEXT
            """)

        conn.commit()
        print("[MIGRATION 016] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 016] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
