#!/usr/bin/env python3
"""
Master migration runner script.

Runs all pending migrations in order.

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
        "013_add_planning_metadata.py"  # Add enrichment_data column to actions table for context-aware planning
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
