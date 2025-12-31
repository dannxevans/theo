#!/usr/bin/env python3
"""
Migration 004: Add is_action column to intents table

This migration adds the is_action column to the intents table to distinguish
action intents (calendar, email, etc.) from conversational intents.

Run with: python3 backend/migrations/004_add_is_action_to_intents.py
Or with custom DB path: python3 backend/migrations/004_add_is_action_to_intents.py /path/to/theo.db
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

    print(f"[MIGRATION 004] Starting migration...")
    print(f"[MIGRATION 004] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 004] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if is_action column already exists
        cursor.execute("PRAGMA table_info(intents)")
        columns = [row[1] for row in cursor.fetchall()]

        if "is_action" in columns:
            print("[MIGRATION 004] ✓ is_action column already exists, skipping")
            return True

        # Add is_action column to intents table
        print("[MIGRATION 004] Adding is_action column to intents table...")
        cursor.execute("""
            ALTER TABLE intents
            ADD COLUMN is_action INTEGER DEFAULT 0
        """)

        # Update existing action intents to set is_action = 1
        print("[MIGRATION 004] Marking existing action intents...")
        action_intent_ids = [
            "read_calendar",
            "book_appointment",
            "update_appointment",
            "cancel_appointment",
            "read_email",
            "compose_email",
            "approve_confirmation",
            "reject_confirmation"
        ]

        for intent_id in action_intent_ids:
            cursor.execute("""
                UPDATE intents
                SET is_action = 1
                WHERE id = ?
            """, (intent_id,))

        conn.commit()
        print("[MIGRATION 004] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 004] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
