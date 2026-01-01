"""
Migration 012: Add feature_provider_usage_logs table

Tracks usage statistics for feature providers (weather, routing, etc.)
"""

import sqlite3
from pathlib import Path


def get_db_path():
    """Get database path from config."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    env = os.getenv("ENV", "dev")
    if env == "prod":
        return "/data/theo.db"
    else:
        # local dev default
        data_dir = Path(__file__).resolve().parent.parent.parent / "data"
        data_dir.mkdir(exist_ok=True)
        return str(data_dir / "theo.db")


def run_migration():
    """Add feature_provider_usage_logs table."""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print("[MIGRATION 012] Starting migration...")
    print(f"[MIGRATION 012] Database: {db_path}")

    # Check if table already exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='feature_provider_usage_logs'
    """)

    if cursor.fetchone():
        print("[MIGRATION 012] ✓ feature_provider_usage_logs table already exists, skipping")
        conn.close()
        return True

    # Create feature_provider_usage_logs table
    print("[MIGRATION 012] Creating feature_provider_usage_logs table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS feature_provider_usage_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            provider_type VARCHAR(50) NOT NULL,
            success BOOLEAN DEFAULT 1,
            latency_ms INTEGER,
            error_message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create index for faster queries
    print("[MIGRATION 012] Creating indexes...")
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_feature_provider_usage_user_provider
        ON feature_provider_usage_logs(user_id, provider_type)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_feature_provider_usage_created_at
        ON feature_provider_usage_logs(created_at)
    """)

    conn.commit()
    conn.close()

    print("[MIGRATION 012] ✓ Migration completed successfully")
    return True


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Override get_db_path by directly using the argument
        db_path = sys.argv[1]

        # Create a wrapper function that uses the passed path
        def run_with_custom_path():
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            print("[MIGRATION 012] Starting migration...")
            print(f"[MIGRATION 012] Database: {db_path}")

            # Check if table already exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='feature_provider_usage_logs'
            """)

            if cursor.fetchone():
                print("[MIGRATION 012] ✓ feature_provider_usage_logs table already exists, skipping")
                conn.close()
                return True

            # Create feature_provider_usage_logs table
            print("[MIGRATION 012] Creating feature_provider_usage_logs table...")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feature_provider_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    provider_type VARCHAR(50) NOT NULL,
                    success BOOLEAN DEFAULT 1,
                    latency_ms INTEGER,
                    error_message TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create index for faster queries
            print("[MIGRATION 012] Creating indexes...")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feature_provider_usage_user_provider
                ON feature_provider_usage_logs(user_id, provider_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_feature_provider_usage_created_at
                ON feature_provider_usage_logs(created_at)
            """)

            conn.commit()
            conn.close()

            print("[MIGRATION 012] ✓ Migration completed successfully")
            return True

        run_with_custom_path()
    else:
        run_migration()
