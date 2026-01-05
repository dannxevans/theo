"""
Migration 025: Add OAuth configuration to feature_providers

Adds encrypted_config column to feature_providers table to store
OAuth client credentials (client_id, client_secret, redirect_uri, etc.)
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
    Add encrypted_config column to feature_providers table.
    """
    print("[MIGRATION 025] Starting migration...")
    print(f"[MIGRATION 025] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 025] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if feature_providers table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='feature_providers'
        """)

        if not cursor.fetchone():
            print("[MIGRATION 025] ⚠ feature_providers table doesn't exist, skipping")
            return True

        # Check if column already exists
        cursor.execute("PRAGMA table_info(feature_providers)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'encrypted_config' in columns:
            print("[MIGRATION 025] ⚠ encrypted_config column already exists, skipping")
            return True

        # Add encrypted_config column (TEXT to store JSON)
        print("[MIGRATION 025] Adding encrypted_config column...")
        cursor.execute("""
            ALTER TABLE feature_providers
            ADD COLUMN encrypted_config TEXT
        """)

        conn.commit()
        print("[MIGRATION 025] ✓ encrypted_config column added")
        print("[MIGRATION 025] ✓ Migration completed successfully")

        return True

    except Exception as e:
        conn.rollback()
        print(f"[MIGRATION 025] ✗ Migration failed: {e}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
