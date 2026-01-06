#!/usr/bin/env python3
"""
Migration 027: Add WHOOP intent for fitness tracking queries

This migration adds the 'whoop' intent to enable routing of WHOOP fitness tracker
queries to the WHOOPHandlers action handler instead of generic LLM responses.

The intent is marked as an action intent (is_action=1) so queries like:
- "Check last night's sleep data"
- "How did I sleep?"
- "What's my recovery score?"
- "How was my workout?"

Will be routed to the WHOOP action handler for data retrieval and formatting.

Run with: python3 backend/migrations/027_add_whoop_intent.py
Or with custom DB path: python3 backend/migrations/027_add_whoop_intent.py /path/to/theo.db
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

    print(f"[MIGRATION 027] Starting migration...")
    print(f"[MIGRATION 027] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 027] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if intents table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='intents'
        """)
        if not cursor.fetchone():
            print(f"[MIGRATION 027] ERROR: intents table does not exist")
            return False

        # Check if whoop intent already exists for any user
        cursor.execute("SELECT COUNT(*) FROM intents WHERE id = 'whoop'")
        existing_count = cursor.fetchone()[0]

        if existing_count > 0:
            print(f"[MIGRATION 027] WHOOP intent already exists for {existing_count} user(s), skipping")
            return True

        # Get all user IDs
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchall()

        if not users:
            print(f"[MIGRATION 027] WARNING: No users found, skipping intent creation")
            return True

        # Insert WHOOP intent for each user
        inserted_count = 0
        for (user_id,) in users:
            cursor.execute("""
                INSERT INTO intents (id, user_id, name, keywords, is_action, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """, (
                'whoop',
                user_id,
                'WHOOP Fitness Data',
                'whoop,sleep,recovery,workout,hrv,strain',
                1,  # is_action=1 (routes to action handler)
                1   # enabled=1
            ))
            inserted_count += 1

        conn.commit()
        print(f"[MIGRATION 027] Successfully added WHOOP intent for {inserted_count} user(s)")
        print(f"[MIGRATION 027] Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 027] ERROR: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
