"""
Migration 031: Add Plex Integration

Creates tables for Plex Media Server integration:
- plex_credentials: OAuth tokens and server configuration
- plex_settings: User notification preferences
- plex_notification_tracking: Deduplication for proactive notifications (7-day retention)
"""

from datetime import datetime


def run_migration(conn):
    """
    Create Plex integration tables.

    Args:
        conn: SQLite database connection
    """
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

    conn.commit()
    print("✅ Migration 031: Plex integration tables created successfully")
