"""
Migration 033: Add intent_reasoning_traces table

This table stores reasoning traces for:
1. Debugging intent classification issues
2. Tracking accuracy over time
3. Learning from user feedback
4. Analyzing service signal effectiveness (for agentic workflows)

Run with: python3 backend/migrations/033_add_intent_reasoning_traces.py
Or with custom DB path: python3 backend/migrations/033_add_intent_reasoning_traces.py /path/to/theo.db
"""

import sqlite3
import os
import sys


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
    """Add intent_reasoning_traces table for debugging and improvement."""
    DB_PATH = get_db_path()

    print(f"[MIGRATION 033] Starting migration...")
    print(f"[MIGRATION 033] Database: {DB_PATH}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create intent_reasoning_traces table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS intent_reasoning_traces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id TEXT,

            -- Input
            user_text TEXT NOT NULL,
            mode TEXT,
            subtab TEXT,

            -- Classification output
            intent TEXT NOT NULL,
            confidence REAL NOT NULL,
            reasoning TEXT,

            -- Entity extraction (JSON)
            entities TEXT,

            -- Service signals (JSON) - for agentic workflow analysis
            service_signals TEXT,

            -- Intent-specific parameters (JSON)
            parameters TEXT,

            -- Ambiguity handling
            is_ambiguous INTEGER DEFAULT 0,
            clarification_question TEXT,

            -- Metadata
            token_count INTEGER,
            latency_ms INTEGER,
            source TEXT DEFAULT 'reasoning',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Accuracy tracking
            user_feedback TEXT,
            corrected_intent TEXT,

            -- Agentic workflow tracking (for future use)
            orchestration_triggered INTEGER DEFAULT 0,
            services_called TEXT,

            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # Indexes for common queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reasoning_traces_user
        ON intent_reasoning_traces(user_id)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reasoning_traces_created
        ON intent_reasoning_traces(created_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reasoning_traces_intent
        ON intent_reasoning_traces(intent)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_reasoning_traces_source
        ON intent_reasoning_traces(source)
    """)

    # Check if table exists
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name = 'intent_reasoning_traces'
    """)
    table_exists = cursor.fetchone() is not None

    if table_exists:
        # Verify indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_reasoning_traces%'
        """)
        index_count = len(cursor.fetchall())

        print("[MIGRATION 033] ✓ intent_reasoning_traces table already exists")
        print(f"[MIGRATION 033] ✓ {index_count} indexes present")
    else:
        conn.commit()
        print("[MIGRATION 033] ✓ intent_reasoning_traces table created successfully")
        print("[MIGRATION 033] Features enabled:")
        print("[MIGRATION 033]   - AI-powered intent reasoning layer")
        print("[MIGRATION 033]   - Rich entity extraction (locations, times, people, activities)")
        print("[MIGRATION 033]   - Service relevance signals for orchestration")
        print("[MIGRATION 033]   - Reasoning trace debugging and analytics")
        print("[MIGRATION 033]   - Foundation for agentic workflow orchestration")

    conn.close()
    return True


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
