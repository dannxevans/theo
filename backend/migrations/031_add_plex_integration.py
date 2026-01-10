"""
Migration 031: Add Plex Integration

Creates tables for Plex Media Server integration:
- plex_credentials: OAuth tokens and server configuration
- plex_settings: User notification preferences
- plex_notification_tracking: Deduplication for proactive notifications (7-day retention)

Run with: python3 backend/migrations/031_add_plex_integration.py
Or with custom DB path: python3 backend/migrations/031_add_plex_integration.py /path/to/theo.db
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
    """Create Plex integration tables."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 031] Starting migration...")
    print(f"[MIGRATION 031] Database: {DB_PATH}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create plex_credentials table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plex_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            access_token TEXT NOT NULL,
            plex_user_id TEXT NOT NULL,
            plex_username TEXT,
            server_url TEXT NOT NULL,
            server_name TEXT,
            server_version TEXT,
            is_valid BOOLEAN DEFAULT 1,
            last_error TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create plex_settings table (notifications disabled by default per user request)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plex_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            new_episode_notifications_enabled BOOLEAN DEFAULT 0,
            new_season_notifications_enabled BOOLEAN DEFAULT 0,
            new_movie_notifications_enabled BOOLEAN DEFAULT 0,
            check_frequency_minutes INTEGER DEFAULT 15,
            quiet_hours_start TEXT,
            quiet_hours_end TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create plex_notification_tracking table for deduplication
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plex_notification_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plex_item_key TEXT NOT NULL,
            plex_item_type TEXT NOT NULL,
            notified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, plex_item_key)
        )
    """)

    # Create index for faster cleanup queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_plex_tracking_created_at
        ON plex_notification_tracking(created_at)
    """)

    # Check if tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('plex_credentials', 'plex_settings', 'plex_notification_tracking')
    """)
    existing_tables = [row[0] for row in cursor.fetchall()]

    if len(existing_tables) == 3:
        print("[MIGRATION 031] ✓ All Plex tables already exist, skipping")
    else:
        conn.commit()
        print("[MIGRATION 031] ✓ Plex integration tables created successfully")
        print("[MIGRATION 031] Features enabled:")
        print("[MIGRATION 031]   - OAuth 2.0 authentication with Plex.tv")
        print("[MIGRATION 031]   - Recently watched queries")
        print("[MIGRATION 031]   - On deck recommendations")
        print("[MIGRATION 031]   - Currently playing sessions")
        print("[MIGRATION 031]   - Routines integration")

    conn.close()
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
