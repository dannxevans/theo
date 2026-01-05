#!/usr/bin/env python3
"""
Migration 022: Add WHOOP Integration Tables

This migration adds support for WHOOP fitness tracking integration to enable:
- OAuth 2.0 authentication with WHOOP API
- Post-sleep summaries with recovery insights
- Post-workout summaries with strain data
- Proactive health notifications (Personal Mode only)
- Privacy-first data handling (7-day tracking retention)

Tables created:
- whoop_credentials: OAuth tokens and WHOOP user ID
- whoop_settings: User preferences for WHOOP notifications
- whoop_data_tracking: Track processed sleep/workout records for deduplication

Medical Guardrails:
- No medical advice, diagnosis, or prescriptive training plans
- Observational language only ("I notice", "Your data shows")
- LLM summaries follow strict guardrail prompts

Run with: python3 backend/migrations/022_add_whoop_integration.py
Or with custom DB path: python3 backend/migrations/022_add_whoop_integration.py /path/to/theo.db
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

    print(f"[MIGRATION 022] Starting migration...")
    print(f"[MIGRATION 022] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 022] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # =============================
        # Create whoop_credentials table
        # =============================
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='whoop_credentials'
        """)

        if cursor.fetchone():
            print("[MIGRATION 022] ✓ whoop_credentials table already exists, skipping")
        else:
            print("[MIGRATION 022] Creating whoop_credentials table...")
            cursor.execute("""
                CREATE TABLE whoop_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT NOT NULL,
                    token_type TEXT DEFAULT 'Bearer',
                    expires_at DATETIME NOT NULL,
                    whoop_user_id TEXT NOT NULL,
                    is_valid BOOLEAN DEFAULT 1,
                    last_refreshed_at DATETIME,
                    last_error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for user lookups
            cursor.execute("""
                CREATE INDEX idx_whoop_credentials_user_id
                ON whoop_credentials(user_id)
            """)

            print("[MIGRATION 022] ✓ whoop_credentials table created")

        # =============================
        # Create whoop_settings table
        # =============================
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='whoop_settings'
        """)

        if cursor.fetchone():
            print("[MIGRATION 022] ✓ whoop_settings table already exists, skipping")
        else:
            print("[MIGRATION 022] Creating whoop_settings table...")
            cursor.execute("""
                CREATE TABLE whoop_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    sleep_notifications_enabled BOOLEAN DEFAULT 1,
                    workout_notifications_enabled BOOLEAN DEFAULT 1,
                    check_frequency_minutes INTEGER DEFAULT 30,
                    quiet_hours_enabled BOOLEAN DEFAULT 0,
                    quiet_hours_start TEXT,
                    quiet_hours_end TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for user lookups
            cursor.execute("""
                CREATE INDEX idx_whoop_settings_user_id
                ON whoop_settings(user_id)
            """)

            print("[MIGRATION 022] ✓ whoop_settings table created")

        # =============================
        # Create whoop_data_tracking table
        # =============================
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='whoop_data_tracking'
        """)

        if cursor.fetchone():
            print("[MIGRATION 022] ✓ whoop_data_tracking table already exists, skipping")
        else:
            print("[MIGRATION 022] Creating whoop_data_tracking table...")
            cursor.execute("""
                CREATE TABLE whoop_data_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    data_type TEXT NOT NULL,
                    whoop_id TEXT NOT NULL UNIQUE,
                    notified_at DATETIME NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Index for user + data_type queries
            cursor.execute("""
                CREATE INDEX idx_whoop_tracking_user_type
                ON whoop_data_tracking(user_id, data_type)
            """)

            # Index for whoop_id lookups (deduplication)
            cursor.execute("""
                CREATE INDEX idx_whoop_tracking_whoop_id
                ON whoop_data_tracking(whoop_id)
            """)

            # Index for cleanup queries (find old records)
            cursor.execute("""
                CREATE INDEX idx_whoop_tracking_created_at
                ON whoop_data_tracking(created_at)
            """)

            print("[MIGRATION 022] ✓ whoop_data_tracking table created")

        conn.commit()
        print("[MIGRATION 022] ✓ Migration completed successfully")
        print("[MIGRATION 022] WHOOP integration tables created")
        print("[MIGRATION 022] Features enabled:")
        print("[MIGRATION 022]   - OAuth 2.0 authentication")
        print("[MIGRATION 022]   - Post-sleep summaries")
        print("[MIGRATION 022]   - Post-workout summaries")
        print("[MIGRATION 022]   - Personal Mode only (Work Mode blocked)")
        print("[MIGRATION 022]   - Medical guardrails enforced")
        print("[MIGRATION 022]   - 7-day tracking retention for privacy")
        return True

    except Exception as e:
        print(f"[MIGRATION 022] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
