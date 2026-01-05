"""
Migration 023: Add stress notifications to WHOOP settings

Adds stress_notifications_enabled column to whoop_settings table
to support daily stress summaries based on HRV/recovery data.
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
    Add stress_notifications_enabled column to whoop_settings table.
    """
    print("[MIGRATION 023] Starting migration...")
    print(f"[MIGRATION 023] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 023] ERROR: Database not found at {DB_PATH}")
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
            print("[MIGRATION 023] ⚠ whoop_settings table doesn't exist, skipping")
            return True

        # Check if column already exists
        cursor.execute("PRAGMA table_info(whoop_settings)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'stress_notifications_enabled' in columns:
            print("[MIGRATION 023] ⚠ stress_notifications_enabled column already exists, skipping")
            return True

        # Add stress_notifications_enabled column
        print("[MIGRATION 023] Adding stress_notifications_enabled column...")
        cursor.execute("""
            ALTER TABLE whoop_settings
            ADD COLUMN stress_notifications_enabled BOOLEAN DEFAULT 1
        """)

        conn.commit()
        print("[MIGRATION 023] ✓ stress_notifications_enabled column added")
        print("[MIGRATION 023] ✓ Migration completed successfully")

        return True

    except Exception as e:
        conn.rollback()
        print(f"[MIGRATION 023] ✗ Migration failed: {e}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
