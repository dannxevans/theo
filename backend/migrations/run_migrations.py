#!/usr/bin/env python3
"""
Manual migration runner script.

NOTE: This is for MANUAL migrations only. The automatic migration runner used
during application startup is in backend/db_backup.py:run_migrations().

The db_backup.py runner is the canonical migration runner that:
- Runs automatically on every application startup
- Handles all migrations 001-019 in sequence
- Is used by AWS deployments and Docker containers

This script (run_migrations.py) is useful for:
- Manual migration testing during development
- Running migrations on a specific database file
- Emergency migration fixes

Usage:
  python3 backend/migrations/run_migrations.py
  python3 backend/migrations/run_migrations.py /path/to/theo.db
"""

import os
import sys
import importlib.util

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

def run_all_migrations():
    """Run all migration scripts in order."""
    migrations_dir = os.path.dirname(__file__)
    db_path = get_db_path()

    print("=" * 60)
    print("THEO Database Migration Runner")
    print("=" * 60)
    print(f"Database: {db_path}")
    print()

    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        print("Skipping migrations - database will be created on first run.")
        print()
        return True

    # Get all migration files in order
    migration_files = [
        "009_add_fallback_provider_to_routing.py",  # Add fallback_provider_id column for provider fallback support
        "010_add_circuit_breaker_cooldown.py",  # Add circuit breaker cooldown columns for time-based auto-retry
        "011_add_feature_providers.py",  # Add feature_providers table for external service API keys
        "012_add_feature_provider_usage_logs.py",  # Add usage tracking for feature providers
        "013_add_planning_metadata.py",  # Add enrichment_data column to actions table for context-aware planning
        "014_add_proactive_settings.py",  # Add proactive_settings table for user notification preferences
        "015_add_proactive_tracking_tables.py",  # Add proactive notification tracking tables
        "016_add_routine_tracking.py",  # Add routine_name and routine_actions columns to turns table
        "017_add_user_routines.py",  # Add user_routines table for custom user-defined routines
        "018_1_cleanup_duplicate_preferences.py",  # Pre-migration cleanup for migration 018
        "018_standardize_user_id_to_integer.py",  # Standardize user_id from String to Integer
        "019_create_debug_logs.py",  # Add debug_logs table for debug console feature
        "020_add_api_keys.py",  # Add api_keys table for API key authentication (Siri Shortcuts, iOS automation)
        "021_add_full_request_context.py",  # Add full_request_context column to turns for LLM prompt debugging
        "022_add_whoop_integration.py",  # Add WHOOP integration tables (credentials, settings, tracking)
        "023_add_whoop_stress_notifications.py",  # Add stress notifications to WHOOP settings
        "024_add_stress_notification_time.py",  # Add stress notification time to WHOOP settings
        "025_add_oauth_config_to_feature_providers.py"  # Add OAuth config storage to feature providers
    ]

    # Filter to only existing files
    existing_migrations = []
    for filename in migration_files:
        filepath = os.path.join(migrations_dir, filename)
        if os.path.exists(filepath):
            existing_migrations.append(filepath)

    if not existing_migrations:
        print("No migration files found.")
        return True

    print(f"Found {len(existing_migrations)} migration(s) to run:")
    for filepath in existing_migrations:
        print(f"  - {os.path.basename(filepath)}")
    print()

    # Run each migration
    all_success = True
    for filepath in existing_migrations:
        # Load and run the migration module
        spec = importlib.util.spec_from_file_location("migration", filepath)
        module = importlib.util.module_from_spec(spec)

        # Temporarily override sys.argv to pass db_path
        original_argv = sys.argv.copy()
        sys.argv = [sys.argv[0], db_path]

        try:
            spec.loader.exec_module(module)
            success = module.run_migration()
            if not success:
                all_success = False
                print(f"\nWARNING: Migration {os.path.basename(filepath)} failed or was skipped")
        except Exception as e:
            print(f"\nERROR running {os.path.basename(filepath)}: {e}")
            all_success = False
        finally:
            # Restore original argv
            sys.argv = original_argv

        print()

    print("=" * 60)
    if all_success:
        print("✓ All migrations completed successfully")
    else:
        print("⚠ Some migrations failed or were skipped")
    print("=" * 60)

    return all_success

if __name__ == "__main__":
    success = run_all_migrations()
    sys.exit(0 if success else 1)
