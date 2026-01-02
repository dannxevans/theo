#!/usr/bin/env python3
"""
Migration 014: Add proactive notification settings

This migration adds the proactive_settings table for user configuration
of calendar and email awareness features.

Run with: python3 backend/migrations/014_add_proactive_settings.py
Or with custom DB path: python3 backend/migrations/014_add_proactive_settings.py /path/to/theo.db
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
    """Execute the migration."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 014] Starting migration...")
    print(f"[MIGRATION 014] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 014] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if proactive_settings table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='proactive_settings'
        """)

        if cursor.fetchone():
            print("[MIGRATION 014] ✓ proactive_settings table already exists")
            return True

        print("[MIGRATION 014] Creating proactive_settings table...")

        cursor.execute("""
            CREATE TABLE proactive_settings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL UNIQUE DEFAULT 'local',

                -- Feature toggles
                calendar_enabled BOOLEAN DEFAULT 1,
                email_enabled BOOLEAN DEFAULT 1,

                -- Timing settings (in minutes)
                calendar_lead_time_minutes INTEGER DEFAULT 15,
                calendar_check_frequency_minutes INTEGER DEFAULT 15,
                email_check_frequency_minutes INTEGER DEFAULT 15,
                email_digest_frequency_minutes INTEGER DEFAULT 60,

                -- Rate limiting
                max_messages_per_hour INTEGER DEFAULT 10,

                -- Quiet hours
                quiet_hours_enabled BOOLEAN DEFAULT 0,
                quiet_hours_start TIME,
                quiet_hours_end TIME,

                -- Frontend polling (in minutes)
                frontend_poll_interval_minutes INTEGER DEFAULT 5,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default settings for 'local' user
        cursor.execute("""
            INSERT INTO proactive_settings (user_id)
            VALUES ('local')
        """)

        conn.commit()
        print("[MIGRATION 014] ✓ proactive_settings table created successfully")
        print("[MIGRATION 014] ✓ Default settings inserted for 'local' user")
        return True

    except Exception as e:
        print(f"[MIGRATION 014] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
