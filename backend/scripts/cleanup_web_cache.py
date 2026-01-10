#!/usr/bin/env python3
"""
Web Fetch Cache Cleanup Script

Removes expired entries from the web_fetch_cache table.
Should be run periodically via cron job (recommended: daily).

Usage:
  python3 backend/scripts/cleanup_web_cache.py
  python3 backend/scripts/cleanup_web_cache.py /path/to/theo.db
"""

import os
import sys
import sqlite3
from datetime import datetime

def get_db_path():
    """Get database path from command line arg or default location."""
    if len(sys.argv) > 1:
        return sys.argv[1]

    # Default: project root /data/theo.db
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))
    return os.path.join(project_root, "data", "theo.db")


def cleanup_expired_cache():
    """Remove expired web fetch cache entries."""
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found: {db_path}")
        return False

    print(f"[CACHE CLEANUP] Starting cleanup...")
    print(f"[CACHE CLEANUP] Database: {db_path}")
    print(f"[CACHE CLEANUP] Time: {datetime.now().isoformat()}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Delete expired cache entries
        cursor.execute("""
            DELETE FROM web_fetch_cache
            WHERE expires_at < datetime('now')
        """)

        deleted_count = cursor.rowcount
        conn.commit()

        # Get remaining cache stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_entries,
                COUNT(DISTINCT user_id) as unique_users,
                ROUND(SUM(LENGTH(content)) / 1024.0 / 1024.0, 2) as total_mb
            FROM web_fetch_cache
        """)

        stats = cursor.fetchone()
        total_entries, unique_users, total_mb = stats if stats else (0, 0, 0.0)

        conn.close()

        print(f"[CACHE CLEANUP] ✓ Deleted {deleted_count} expired entries")
        print(f"[CACHE CLEANUP] Remaining: {total_entries} entries")
        print(f"[CACHE CLEANUP] Users with cached data: {unique_users}")
        print(f"[CACHE CLEANUP] Total cache size: {total_mb} MB")
        print(f"[CACHE CLEANUP] Cleanup complete")

        return True

    except Exception as e:
        print(f"[CACHE CLEANUP] ERROR: {e}")
        return False


if __name__ == "__main__":
    success = cleanup_expired_cache()
    sys.exit(0 if success else 1)
