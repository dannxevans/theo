#!/usr/bin/env python3
"""
Migration 009: Add fallback_provider_id column to routing_preferences table

This migration adds the fallback_provider_id column to support configurable
fallback providers when the primary provider fails (e.g., quota limits, API errors).

Run with: python3 backend/migrations/009_add_fallback_provider_to_routing.py
Or with custom DB path: python3 backend/migrations/009_add_fallback_provider_to_routing.py /path/to/theo.db
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

    print(f"[MIGRATION 009] Starting migration...")
    print(f"[MIGRATION 009] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 009] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if fallback_provider_id column already exists
        cursor.execute("PRAGMA table_info(routing_preferences)")
        columns = [row[1] for row in cursor.fetchall()]

        if "fallback_provider_id" in columns:
            print("[MIGRATION 009] ✓ fallback_provider_id column already exists, skipping")
            return True

        # Add fallback_provider_id column to routing_preferences table
        print("[MIGRATION 009] Adding fallback_provider_id column to routing_preferences table...")
        cursor.execute("""
            ALTER TABLE routing_preferences
            ADD COLUMN fallback_provider_id TEXT DEFAULT NULL
        """)

        conn.commit()
        print("[MIGRATION 009] ✓ Migration completed successfully")
        print("[MIGRATION 009] Users can now configure fallback providers in Routing Settings")
        return True

    except Exception as e:
        print(f"[MIGRATION 009] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
