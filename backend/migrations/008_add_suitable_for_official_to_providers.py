#!/usr/bin/env python3
"""
Migration 008: Add suitable_for_official column to providers table

This migration adds the suitable_for_official column to track which providers
are suitable for handling OFFICIAL classified data in Work Mode.

Run with: python3 backend/migrations/008_add_suitable_for_official_to_providers.py
Or with custom DB path: python3 backend/migrations/008_add_suitable_for_official_to_providers.py /path/to/theo.db
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

    print(f"[MIGRATION 008] Starting migration...")
    print(f"[MIGRATION 008] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 008] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if suitable_for_official column already exists
        cursor.execute("PRAGMA table_info(providers)")
        columns = [row[1] for row in cursor.fetchall()]

        if "suitable_for_official" in columns:
            print("[MIGRATION 008] ✓ suitable_for_official column already exists, skipping")
            return True

        # Add suitable_for_official column to providers table
        print("[MIGRATION 008] Adding suitable_for_official column to providers table...")
        cursor.execute("""
            ALTER TABLE providers
            ADD COLUMN suitable_for_official INTEGER DEFAULT 0
        """)

        # Set suitable_for_official to true for known OFFICIAL-suitable providers
        print("[MIGRATION 008] Setting suitable_for_official for known providers...")

        # Based on the risk assessment in AIProvidersSettings.svelte
        # Using provider type (not id) as that's how they're organized
        official_suitable_types = [
            'openai',
            'anthropic',
            'xai',
            'mistral',
            'google',
            'perplexity',
            'mock',  # for testing only
            'azure_openai'  # RECOMMENDED for OFFICIAL
        ]

        for provider_type in official_suitable_types:
            cursor.execute("""
                UPDATE providers
                SET suitable_for_official = 1
                WHERE type = ?
            """, (provider_type,))

        # Explicitly set OpenRouter to false (HIGH RISK)
        cursor.execute("""
            UPDATE providers
            SET suitable_for_official = 0
            WHERE type = 'openrouter'
        """)

        conn.commit()
        print("[MIGRATION 008] ✓ Migration completed successfully")
        return True

    except Exception as e:
        print(f"[MIGRATION 008] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
