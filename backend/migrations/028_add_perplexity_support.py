#!/usr/bin/env python3
"""
Migration 028: Add Perplexity AI provider support

This migration is informational only. Perplexity provider support is added via:
- Backend: providers/perplexity.py (new provider class)
- Router: core/router.py (instantiate_provider, capabilities)
- Intent: core/intent_classifier.py (search intent keywords)
- Frontend: Chat.svelte (model display, footer styling)
- Frontend: AIProvidersSettings.svelte (risk assessment)

No database schema changes required. Provider metadata is initialized automatically
when a Perplexity provider is first created via the API.

Run with: python3 backend/migrations/028_add_perplexity_support.py
Or with custom DB path: python3 backend/migrations/028_add_perplexity_support.py /path/to/theo.db
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

    print(f"[MIGRATION 028] Starting migration...")
    print(f"[MIGRATION 028] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 028] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Verify providers table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='providers'")
        if not cursor.fetchone():
            print("[MIGRATION 028] ERROR: providers table not found")
            return False

        # Verify provider_metadata table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='provider_metadata'")
        if not cursor.fetchone():
            print("[MIGRATION 028] ERROR: provider_metadata table not found")
            return False

        # Check if migration 008 has run (suitable_for_official column exists)
        cursor.execute("PRAGMA table_info(providers)")
        columns = [row[1] for row in cursor.fetchall()]

        if "suitable_for_official" not in columns:
            print("[MIGRATION 028] WARNING: Migration 008 (suitable_for_official) has not run yet")
            print("[MIGRATION 028] Please run migration 008 first")
            return False

        # Migration 028 is informational only - no schema changes
        # Perplexity providers can now be added via the API
        print("[MIGRATION 028] ✓ Perplexity provider support enabled")
        print("[MIGRATION 028] ✓ No database changes required")
        print("[MIGRATION 028] ✓ Create Perplexity providers via API: POST /api/providers")
        print("[MIGRATION 028] ✓ Search intent routing enabled via intent classifier")
        print("[MIGRATION 028] ✓ Migration completed successfully")

        conn.commit()
        return True

    except Exception as e:
        print(f"[MIGRATION 028] ✗ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
