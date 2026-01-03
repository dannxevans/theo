#!/usr/bin/env python3
"""
Pre-migration cleanup for Migration 018: Remove duplicate 'local' user_id preferences

This script removes preferences entries with user_id='local' that would conflict
with existing user_id=1 entries when migration 018 converts 'local' to 1.

Run with: python3 backend/migrations/018_1_cleanup_duplicate_preferences.py
Or with custom DB path: python3 backend/migrations/018_1_cleanup_duplicate_preferences.py /path/to/theo.db
"""

import sqlite3
import os
import sys

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
    """Execute the cleanup (using standard migration function name)."""
    return run_cleanup()

def run_cleanup():
    """Execute the cleanup."""
    DB_PATH = get_db_path()

    print(f"[CLEANUP 018] Starting duplicate preferences cleanup...")
    print(f"[CLEANUP 018] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[CLEANUP 018] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if preferences table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='preferences'
        """)

        if not cursor.fetchone():
            print("[CLEANUP 018] ✓ preferences table doesn't exist yet, skipping")
            return True

        # Tables that might have both 'local' and user_id=1 entries
        # These tables have UNIQUE constraints on user_id (or user_id + key)
        tables_to_clean = [
            ('preferences', 'key'),  # UNIQUE(user_id, key)
            ('proactive_settings', None),  # UNIQUE(user_id)
            ('system_prompt_config', None),  # UNIQUE(user_id)
        ]

        total_deleted = 0

        for table_name, key_column in tables_to_clean:
            # Check if table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name=?
            """, (table_name,))

            if not cursor.fetchone():
                print(f"[CLEANUP 018] ✓ {table_name} table doesn't exist, skipping")
                continue

            # Check if there are 'local' entries
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE user_id = 'local'
            """)
            local_count = cursor.fetchone()[0]

            if local_count == 0:
                print(f"[CLEANUP 018] ✓ No 'local' entries in {table_name}")
                continue

            # Check if user_id=1 exists in this table
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name}
                WHERE user_id = 1
            """)
            user1_count = cursor.fetchone()[0]

            if user1_count == 0:
                # No conflict - migration will safely convert 'local' → 1
                print(f"[CLEANUP 018] ✓ {table_name}: {local_count} 'local' entries will be migrated (no conflict)")
                continue

            # Both 'local' and user_id=1 exist - delete 'local' entries
            cursor.execute(f"""
                DELETE FROM {table_name}
                WHERE user_id = 'local'
            """)
            deleted = cursor.rowcount
            total_deleted += deleted
            print(f"[CLEANUP 018] ✓ {table_name}: Deleted {deleted} 'local' entries (user_id=1 exists)")

        if total_deleted > 0:
            conn.commit()
            print(f"[CLEANUP 018] ✓ Total deleted: {total_deleted} 'local' entries across all tables")
        else:
            print("[CLEANUP 018] ✓ No duplicates to delete")

        print("[CLEANUP 018] ✓ Cleanup completed successfully")
        return True

    except Exception as e:
        print(f"[CLEANUP 018] ✗ Cleanup failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_cleanup()
    sys.exit(0 if success else 1)
