"""
Migration 032: Add Web Fetch Cache

Creates web_fetch_cache table for caching fetched web content:
- Stores fetched URL content with 1-hour TTL
- Per-user caching for privacy
- Indexed for fast lookups by URL hash

Run with: python3 backend/migrations/032_add_web_fetch_cache.py
Or with custom DB path: python3 backend/migrations/032_add_web_fetch_cache.py /path/to/theo.db
"""

import sqlite3
import os
import sys
from datetime import datetime


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
    """Create web_fetch_cache table."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 032] Starting migration...")
    print(f"[MIGRATION 032] Database: {DB_PATH}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create web_fetch_cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS web_fetch_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            url_hash TEXT NOT NULL,
            title TEXT,
            content TEXT NOT NULL,
            metadata TEXT,
            fetched_at DATETIME NOT NULL,
            expires_at DATETIME NOT NULL,
            content_hash TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create index on user_id for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_fetch_cache_user_id
        ON web_fetch_cache(user_id)
    """)

    # Create index on url_hash for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_fetch_cache_url_hash
        ON web_fetch_cache(url_hash)
    """)

    # Create index on expires_at for efficient cleanup
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_web_fetch_cache_expires_at
        ON web_fetch_cache(expires_at)
    """)

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name = 'web_fetch_cache'
    """)
    table_exists = cursor.fetchone() is not None

    if table_exists:
        # Verify indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_web_fetch_cache%'
        """)
        index_count = len(cursor.fetchall())

        print("[MIGRATION 032] ✓ web_fetch_cache table already exists")
        print(f"[MIGRATION 032] ✓ {index_count} indexes present")
    else:
        conn.commit()
        print("[MIGRATION 032] ✓ web_fetch_cache table created successfully")
        print("[MIGRATION 032] Features enabled:")
        print("[MIGRATION 032]   - Web content fetching and extraction")
        print("[MIGRATION 032]   - 1-hour caching per URL per user")
        print("[MIGRATION 032]   - HTTPS-only with private IP blocking")
        print("[MIGRATION 032]   - Rate limiting (50 requests/hour)")
        print("[MIGRATION 032]   - Multi-URL support")

    conn.close()
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
