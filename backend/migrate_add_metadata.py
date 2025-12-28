#!/usr/bin/env python3
"""
Migration script to add provider metadata columns to turns table.
Run this once to update your existing database.
"""

import sqlite3
import sys
from config import Config

def migrate():
    db_path = Config.DATABASE_URL.replace('sqlite:///', '')

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]

        columns_to_add = []
        if 'provider_id' not in columns:
            columns_to_add.append('provider_id')
        if 'model' not in columns:
            columns_to_add.append('model')
        if 'intent' not in columns:
            columns_to_add.append('intent')
        if 'metadata' not in columns:  # ADD THIS
            columns_to_add.append('metadata')

        if not columns_to_add:
            print("✓ All columns already exist. No migration needed.")
            return

        print(f"Adding columns: {', '.join(columns_to_add)}")

        # Add columns (SQLite allows adding nullable columns)
        for column in columns_to_add:
            cursor.execute(f"ALTER TABLE turns ADD COLUMN {column} TEXT")
            print(f"  ✓ Added column: {column}")

        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("   Provider metadata will now be stored for new messages.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
