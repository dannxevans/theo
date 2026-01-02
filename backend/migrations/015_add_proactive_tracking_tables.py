#!/usr/bin/env python3
"""
Migration 015: Add proactive notification tracking tables

This migration adds tables for tracking:
- Calendar event notifications (deduplication)
- Email processing (important emails and digests)
- Email digest batches
- Proactive errors
- Rate limiting

Run with: python3 backend/migrations/015_add_proactive_tracking_tables.py
Or with custom DB path: python3 backend/migrations/015_add_proactive_tracking_tables.py /path/to/theo.db
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

    print(f"[MIGRATION 015] Starting migration...")
    print(f"[MIGRATION 015] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 015] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1. Create proactive_calendar_notifications table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='proactive_calendar_notifications'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 015] Creating proactive_calendar_notifications table...")
            cursor.execute("""
                CREATE TABLE proactive_calendar_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    event_id TEXT NOT NULL,
                    event_start TIMESTAMP NOT NULL,
                    event_title TEXT,
                    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notification_content TEXT,
                    UNIQUE(user_id, event_id, event_start)
                )
            """)
            print("[MIGRATION 015] ✓ proactive_calendar_notifications table created")
        else:
            print("[MIGRATION 015] ✓ proactive_calendar_notifications table already exists")

        # 2. Create proactive_email_tracking table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='proactive_email_tracking'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 015] Creating proactive_email_tracking table...")
            cursor.execute("""
                CREATE TABLE proactive_email_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    email_id TEXT NOT NULL,
                    received_at TIMESTAMP NOT NULL,
                    is_important BOOLEAN DEFAULT 0,
                    notified_at TIMESTAMP,
                    digest_included_at TIMESTAMP,
                    classification_method TEXT,
                    UNIQUE(user_id, email_id)
                )
            """)
            print("[MIGRATION 015] ✓ proactive_email_tracking table created")
        else:
            print("[MIGRATION 015] ✓ proactive_email_tracking table already exists")

        # 3. Create proactive_email_digests table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='proactive_email_digests'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 015] Creating proactive_email_digests table...")
            cursor.execute("""
                CREATE TABLE proactive_email_digests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    digest_sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    email_count INTEGER,
                    summary_content TEXT
                )
            """)
            print("[MIGRATION 015] ✓ proactive_email_digests table created")
        else:
            print("[MIGRATION 015] ✓ proactive_email_digests table already exists")

        # 4. Create proactive_errors table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='proactive_errors'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 015] Creating proactive_errors table...")
            cursor.execute("""
                CREATE TABLE proactive_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    error_type TEXT NOT NULL,
                    error_message TEXT,
                    error_details TEXT,
                    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved BOOLEAN DEFAULT 0
                )
            """)
            print("[MIGRATION 015] ✓ proactive_errors table created")
        else:
            print("[MIGRATION 015] ✓ proactive_errors table already exists")

        # 5. Create proactive_rate_limit_tracking table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='proactive_rate_limit_tracking'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 015] Creating proactive_rate_limit_tracking table...")
            cursor.execute("""
                CREATE TABLE proactive_rate_limit_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL DEFAULT 'local',
                    hour_window TIMESTAMP NOT NULL,
                    message_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, hour_window)
                )
            """)
            print("[MIGRATION 015] ✓ proactive_rate_limit_tracking table created")
        else:
            print("[MIGRATION 015] ✓ proactive_rate_limit_tracking table already exists")

        conn.commit()
        print("[MIGRATION 015] ✓ Migration completed successfully")
        print("[MIGRATION 015] All proactive tracking tables created")
        return True

    except Exception as e:
        print(f"[MIGRATION 015] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
