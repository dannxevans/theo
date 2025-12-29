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

## Notes

These scripts are meant to be run from the project root directory. They automatically add the backend directory to the Python path.
