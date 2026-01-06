#!/usr/bin/env python3
"""
Migration 026: Add session folders for organization and archiving

This migration adds folder support to enable:
- Custom folder creation for organizing sessions
- System-managed Archive folder (protected)
- Drag-and-drop session organization
- Folder expand/collapse state persistence
- Per-user folder management

Key features:
- session_folders table with user ownership
- Archive folder auto-created for all users
- sessions.folder_id for folder assignment
- Unique constraint prevents duplicate folder names per user
- System folder protection (is_system flag)

Run with: python3 backend/migrations/026_add_session_folders.py
Or with custom DB path: python3 backend/migrations/026_add_session_folders.py /path/to/theo.db
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

    print(f"[MIGRATION 026] Starting migration...")
    print(f"[MIGRATION 026] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 026] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='session_folders'
        """)

        table_exists = cursor.fetchone() is not None

        if not table_exists:
            # Create session_folders table
            print("[MIGRATION 026] Creating session_folders table...")
            cursor.execute("""
                CREATE TABLE session_folders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    user_id INTEGER NOT NULL,
                    is_system BOOLEAN DEFAULT 0,
                    sort_order INTEGER DEFAULT 0,
                    collapsed BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(user_id, name)
                )
            """)

            # Create indexes for performance
            print("[MIGRATION 026] Creating indexes...")

            # Index for listing user's folders
            cursor.execute("""
                CREATE INDEX idx_session_folders_user_id
                ON session_folders(user_id)
            """)

            # Index for system folder queries
            cursor.execute("""
                CREATE INDEX idx_session_folders_system
                ON session_folders(user_id, is_system)
            """)
        else:
            print("[MIGRATION 026] ✓ session_folders table already exists")

        # Add folder_id column to sessions table if it doesn't exist
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'folder_id' not in columns:
            print("[MIGRATION 026] Adding folder_id column to sessions table...")
            cursor.execute("""
                ALTER TABLE sessions ADD COLUMN folder_id INTEGER DEFAULT NULL
            """)

            # Create index for session folder queries
            cursor.execute("""
                CREATE INDEX idx_sessions_folder_id ON sessions(folder_id)
            """)
            print("[MIGRATION 026] ✓ folder_id column added to sessions table")
        else:
            print("[MIGRATION 026] ✓ folder_id column already exists in sessions table")

        # Create Archive folder for all existing users
        print("[MIGRATION 026] Creating Archive folders for users...")
        cursor.execute("""
            INSERT OR IGNORE INTO session_folders (name, user_id, is_system, sort_order, collapsed)
            SELECT 'Archive', id, 1, -1, 0
            FROM users
        """)

        archive_count = cursor.rowcount
        print(f"[MIGRATION 026] ✓ Created {archive_count} Archive folder(s)")

        conn.commit()
        print("[MIGRATION 026] ✓ Migration completed successfully")
        print("[MIGRATION 026] Session folders enabled:")
        print("[MIGRATION 026]   - Custom folders: Create, rename, delete")
        print("[MIGRATION 026]   - Archive folder: Protected system folder")
        print("[MIGRATION 026]   - Folder state: Expand/collapse persistence")
        return True

    except Exception as e:
        print(f"[MIGRATION 026] ✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

    finally:
        conn.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
