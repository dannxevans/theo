#!/usr/bin/env python3
"""
Migration 003: Add mode and user_id columns to sessions table

This migration adds mode-based session filtering by adding:
- mode column (default "personal") - to separate work/personal chats
- user_id column (nullable) - to filter sessions by authenticated user

Also adds PII filtering configuration to mode_settings table.

Run with: python3 backend/migrations/003_add_mode_to_sessions.py
Or with custom DB path: python3 backend/migrations/003_add_mode_to_sessions.py /path/to/theo.db
"""

import sqlite3
import os
import sys
from datetime import datetime

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

    print(f"[MIGRATION 003] Starting migration...")
    print(f"[MIGRATION 003] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 003] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        # Add mode column to sessions table
        if "mode" not in columns:
            print("[MIGRATION 003] Adding mode column to sessions table...")
            cursor.execute("""
                ALTER TABLE sessions
                ADD COLUMN mode TEXT DEFAULT 'personal'
            """)
            print("[MIGRATION 003] ✓ Added mode column")
        else:
            print("[MIGRATION 003] ✓ mode column already exists, skipping")

        # Add user_id column to sessions table
        if "user_id" not in columns:
            print("[MIGRATION 003] Adding user_id column to sessions table...")
            cursor.execute("""
                ALTER TABLE sessions
                ADD COLUMN user_id INTEGER
            """)
            print("[MIGRATION 003] ✓ Added user_id column")
        else:
            print("[MIGRATION 003] ✓ user_id column already exists, skipping")

        # Check mode_settings table columns
        cursor.execute("PRAGMA table_info(mode_settings)")
        mode_settings_columns = [row[1] for row in cursor.fetchall()]

        # Add pii_filtering_enabled column to mode_settings table
        if "pii_filtering_enabled" not in mode_settings_columns:
            print("[MIGRATION 003] Adding pii_filtering_enabled column to mode_settings table...")
            cursor.execute("""
                ALTER TABLE mode_settings
                ADD COLUMN pii_filtering_enabled INTEGER DEFAULT 0
            """)
            print("[MIGRATION 003] ✓ Added pii_filtering_enabled column")
        else:
            print("[MIGRATION 003] ✓ pii_filtering_enabled column already exists, skipping")

        # Add pii_redaction_config column to mode_settings table
        if "pii_redaction_config" not in mode_settings_columns:
            print("[MIGRATION 003] Adding pii_redaction_config column to mode_settings table...")
            cursor.execute("""
                ALTER TABLE mode_settings
                ADD COLUMN pii_redaction_config TEXT
            """)
            print("[MIGRATION 003] ✓ Added pii_redaction_config column")
        else:
            print("[MIGRATION 003] ✓ pii_redaction_config column already exists, skipping")

        # Create index for performance
        print("[MIGRATION 003] Creating composite index on sessions...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user_mode_updated
                ON sessions(user_id, mode, updated_at DESC)
            """)
            print("[MIGRATION 003] ✓ Created index idx_sessions_user_mode_updated")
        except Exception as e:
            print(f"[MIGRATION 003] ⚠ Index creation warning: {e}")

        conn.commit()
        print("[MIGRATION 003] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 003] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
