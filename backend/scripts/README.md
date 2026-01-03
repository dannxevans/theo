# THEO Utility Scripts

This directory contains utility scripts for THEO administration and diagnostics.

## Scripts

### `reset_password.py`
Reset a user's password via direct database access.

**Usage**:
```bash
python backend/scripts/reset_password.py <username> <new_password>
```

**Example**:
```bash
python backend/scripts/reset_password.py admin mynewpassword
```

Useful when you've forgotten your password and need to regain access.

---

### `test_m365_auth.py`
Diagnostic script to test Microsoft 365 OAuth device code flow.

**Usage**:
```bash
python backend/scripts/test_m365_auth.py
```

This script helps diagnose M365 authentication issues by testing the OAuth flow step-by-step.

**Prerequisites**:
- `M365_CLIENT_ID` environment variable set in `.env`
- `M365_TENANT_ID` environment variable set in `.env` (optional, defaults to "common")

---

### `debug_recovery.py`
Emergency recovery script for when Debug Console causes container crashes.

**When to use**:
- Container stuck in crash loop due to debug log flooding
- Health check failures from excessive logging
- 504 Gateway Timeout errors when toggling debug mode
- Container memory exhaustion from debug logs

**What it does**:
1. Disables debug logging (`debug_enabled = false`)
2. Resets all logger filters to OFF (safe defaults)
3. Clears all debug logs from the database

**Usage**:
```bash
# From project root:
python3 backend/scripts/debug_recovery.py
```

**Output**:
```
[RECOVERY] Connecting to database: /path/to/theo.db
[RECOVERY] Disabling debug logging...
[RECOVERY] ✓ Disabled debug logging (1 rows updated)
[RECOVERY] Resetting logger filters to safe defaults...
[RECOVERY] ✓ Reset 4 logger filters to OFF
[RECOVERY] Clearing 1234 debug logs...
[RECOVERY] ✓ Cleared 1234 debug log entries

============================================================
✓ RECOVERY COMPLETE
============================================================
```

**For AWS/Production Recovery**:

If container is already crashing, you'll need database access:

1. Download latest S3 backup:
   ```bash
   aws s3 cp s3://YOUR-BACKUP-BUCKET/latest.db ./theo_prod.db
   ```

2. Point script to this database:
   ```bash
   export DATABASE_URL=sqlite:///./theo_prod.db
   python3 backend/scripts/debug_recovery.py
   ```

3. Upload fixed database and restore in ECS

**Safety**: Idempotent and safe to run multiple times. Only modifies debug-related preferences.

---

## Notes

These scripts are meant to be run from the project root directory. They automatically add the backend directory to the Python path.
