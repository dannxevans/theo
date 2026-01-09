#!/usr/bin/env python3
"""
Migration 030: Add work_mode_ip_config table

This migration adds the work_mode_ip_config table to support IP-based access
control for Work Mode. The table stores:
- enabled: Toggle for IP restrictions (disabled by default)
- allowed_ranges: JSON array of CIDR notation IP ranges

Run with: python3 backend/migrations/030_add_work_mode_ip_config.py
Or with custom DB path: python3 backend/migrations/030_add_work_mode_ip_config.py /path/to/theo.db
"""

import sqlite3
import os
import sys
import json

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

    print(f"[MIGRATION 030] Starting migration...")
    print(f"[MIGRATION 030] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 030] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='work_mode_ip_config'
        """)

        if cursor.fetchone():
            print("[MIGRATION 030] ✓ Table already exists, skipping")
            return True

        # Create the work_mode_ip_config table
        print("[MIGRATION 030] Creating work_mode_ip_config table...")
        cursor.execute("""
            CREATE TABLE work_mode_ip_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enabled BOOLEAN NOT NULL DEFAULT 0,
                allowed_ranges TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Insert default row (disabled, empty ranges)
        print("[MIGRATION 030] Inserting default configuration...")
        default_ranges = json.dumps([])
        cursor.execute("""
            INSERT INTO work_mode_ip_config (enabled, allowed_ranges)
            VALUES (0, ?)
        """, (default_ranges,))

        conn.commit()

        # Verify table creation
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='work_mode_ip_config'
        """)
        if not cursor.fetchone():
            print("[MIGRATION 030] ✗ Table verification failed")
            return False

        # Verify default row
        cursor.execute("SELECT COUNT(*) FROM work_mode_ip_config")
        count = cursor.fetchone()[0]
        if count != 1:
            print(f"[MIGRATION 030] ✗ Expected 1 row, found {count}")
            return False

        print("[MIGRATION 030] ✓ Migration completed successfully")
        print("[MIGRATION 030] Created work_mode_ip_config table")
        print("[MIGRATION 030] Default state: disabled with empty allowed ranges")
        return True

    except Exception as e:
        print(f"[MIGRATION 030] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
