#!/usr/bin/env python3
"""
Migration 007: Configurable Action Intents and Session Timeout
Date: 2025-12-31
Issues: #115, #116, #117

Changes:
1. Add is_action column to intents table (Issue #115/#117)
2. Add last_activity_at column to auth_sessions table (Issue #116)
3. Add unique constraint to preferences table (Issue #116)
4. Seed default action intents and system intent
"""

import sqlite3
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_db_path():
    """Get the database path from environment or use default."""
    import os
    env = os.getenv("ENV", "dev")

    if env == "prod":
        return "/data/theo.db"
    else:
        # Local dev default
        repo_root = Path(__file__).resolve().parent.parent.parent
        data_dir = repo_root / "data"
        data_dir.mkdir(exist_ok=True)
        return str(data_dir / "theo.db")


def add_is_action_to_intents(conn):
    """Add is_action column to intents table."""
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(intents)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'is_action' not in columns:
        logging.info("Adding is_action column to intents table...")
        cursor.execute("ALTER TABLE intents ADD COLUMN is_action BOOLEAN DEFAULT 0")
        conn.commit()
        logging.info("✓ Added is_action column to intents")
    else:
        logging.info("✓ is_action column already exists in intents table")


def add_last_activity_to_sessions(conn):
    """Add last_activity_at column to auth_sessions table."""
    cursor = conn.cursor()

    # Check if column already exists
    cursor.execute("PRAGMA table_info(auth_sessions)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'last_activity_at' not in columns:
        logging.info("Adding last_activity_at column to auth_sessions table...")
        cursor.execute("ALTER TABLE auth_sessions ADD COLUMN last_activity_at DATETIME")

        # Initialize last_activity_at for existing sessions to their created_at
        cursor.execute("""
            UPDATE auth_sessions
            SET last_activity_at = created_at
            WHERE last_activity_at IS NULL
        """)
        conn.commit()
        logging.info("✓ Added last_activity_at column to auth_sessions")
    else:
        logging.info("✓ last_activity_at column already exists in auth_sessions table")


def add_preferences_unique_constraint(conn):
    """Add unique constraint to preferences table on (user_id, key)."""
    cursor = conn.cursor()

    # Check if unique constraint already exists
    cursor.execute("PRAGMA index_list(preferences)")
    indexes = cursor.fetchall()
    has_unique_constraint = any('uq_user_preference' in str(idx) for idx in indexes)

    if not has_unique_constraint:
        logging.info("Adding unique constraint to preferences table...")

        # Create new table with unique constraint
        cursor.execute("""
            CREATE TABLE preferences_new (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, key)
            )
        """)

        # Copy data from old table
        cursor.execute("""
            INSERT INTO preferences_new (user_id, key, value, updated_at)
            SELECT user_id, key, value, updated_at
            FROM preferences
        """)

        # Drop old table and rename new table
        cursor.execute("DROP TABLE preferences")
        cursor.execute("ALTER TABLE preferences_new RENAME TO preferences")

        conn.commit()
        logging.info("✓ Added unique constraint to preferences table")
    else:
        logging.info("✓ Unique constraint already exists on preferences table")


def seed_action_intents(conn):
    """Seed default action intents and system intent."""
    cursor = conn.cursor()

    # Get all user_ids from existing intents to seed for each user
    cursor.execute("SELECT DISTINCT user_id FROM intents")
    user_ids = [row[0] for row in cursor.fetchall()]

    if not user_ids:
        logging.info("No users found with existing intents, skipping action intent seeding")
        return

    action_intents = [
        # Action Intents (is_action=True)
        ("calendar_view", "View Calendar", "View upcoming calendar events and appointments", "calendar, schedule, appointments, meetings, what's on my calendar", 95, True, True),
        ("calendar_create", "Create Calendar Event", "Create new calendar events and appointments", "create event, schedule meeting, add appointment, book calendar", 95, True, True),
        ("email_inbox", "View Inbox", "View recent emails from inbox", "inbox, check email, show emails, recent messages, what's in my inbox", 95, True, True),
        ("email_search", "Search Emails", "Search emails by sender, subject, or content", "search email, find message, look for email, email from", 95, True, True),
        ("email_compose", "Compose Email", "Compose and send new emails", "send email, write email, compose message, email to", 95, True, True),
        ("email_reply", "Reply to Email", "Reply to or forward emails", "reply to, forward email, respond to email", 95, True, True),
        ("contact_lookup", "Lookup Contact", "Find contact information", "contact info, phone number, email address, find contact", 95, True, True),
        ("task_management", "Manage Tasks", "View, create, and manage tasks", "tasks, to-do, create task, view tasks, task list", 95, True, True),

        # System Intent (is_action=False, hidden from UI)
        ("system", "System", "Lightweight background tasks (email summarization, calendar extraction, etc.)", "", 100, True, False),
    ]

    for user_id in user_ids:
        logging.info(f"Seeding action intents for user_id={user_id}...")

        for intent_id, name, description, keywords, priority, enabled, is_action in action_intents:
            # Check if intent already exists for this user
            cursor.execute(
                "SELECT id FROM intents WHERE user_id = ? AND id = ?",
                (user_id, intent_id)
            )

            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO intents (user_id, id, name, description, keywords, priority, enabled, is_action)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, intent_id, name, description, keywords, priority, enabled, is_action))
                logging.info(f"  ✓ Created intent: {intent_id}")
            else:
                # Update is_action for existing intent
                cursor.execute("""
                    UPDATE intents
                    SET is_action = ?
                    WHERE user_id = ? AND id = ?
                """, (is_action, user_id, intent_id))
                logging.info(f"  ✓ Updated intent: {intent_id}")

        conn.commit()
        logging.info(f"✓ Seeded action intents for user_id={user_id}")


def run_migration():
    """Run all migration steps."""
    db_path = get_db_path()
    logging.info(f"Running migration on database: {db_path}")

    try:
        conn = sqlite3.connect(db_path)

        # Run all migration steps
        add_is_action_to_intents(conn)
        add_last_activity_to_sessions(conn)
        add_preferences_unique_constraint(conn)
        seed_action_intents(conn)

        conn.close()
        logging.info("✓ Migration 007 completed successfully")
        return True

    except Exception as e:
        logging.error(f"✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
