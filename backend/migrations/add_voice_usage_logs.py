#!/usr/bin/env python3
"""
THEO Database Migration: Voice Services Cost Tracking
Adds voice_usage_logs table for tracking TTS/STT usage and costs.
"""

import sqlite3
import sys
from pathlib import Path

def run_migration(db_path):
    """Add voice_usage_logs table to the database."""

    print("=" * 60)
    print("THEO Database Migration: Voice Services Cost Tracking")
    print("=" * 60)
    print(f"📁 Using database: {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='voice_usage_logs'
        """)

        if cursor.fetchone():
            print("⚠️  voice_usage_logs table already exists, skipping creation")
        else:
            print("➕ Creating voice_usage_logs table...")

            cursor.execute("""
                CREATE TABLE voice_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_type TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT,
                    character_count INTEGER DEFAULT 0,
                    audio_duration_seconds INTEGER DEFAULT 0,
                    estimated_cost INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_usage_created_at
                ON voice_usage_logs(created_at)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_voice_usage_service_type
                ON voice_usage_logs(service_type)
            """)

            conn.commit()
            print("✅ voice_usage_logs table created successfully")

        # Verify migration
        print("\n🔍 Verifying migration...")

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='voice_usage_logs'
        """)

        if cursor.fetchone():
            print("✅ voice_usage_logs table exists")

            # Check table structure
            cursor.execute("PRAGMA table_info(voice_usage_logs)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = {
                'id', 'service_type', 'provider', 'model',
                'character_count', 'audio_duration_seconds',
                'estimated_cost', 'success', 'error_message', 'created_at'
            }

            if required_columns.issubset(columns):
                print("✅ All required columns present")
            else:
                missing = required_columns - columns
                print(f"❌ Missing columns: {missing}")
                return False
        else:
            print("❌ voice_usage_logs table not found")
            return False

        print("\n✅ Migration completed successfully!")
        print("✅ All done! You can now deploy the updated code.")
        return True

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    # Default to theo.db in current directory
    db_path = Path("theo.db")

    # Allow custom path via command line
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    success = run_migration(db_path)
    sys.exit(0 if success else 1)
