#!/usr/bin/env python3
"""
Migration 019: Create debug_logs table

This migration creates a table for storing application logs for the debug console.

Run with: python3 backend/migrations/019_create_debug_logs.py
Or with custom DB path: python3 backend/migrations/019_create_debug_logs.py /path/to/theo.db
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

    print(f"[MIGRATION 019] Starting migration...")
    print(f"[MIGRATION 019] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 019] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='debug_logs'
        """)

        if cursor.fetchone():
            print("[MIGRATION 019] ✓ debug_logs table already exists, skipping")
            return True

        # Create debug_logs table
        print("[MIGRATION 019] Creating debug_logs table...")
        cursor.execute("""
            CREATE TABLE debug_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                level VARCHAR(10) NOT NULL,
                source VARCHAR(20) NOT NULL,
                component VARCHAR(50),
                message TEXT NOT NULL,
                raw_data TEXT,
                user_id INTEGER,
                session_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Create indexes for efficient querying
        print("[MIGRATION 019] Creating indexes...")
        cursor.execute("""
            CREATE INDEX idx_debug_logs_timestamp
            ON debug_logs(timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX idx_debug_logs_level
            ON debug_logs(level)
        """)

        cursor.execute("""
            CREATE INDEX idx_debug_logs_source
            ON debug_logs(source)
        """)

        cursor.execute("""
            CREATE INDEX idx_debug_logs_component
            ON debug_logs(component)
        """)

        conn.commit()
        print("[MIGRATION 019] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 019] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
