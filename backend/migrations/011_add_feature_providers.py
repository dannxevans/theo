#!/usr/bin/env python3
"""
Migration 011: Add feature_providers table

This migration adds support for external feature providers (weather, traffic, etc.):
- feature_providers table to store API keys and configuration
- Supports OpenWeather, HERE.com traffic, and future providers
- API keys stored as preferences per user

Run with: python3 backend/migrations/011_add_feature_providers.py
Or with custom DB path: python3 backend/migrations/011_add_feature_providers.py /path/to/theo.db
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

    print(f"[MIGRATION 011] Starting migration...")
    print(f"[MIGRATION 011] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 011] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='feature_providers'
        """)

        if cursor.fetchone():
            print("[MIGRATION 011] ✓ feature_providers table already exists, skipping")
            return True

        # Create feature_providers table
        print("[MIGRATION 011] Creating feature_providers table...")
        cursor.execute("""
            CREATE TABLE feature_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                provider_type VARCHAR(50) NOT NULL,
                provider_name VARCHAR(100) NOT NULL,
                is_enabled BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, provider_type)
            )
        """)

        # Create index for faster lookups
        print("[MIGRATION 011] Creating index on user_id and provider_type...")
        cursor.execute("""
            CREATE INDEX idx_feature_providers_user_type
            ON feature_providers(user_id, provider_type)
        """)

        conn.commit()
        print("[MIGRATION 011] ✓ Migration completed successfully")
        print("[MIGRATION 011] Feature providers table created")
        print("[MIGRATION 011] Note: API keys are stored in preferences table with keys like 'feature_provider_openweather_api_key'")
        return True

    except Exception as e:
        print(f"[MIGRATION 011] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
