"""
Migration 032: Add Intent Reasoning Traces Table

Creates table for storing Intent Reasoning Engine execution traces:
- intent_reasoning_traces: Stores LLM reasoning analysis for debugging and optimization

This table enables:
- Debugging intent classification issues
- Analyzing LLM reasoning quality
- Optimizing prompt engineering
- Tracking orchestration recommendations

Run with: python3 backend/migrations/032_add_intent_reasoning_traces.py
Or with custom DB path: python3 backend/migrations/032_add_intent_reasoning_traces.py /path/to/theo.db
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
    """Create intent_reasoning_traces table."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 032] Starting migration...")
    print(f"[MIGRATION 032] Database: {DB_PATH}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create intent_reasoning_traces table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intent_reasoning_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            user_text TEXT NOT NULL,
            mode TEXT,
            subtab TEXT,
            intent TEXT NOT NULL,
            confidence REAL NOT NULL,
            reasoning TEXT,
            entities TEXT,
            service_signals TEXT,
            parameters TEXT,
            is_ambiguous BOOLEAN DEFAULT 0,
            clarification_question TEXT,
            orchestration_recommended BOOLEAN DEFAULT 0,
            orchestration_reason TEXT,
            token_count INTEGER,
            latency_ms INTEGER,
            source TEXT DEFAULT 'reasoning',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    # Create index for faster queries by user and session
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reasoning_traces_user_session
        ON intent_reasoning_traces(user_id, session_id)
    """)

    # Create index for faster queries by timestamp (for cleanup)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reasoning_traces_created_at
        ON intent_reasoning_traces(created_at)
    """)

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='intent_reasoning_traces'
    """)
    table_exists = cursor.fetchone()

    if table_exists:
        # Table exists, check if orchestration columns exist
        cursor.execute("PRAGMA table_info(intent_reasoning_traces)")
        columns = {row[1] for row in cursor.fetchall()}

        needs_update = False

        # Add orchestration_recommended column if missing
        if 'orchestration_recommended' not in columns:
            cursor.execute("""
                ALTER TABLE intent_reasoning_traces
                ADD COLUMN orchestration_recommended BOOLEAN DEFAULT 0
            """)
            needs_update = True
            print("[MIGRATION 032] ✓ Added orchestration_recommended column")

        # Add orchestration_reason column if missing
        if 'orchestration_reason' not in columns:
            cursor.execute("""
                ALTER TABLE intent_reasoning_traces
                ADD COLUMN orchestration_reason TEXT
            """)
            needs_update = True
            print("[MIGRATION 032] ✓ Added orchestration_reason column")

        if needs_update:
            conn.commit()
            print("[MIGRATION 032] ✓ Updated intent_reasoning_traces table")
        else:
            print("[MIGRATION 032] ✓ intent_reasoning_traces table already up-to-date")
    else:
        conn.commit()
        print("[MIGRATION 032] ✓ intent_reasoning_traces table created successfully")
        print("[MIGRATION 032] Features enabled:")
        print("[MIGRATION 032]   - Intent Reasoning debugging and analysis")
        print("[MIGRATION 032]   - Orchestration decision tracking")
        print("[MIGRATION 032]   - LLM reasoning quality monitoring")
        print("[MIGRATION 032]   - Prompt engineering optimization data")

    conn.close()
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
