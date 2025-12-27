#!/usr/bin/env python3
"""
Migration 001: Add Action System Tables

This migration adds the database schema for the Personal AI Agent system:
- service_providers: External service integrations (M365, booking APIs, etc.)
- actions: Tracks all planned/executed actions
- action_confirmations: Manages confirmation workflow
- m365_credentials: OAuth credentials for Microsoft 365
- calendar_events_cache: Optional cache for calendar data

Run with: python3 backend/migrations/001_add_action_tables.py
"""

import sqlite3
import os
from datetime import datetime

# Determine database path
# Database is at project root /data/theo.db
DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "theo.db"
)

def run_migration():
    """Execute the migration."""
    print(f"[MIGRATION 001] Starting migration...")
    print(f"[MIGRATION 001] Database: {DB_PATH}")

    if not os.path.exists(DB_PATH):
        print(f"[MIGRATION 001] ERROR: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Create service_providers table
        print("[MIGRATION 001] Creating service_providers table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                category VARCHAR(100) NOT NULL,
                provider_type VARCHAR(50) NOT NULL,
                capabilities TEXT,

                api_base_url VARCHAR(500),
                auth_method VARCHAR(50),

                access_token TEXT,
                refresh_token TEXT,
                token_expires_at DATETIME,

                api_endpoint_calendar VARCHAR(500),
                api_endpoint_email VARCHAR(500),
                additional_metadata TEXT,

                trust_level VARCHAR(20) DEFAULT 'manual',
                booking_method VARCHAR(50),
                preferred_for_category BOOLEAN DEFAULT 0,

                is_enabled BOOLEAN DEFAULT 1,
                last_synced_at DATETIME,
                health_status VARCHAR(20) DEFAULT 'unknown',

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_service_providers_user_category
            ON service_providers(user_id, category)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_service_providers_enabled
            ON service_providers(user_id, is_enabled)
        """)

        # Create actions table
        print("[MIGRATION 001] Creating actions table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id VARCHAR(255) NOT NULL,

                action_type VARCHAR(50) NOT NULL,
                category VARCHAR(50) NOT NULL,
                intent_summary TEXT NOT NULL,

                service_provider_id INTEGER,

                action_params TEXT,
                planned_execution_time DATETIME,

                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                requires_confirmation BOOLEAN DEFAULT 1,

                initiated_at DATETIME,
                approved_at DATETIME,
                executed_at DATETIME,
                completed_at DATETIME,

                result_data TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 3,

                is_reversible BOOLEAN DEFAULT 0,
                rollback_action_id INTEGER,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (service_provider_id) REFERENCES service_providers(id)
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_actions_user_status
            ON actions(user_id, status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_actions_session
            ON actions(session_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_actions_provider
            ON actions(service_provider_id)
        """)

        # Create action_confirmations table
        print("[MIGRATION 001] Creating action_confirmations table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS action_confirmations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_id INTEGER NOT NULL UNIQUE,

                confirmation_message TEXT NOT NULL,
                user_response VARCHAR(20),
                user_response_text TEXT,

                modified_params TEXT,

                presented_at DATETIME NOT NULL,
                responded_at DATETIME,
                expires_at DATETIME,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (action_id) REFERENCES actions(id)
            )
        """)

        # Create m365_credentials table
        print("[MIGRATION 001] Creating m365_credentials table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS m365_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,

                access_token TEXT NOT NULL,
                refresh_token TEXT NOT NULL,
                token_type VARCHAR(50) DEFAULT 'Bearer',
                expires_at DATETIME NOT NULL,
                scope TEXT,

                tenant_id VARCHAR(255),
                user_principal_name VARCHAR(255),

                is_valid BOOLEAN DEFAULT 1,
                last_refreshed_at DATETIME,
                last_error TEXT,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create calendar_events_cache table (optional)
        print("[MIGRATION 001] Creating calendar_events_cache table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calendar_events_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,

                event_id VARCHAR(255) NOT NULL,
                calendar_id VARCHAR(255),

                subject VARCHAR(500),
                start_time DATETIME NOT NULL,
                end_time DATETIME NOT NULL,
                location VARCHAR(500),
                description TEXT,
                attendees TEXT,

                is_all_day BOOLEAN DEFAULT 0,
                status VARCHAR(50),
                importance VARCHAR(20),

                fetched_at DATETIME NOT NULL,
                cache_expires_at DATETIME,

                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calendar_cache_user_time
            ON calendar_events_cache(user_id, start_time, end_time)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_calendar_cache_event
            ON calendar_events_cache(event_id)
        """)

        # Commit changes
        conn.commit()

        print("[MIGRATION 001] Migration completed successfully!")
        print("[MIGRATION 001] Created tables:")
        print("  - service_providers")
        print("  - actions")
        print("  - action_confirmations")
        print("  - m365_credentials")
        print("  - calendar_events_cache")

        return True

    except Exception as e:
        print(f"[MIGRATION 001] ERROR: {e}")
        conn.rollback()
        return False

    finally:
        conn.close()

def verify_migration():
    """Verify that all tables were created."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name IN ('service_providers', 'actions', 'action_confirmations',
                         'm365_credentials', 'calendar_events_cache')
            ORDER BY name
        """)

        tables = [row[0] for row in cursor.fetchall()]

        print("\n[MIGRATION 001] Verification:")
        expected_tables = [
            'action_confirmations',
            'actions',
            'calendar_events_cache',
            'm365_credentials',
            'service_providers'
        ]

        for table in expected_tables:
            if table in tables:
                print(f"  ✓ {table}")
            else:
                print(f"  ✗ {table} (MISSING!)")

        return len(tables) == len(expected_tables)

    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("THEO Database Migration 001: Action System Tables")
    print("=" * 60)
    print()

    success = run_migration()

    if success:
        verify_migration()
        print("\n[MIGRATION 001] ✓ Migration complete!")
    else:
        print("\n[MIGRATION 001] ✗ Migration failed!")
        exit(1)
