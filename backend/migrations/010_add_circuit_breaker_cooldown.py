#!/usr/bin/env python3
"""
Migration 010: Add circuit breaker cooldown columns

This migration adds time-based circuit breaker reset functionality:
- circuit_breaker_opened_at: Timestamp when circuit breaker was opened
- circuit_breaker_cooldown_minutes: Configurable cooldown period (default 60 minutes)

After the cooldown period, the circuit breaker enters "half-open" state and
automatically retries the provider. If successful, it closes; if it fails, it
reopens and waits another cooldown period.

Run with: python3 backend/migrations/010_add_circuit_breaker_cooldown.py
Or with custom DB path: python3 backend/migrations/010_add_circuit_breaker_cooldown.py /path/to/theo.db
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

    print(f"[MIGRATION 010] Starting migration...")
    print(f"[MIGRATION 010] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 010] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(provider_metadata)")
        columns = [row[1] for row in cursor.fetchall()]

        needs_opened_at = "circuit_breaker_opened_at" not in columns
        needs_cooldown = "circuit_breaker_cooldown_minutes" not in columns

        if not needs_opened_at and not needs_cooldown:
            print("[MIGRATION 010] ✓ Circuit breaker cooldown columns already exist, skipping")
            return True

        # Add circuit_breaker_opened_at column
        if needs_opened_at:
            print("[MIGRATION 010] Adding circuit_breaker_opened_at column...")
            cursor.execute("""
                ALTER TABLE provider_metadata
                ADD COLUMN circuit_breaker_opened_at TEXT DEFAULT NULL
            """)

        # Add circuit_breaker_cooldown_minutes column
        if needs_cooldown:
            print("[MIGRATION 010] Adding circuit_breaker_cooldown_minutes column...")
            cursor.execute("""
                ALTER TABLE provider_metadata
                ADD COLUMN circuit_breaker_cooldown_minutes INTEGER DEFAULT 60
            """)

        conn.commit()
        print("[MIGRATION 010] ✓ Migration completed successfully")
        print("[MIGRATION 010] Circuit breakers will now automatically retry after cooldown period")
        return True

    except Exception as e:
        print(f"[MIGRATION 010] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
