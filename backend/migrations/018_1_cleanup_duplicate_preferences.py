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

        # Get all preferences with user_id='local'
        cursor.execute("""
            SELECT user_id, key, value FROM preferences
            WHERE user_id = 'local'
        """)
        local_prefs = cursor.fetchall()

        if not local_prefs:
            print("[CLEANUP 018] ✓ No 'local' user_id preferences found, skipping")
            return True

        print(f"[CLEANUP 018] Found {len(local_prefs)} 'local' user_id preferences")

        # For each 'local' preference, check if user_id=1 has the same key
        duplicates_to_delete = []
        for user_id, key, value in local_prefs:
            cursor.execute("""
                SELECT 1 FROM preferences
                WHERE user_id = 1 AND key = ?
            """, (key,))

            if cursor.fetchone():
                # Duplicate exists - delete the 'local' version
                duplicates_to_delete.append(key)
                print(f"[CLEANUP 018]   Duplicate found: {key} (will delete 'local' version)")
            else:
                # No duplicate - migration 018 will safely convert this to user_id=1
                print(f"[CLEANUP 018]   No conflict: {key} (will be migrated)")

        if duplicates_to_delete:
            # Delete duplicate 'local' preferences
            placeholders = ','.join('?' * len(duplicates_to_delete))
            cursor.execute(f"""
                DELETE FROM preferences
                WHERE user_id = 'local' AND key IN ({placeholders})
            """, duplicates_to_delete)

            conn.commit()
            print(f"[CLEANUP 018] ✓ Deleted {len(duplicates_to_delete)} duplicate 'local' preferences")
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
