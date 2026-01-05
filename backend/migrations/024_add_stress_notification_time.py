"""
Migration 024: Add stress notification time to WHOOP settings

Adds stress_notification_time column to whoop_settings table
to allow users to configure when they receive daily stress summaries.
"""

import sqlite3
import os
import sys

# Get database path from environment or use default
DB_PATH = os.getenv("DATABASE_PATH")
if not DB_PATH:
    # Try to find the database relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    DB_PATH = os.path.join(script_dir, "..", "..", "data", "theo.db")

def run_migration():
    """
    Add stress_notification_time column to whoop_settings table.
    """
    print("[MIGRATION 024] Starting migration...")
    print(f"[MIGRATION 024] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 024] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if whoop_settings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='whoop_settings'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 024] ⚠ whoop_settings table doesn't exist, skipping")
            return True

        # Check if column already exists
        cursor.execute("PRAGMA table_info(whoop_settings)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'stress_notification_time' in columns:
            print("[MIGRATION 024] ⚠ stress_notification_time column already exists, skipping")
            return True

        # Add stress_notification_time column (default 14:00 UTC = 2 PM)
        print("[MIGRATION 024] Adding stress_notification_time column...")
        cursor.execute("""
            ALTER TABLE whoop_settings
            ADD COLUMN stress_notification_time TEXT DEFAULT '14:00'
        """)

        conn.commit()
        print("[MIGRATION 024] ✓ stress_notification_time column added")
        print("[MIGRATION 024] ✓ Migration completed successfully")

        return True

    except Exception as e:
        conn.rollback()
        print(f"[MIGRATION 024] ✗ Migration failed: {e}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
