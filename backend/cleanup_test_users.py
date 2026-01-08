#!/usr/bin/env python3
"""
Cleanup script to remove test users from production database.

This script removes all users with usernames matching the pattern:
- testuser_*
- testuser

Usage:
    python3 backend/cleanup_test_users.py
    python3 backend/cleanup_test_users.py /path/to/theo.db
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
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "theo.db"
    )


def cleanup_test_users():
    """Remove test users from database."""
    DB_PATH = get_db_path()

    print(f"[CLEANUP] Starting test user cleanup...")
    print(f"[CLEANUP] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[CLEANUP] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Find test users
        cursor.execute("""
            SELECT id, username FROM users
            WHERE username LIKE 'testuser_%' OR username = 'testuser'
        """)
        test_users = cursor.fetchall()

        if not test_users:
            print("[CLEANUP] ✓ No test users found")
            return True

        print(f"[CLEANUP] Found {len(test_users)} test user(s):")
        for user_id, username in test_users:
            print(f"  - {username} (ID: {user_id})")

        # Ask for confirmation
        response = input("\nDelete these users? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("[CLEANUP] Cancelled by user")
            return False

        # Delete test users and their related data
        for user_id, username in test_users:
            print(f"[CLEANUP] Deleting user: {username}")

            # Helper function to safely delete from a table
            def safe_delete(table_name):
                try:
                    cursor.execute(f"DELETE FROM {table_name} WHERE user_id = ?", (user_id,))
                except sqlite3.OperationalError as e:
                    if "no such table" not in str(e):
                        raise

            # Delete user's related data (safely ignore missing tables)
            safe_delete("auth_sessions")
            safe_delete("api_keys")
            safe_delete("memories")
            safe_delete("sessions")
            safe_delete("preferences")
            safe_delete("intents")
            safe_delete("routing_preferences")
            safe_delete("feature_providers")
            safe_delete("debug_settings")
            safe_delete("system_prompt_config")
            safe_delete("mode_config")
            safe_delete("proactive_settings")
            safe_delete("user_routines")

            # Finally, delete the user
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

        conn.commit()
        print(f"[CLEANUP] ✓ Successfully deleted {len(test_users)} test user(s)")
        print("[CLEANUP] All related data has been cleaned up")
        return True

    except Exception as e:
        print(f"[CLEANUP] ✗ Cleanup failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = cleanup_test_users()
    sys.exit(0 if success else 1)
