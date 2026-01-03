#!/usr/bin/env python3
"""
Debug Console Recovery Script

Disables debug logging and clears debug logs to help recover from a crashed container.
Run this script when the container is stuck due to debug log flooding.

Usage:
    python3 backend/scripts/debug_recovery.py

This will:
1. Disable debug logging (set debug_enabled = false)
2. Clear all debug logs from the database
3. Reset all logger filters to off (default safe state)
"""

import sys
import os
import sqlite3

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config import Config


def recover_debug():
    """Disable debug and clear logs to recover from crash."""

    # Get database path
    db_url = Config.DATABASE_URL
    if db_url.startswith('sqlite:///'):
        db_path = db_url.replace('sqlite:///', '')
    else:
        db_path = db_url.split('sqlite:///')[-1]

    print(f"[RECOVERY] Connecting to database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 1. Disable debug logging
        print("[RECOVERY] Disabling debug logging...")
        cursor.execute("""
            UPDATE preferences
            SET value = 'false'
            WHERE user_id = 1 AND key = 'debug_enabled'
        """)
        affected = cursor.rowcount
        if affected == 0:
            # Insert if doesn't exist
            cursor.execute("""
                INSERT INTO preferences (user_id, key, value)
                VALUES (1, 'debug_enabled', 'false')
            """)
            print("[RECOVERY] ✓ Created debug_enabled = false preference")
        else:
            print(f"[RECOVERY] ✓ Disabled debug logging ({affected} rows updated)")

        # 2. Reset all logger filters to OFF (safe state)
        print("[RECOVERY] Resetting logger filters to safe defaults...")
        filters = [
            'debug_filter_sqlalchemy',
            'debug_filter_werkzeug',
            'debug_filter_urllib3',
            'debug_filter_botocore'
        ]

        for filter_key in filters:
            cursor.execute("""
                UPDATE preferences
                SET value = 'false'
                WHERE user_id = 1 AND key = ?
            """, (filter_key,))
            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO preferences (user_id, key, value)
                    VALUES (1, ?, 'false')
                """, (filter_key,))
        print(f"[RECOVERY] ✓ Reset {len(filters)} logger filters to OFF")

        # 3. Clear debug logs
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_logs'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM debug_logs")
            log_count = cursor.fetchone()[0]

            print(f"[RECOVERY] Clearing {log_count} debug logs...")
            cursor.execute("DELETE FROM debug_logs")
            print(f"[RECOVERY] ✓ Cleared {cursor.rowcount} debug log entries")
        else:
            print("[RECOVERY] ✓ debug_logs table doesn't exist (nothing to clear)")

        # Commit changes
        conn.commit()
        conn.close()

        print("\n" + "="*60)
        print("✓ RECOVERY COMPLETE")
        print("="*60)
        print()
        print("Debug logging has been disabled and logs cleared.")
        print("The container should now be able to start successfully.")
        print()
        print("You can safely deploy now!")
        print()

        return 0

    except Exception as e:
        print(f"\n[RECOVERY] ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(recover_debug())
