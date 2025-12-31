#!/usr/bin/env python3
"""
Migration: Add OFFICIAL classification columns to sessions table

This migration adds:
- classification column (defaults to 'OFFICIAL')
- Classification audit table for tracking classification-related actions

Usage:
  python3 migrations/add_classification_columns.py

For AWS deployment, run this before deploying the new code.
"""

import sqlite3
import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def get_db_path():
    """Get database path from environment or use default"""
    db_url = os.getenv('DATABASE_URL', 'sqlite:///theo.db')
    # Remove sqlite:/// prefix
    return db_url.replace('sqlite:///', '')

def run_migration():
    """Apply the migration"""
    db_path = get_db_path()

    if not os.path.exists(db_path):
        print(f"❌ Error: Database not found at {db_path}")
        return False

    print(f"📁 Using database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if classification column already exists
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'classification' in columns:
            print("✅ Classification column already exists, skipping sessions table update")
        else:
            print("➕ Adding classification column to sessions table...")
            cursor.execute("""
                ALTER TABLE sessions
                ADD COLUMN classification TEXT DEFAULT 'OFFICIAL'
            """)
            print("✅ Classification column added")

        # Check if classification_audit table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='classification_audit'
        """)

        if cursor.fetchone():
            print("✅ Classification audit table already exists, skipping")
        else:
            print("➕ Creating classification_audit table...")
            cursor.execute("""
                CREATE TABLE classification_audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    session_id TEXT,
                    classification TEXT NOT NULL,
                    action TEXT NOT NULL,
                    justification TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)
            print("✅ Classification audit table created")

        # Update existing work mode sessions to OFFICIAL
        cursor.execute("""
            UPDATE sessions
            SET classification = 'OFFICIAL'
            WHERE mode = 'work' AND (classification IS NULL OR classification = '')
        """)
        updated_count = cursor.rowcount
        if updated_count > 0:
            print(f"✅ Updated {updated_count} work mode sessions to OFFICIAL classification")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        return True

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verify_migration():
    """Verify the migration was successful"""
    db_path = get_db_path()

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("\n🔍 Verifying migration...")

        # Check sessions table
        cursor.execute("PRAGMA table_info(sessions)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}

        if 'classification' in columns:
            print("✅ sessions.classification column exists")
        else:
            print("❌ sessions.classification column missing!")
            return False

        # Check classification_audit table
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='classification_audit'
        """)
        if cursor.fetchone():
            print("✅ classification_audit table exists")
        else:
            print("❌ classification_audit table missing!")
            return False

        # Count sessions with classification
        cursor.execute("""
            SELECT COUNT(*) FROM sessions WHERE classification IS NOT NULL
        """)
        count = cursor.fetchone()[0]
        print(f"✅ {count} sessions have classification set")

        return True

    except sqlite3.Error as e:
        print(f"❌ Verification error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    print("=" * 60)
    print("THEO Database Migration: OFFICIAL Classification Support")
    print("=" * 60)
    print()

    success = run_migration()

    if success:
        verify_migration()
        print("\n✅ All done! You can now deploy the updated code.")
    else:
        print("\n❌ Migration failed. Please check errors above.")
        sys.exit(1)
