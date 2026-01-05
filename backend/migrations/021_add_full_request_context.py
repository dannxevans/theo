#!/usr/bin/env python3
"""
Migration 021: Add full_request_context column to turns table.

This column stores the complete message array sent to the LLM, including:
- System prompt
- Previous conversation context
- Planning metadata enrichment
- The actual user message

This enables debugging of unexpected LLM responses by viewing the exact prompt.

Run with: python3 backend/migrations/021_add_full_request_context.py
Or with custom DB path: python3 backend/migrations/021_add_full_request_context.py /path/to/theo.db
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

    print(f"[MIGRATION 021] Starting migration...")
    print(f"[MIGRATION 021] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 021] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]

        if "full_request_context" in columns:
            print("[MIGRATION 021] ✓ full_request_context column already exists, skipping")
            return True

        # Add the new column (nullable, will be populated going forward)
        print("[MIGRATION 021] Adding full_request_context column to turns table...")
        cursor.execute("""
            ALTER TABLE turns
            ADD COLUMN full_request_context TEXT
        """)

        conn.commit()
        print("[MIGRATION 021] ✓ Added full_request_context column")
        print("[MIGRATION 021] Migration 021 complete")
        return True

    except Exception as e:
        conn.rollback()
        print(f"[MIGRATION 021] ERROR: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
