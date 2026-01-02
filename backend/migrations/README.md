# Database Migrations

This directory contains database migration scripts for THEO.

## Migration System Overview

**IMPORTANT**: THEO has two migration runners:

1. **`backend/db_backup.py:run_migrations()`** - **MAIN MIGRATION RUNNER**
   - Runs automatically on every application startup
   - Handles all migrations 001-019 in sequence
   - Used by AWS deployments and Docker containers
   - Called by `init_database_backup()` in app initialization

2. **`backend/migrations/run_migrations.py`** - Manual runner for development
   - Use for manual migration testing
   - Use for running migrations on specific database files
   - Use for emergency migration fixes

## Running Migrations

### Automatic (Production/AWS)

Migrations run automatically when the application starts via `backend/db_backup.py`.

No manual intervention needed - migrations 001-019 are applied automatically.

### Manual (Development/Testing)

Run all pending migrations manually:

```bash
python3 backend/migrations/run_migrations.py
```

Or for a specific database:

```bash
python3 backend/migrations/run_migrations.py /path/to/theo.db
```

### Local Development

Run individual migrations against the local database:

```bash
python3 backend/migrations/004_add_is_action_to_intents.py
python3 backend/migrations/005_add_last_activity_to_sessions.py
python3 backend/migrations/006_add_preferences_unique_constraint.py
```

### Production / AWS

Run migrations against a remote database by providing the database path:

```bash
python3 backend/migrations/run_migrations.py /path/to/production/theo.db
```

Or SSH into your AWS instance and run:

```bash
cd /path/to/theo
python3 backend/migrations/run_migrations.py
```

## Migration List

| Migration | Description | Status |
|-----------|-------------|--------|
| 001_add_action_tables.py | Initial action system tables | ✓ |
| 002_add_turns_metadata.py | Add metadata column to turns table | ✓ |
| 003_add_mode_to_sessions.py | Add mode column to sessions table | ✓ |
| 004_add_is_action_to_intents.py | Add is_action flag to intents table for action intent management | New |
| 005_add_last_activity_to_sessions.py | Add last_activity_at to auth_sessions for inactivity timeout | New |
| 006_add_preferences_unique_constraint.py | Add unique constraint to preferences table | New |

## Creating New Migrations

1. Create a new file: `backend/migrations/00X_description.py`
2. Follow the pattern from existing migrations
3. Include rollback/safety checks (e.g., checking if column exists)
4. Test locally before deploying
5. Update this README

## Notes

- Migrations are idempotent - safe to run multiple times
- Always backup the database before running migrations in production
- Migrations check for existing schema elements before making changes
