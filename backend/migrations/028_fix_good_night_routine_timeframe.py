#!/usr/bin/env python3
"""
Migration 028: Fix Good Night Routine Timeframe Parameter

Issue: GitHub #328
The "Good Night" routine has a calendar_read action with timeframe="today"
when it should be "tomorrow". This causes the routine to show today's events
instead of tomorrow's events.

This migration:
1. Finds all "Good Night" routines
2. Updates the calendar_read action to use timeframe="tomorrow"
3. Preserves all other routine configuration

Run with: python3 backend/migrations/028_fix_good_night_routine_timeframe.py
Or with custom DB path: python3 backend/migrations/028_fix_good_night_routine_timeframe.py /path/to/theo.db
"""

import sqlite3
import json
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
    """Execute the migration."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 028] Starting migration...")
    print(f"[MIGRATION 028] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 028] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if user_routines table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='user_routines'
        """)
        if not cursor.fetchone():
            print(f"[MIGRATION 028] user_routines table does not exist, skipping")
            return True

        # Find all Good Night routines
        cursor.execute("""
            SELECT id, user_id, name, actions
            FROM user_routines
            WHERE name = 'Good Night'
        """)

        routines = cursor.fetchall()

        if not routines:
            print("[MIGRATION 028] No 'Good Night' routines found, skipping")
            return True

        print(f"[MIGRATION 028] Found {len(routines)} 'Good Night' routine(s) to fix")

        fixed_count = 0

        for routine_id, user_id, name, actions_json in routines:
            try:
                # Parse actions JSON
                actions = json.loads(actions_json)

                # Track if we made changes
                modified = False

                # Find and fix calendar_read actions with wrong timeframe
                for action in actions:
                    if action.get("type") == "calendar_read":
                        params = action.get("params", {})

                        # Check if timeframe is "today" when description suggests tomorrow
                        description = action.get("description", "").lower()
                        current_timeframe = params.get("timeframe")

                        if current_timeframe == "today" and ("tomorrow" in description or "next day" in description):
                            print(
                                f"[MIGRATION 028] Fixing routine ID {routine_id} (user {user_id}): "
                                f"timeframe 'today' → 'tomorrow'"
                            )

                            # Update timeframe to tomorrow
                            params["timeframe"] = "tomorrow"
                            action["params"] = params
                            modified = True

                # Update routine if modified
                if modified:
                    updated_actions_json = json.dumps(actions)

                    cursor.execute("""
                        UPDATE user_routines
                        SET actions = ?
                        WHERE id = ?
                    """, (updated_actions_json, routine_id))

                    fixed_count += 1
                    print(f"[MIGRATION 028] ✓ Fixed routine ID {routine_id}")

            except Exception as e:
                print(f"[MIGRATION 028] Error fixing routine ID {routine_id}: {e}")
                # Continue with other routines even if one fails

        conn.commit()

        print(f"[MIGRATION 028] ✓ Migration completed successfully")
        print(f"[MIGRATION 028] Fixed {fixed_count} routine(s)")

        if fixed_count > 0:
            print("[MIGRATION 028] Good Night routines now correctly show tomorrow's calendar")

        return True

    except Exception as e:
        print(f"[MIGRATION 028] ERROR: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
