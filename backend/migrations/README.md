# Database Migrations

This directory contains database migration scripts for THEO.

## Running Migrations

### Local Development

Run migrations against the local database:

```bash
python3 backend/migrations/001_add_action_tables.py
python3 backend/migrations/002_add_turns_metadata.py
```

### Production / AWS

Run migrations against a remote database by providing the database path:

```bash
python3 backend/migrations/002_add_turns_metadata.py /path/to/production/theo.db
```

Or SSH into your AWS instance and run:

```bash
cd /path/to/theo
python3 backend/migrations/002_add_turns_metadata.py
```

## Migration List

| Migration | Description | Status |
|-----------|-------------|--------|
| 001_add_action_tables.py | Initial action system tables | ✓ |
| 002_add_turns_metadata.py | Add metadata column to turns table | ✓ |

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
