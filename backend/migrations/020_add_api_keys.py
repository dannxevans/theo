#!/usr/bin/env python3
"""
Migration 020: Add API keys table for programmatic authentication

This migration adds support for API key authentication to enable:
- Siri Shortcuts integration
- iOS automation
- External tool integrations
- CLI script access

Key features:
- API keys with format theo_<random>
- Bcrypt hashed storage (same security as passwords)
- Optional expiration dates
- Revocation support
- Usage tracking via last_used_at

Run with: python3 backend/migrations/020_add_api_keys.py
Or with custom DB path: python3 backend/migrations/020_add_api_keys.py /path/to/theo.db
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

    print(f"[MIGRATION 020] Starting migration...")
    print(f"[MIGRATION 020] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 020] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='api_keys'
        """)

        if cursor.fetchone():
            print("[MIGRATION 020] ✓ api_keys table already exists, skipping")
            return True

        # Create api_keys table
        print("[MIGRATION 020] Creating api_keys table...")
        cursor.execute("""
            CREATE TABLE api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                key_hash TEXT NOT NULL,
                name TEXT,
                last_used_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME,
                is_revoked BOOLEAN DEFAULT 0,
                revoked_at DATETIME
            )
        """)

        # Create indexes for performance
        print("[MIGRATION 020] Creating indexes...")

        # Index for listing user's keys
        cursor.execute("""
            CREATE INDEX idx_api_keys_user_id
            ON api_keys(user_id)
        """)

        # Index for key validation (hash lookup)
        cursor.execute("""
            CREATE INDEX idx_api_keys_key_hash
            ON api_keys(key_hash)
        """)

        # Index for active keys query (not revoked, not expired)
        cursor.execute("""
            CREATE INDEX idx_api_keys_status
            ON api_keys(is_revoked, expires_at)
        """)

        conn.commit()
        print("[MIGRATION 020] ✓ Migration completed successfully")
        print("[MIGRATION 020] API keys table created with indexes")
        print("[MIGRATION 020] Note: API keys are hashed using bcrypt (same as passwords)")
        print("[MIGRATION 020] Format: theo_<64-hex-chars>")
        return True

    except Exception as e:
        print(f"[MIGRATION 020] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
