#!/usr/bin/env python3
"""
Migration 033: Add category column to intents table

This migration adds the category column to the intents table to distinguish
between user-defined intents, action intents, and orchestration intents.

Category values:
- "user": User-defined intents (fully editable, routable)
- "action": Action intents (hidden from routing rules, use system routing)
- "orchestration": Orchestration intents (read-only display, routable)

Run with: python3 backend/migrations/033_add_category_to_intents.py
Or with custom DB path: python3 backend/migrations/033_add_category_to_intents.py /path/to/theo.db
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

    print(f"[MIGRATION 033] Starting migration...")
    print(f"[MIGRATION 033] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 033] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if category column already exists
        cursor.execute("PRAGMA table_info(intents)")
        columns = [row[1] for row in cursor.fetchall()]

        if "category" in columns:
            print("[MIGRATION 033] ✓ category column already exists, skipping")
            return True

        # Add category column to intents table
        print("[MIGRATION 033] Adding category column to intents table...")
        cursor.execute("""
            ALTER TABLE intents
            ADD COLUMN category TEXT DEFAULT 'user'
        """)

        # Update existing action intents to category='action'
        print("[MIGRATION 033] Updating existing action intents to category='action'...")
        cursor.execute("""
            UPDATE intents
            SET category = 'action'
            WHERE is_action = 1
        """)

        # Ensure remaining intents have category='user'
        cursor.execute("""
            UPDATE intents
            SET category = 'user'
            WHERE category IS NULL OR category = ''
        """)

        conn.commit()
        print("[MIGRATION 033] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 033] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
