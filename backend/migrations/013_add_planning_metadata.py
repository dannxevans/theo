#!/usr/bin/env python3
"""
Migration 013: Add planning metadata columns

This migration adds support for context-aware planning:
- planning_metadata column to messages table (stores weather/traffic/calendar data)
- enrichment_data column to actions table (stores enriched context for confirmations)

Run with: python3 backend/migrations/013_add_planning_metadata.py
Or with custom DB path: python3 backend/migrations/013_add_planning_metadata.py /path/to/theo.db
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

    print(f"[MIGRATION 013] Starting migration...")
    print(f"[MIGRATION 013] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 013] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if planning_metadata column already exists in turns table
        cursor.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'planning_metadata' not in columns:
            print("[MIGRATION 013] Adding planning_metadata column to turns table...")
            cursor.execute("""
                ALTER TABLE turns
                ADD COLUMN planning_metadata TEXT
            """)
            print("[MIGRATION 013] ✓ Added planning_metadata column")
        else:
            print("[MIGRATION 013] ✓ planning_metadata column already exists in turns")

        # Check if enrichment_data column already exists in actions table
        cursor.execute("PRAGMA table_info(actions)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'enrichment_data' not in columns:
            print("[MIGRATION 013] Adding enrichment_data column to actions table...")
            cursor.execute("""
                ALTER TABLE actions
                ADD COLUMN enrichment_data TEXT
            """)
            print("[MIGRATION 013] ✓ Added enrichment_data column")
        else:
            print("[MIGRATION 013] ✓ enrichment_data column already exists in actions")

        conn.commit()
        print("[MIGRATION 013] ✓ Migration completed successfully")
        print("[MIGRATION 013] Columns added for context-aware planning")
        return True

    except Exception as e:
        print(f"[MIGRATION 013] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
