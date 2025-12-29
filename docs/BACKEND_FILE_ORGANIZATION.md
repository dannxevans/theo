# Backend File Organization Analysis

**Date**: December 29, 2025

---

## Current Backend Root Structure

```
backend/
├── app.py                      # ✅ Main Flask application (keep)
├── auth.py                     # ⚠️ MISPLACED - Should be in backend/auth/
├── config.py                   # ✅ Configuration module (keep)
├── db_backup.py                # ✅ Database backup utility (keep)
├── migrate_add_metadata.py     # ⚠️ MISPLACED - Should be in backend/migrations/
├── reset_password.py           # ⚠️ MISPLACED - Should be in backend/scripts/
├── test_m365_auth.py           # ⚠️ MISPLACED - Should be in backend/tests/
├── requirements.txt            # ✅ Python dependencies (keep)
├── Dockerfile                  # ✅ Docker configuration (keep)
├── pytest.ini                  # ✅ Pytest configuration (keep)
├── .coveragerc                 # ✅ Coverage configuration (keep)
│
├── actions/                    # ✅ Action system
├── auth/                       # ✅ OAuth implementations
├── core/                       # ✅ Core modules
├── migrations/                 # ✅ Database migrations
├── providers/                  # ✅ AI provider implementations
├── routes/                     # ✅ Flask blueprints
├── tests/                      # ✅ Test suite
├── voice/                      # ✅ Voice features
└── venv/                       # ✅ Virtual environment
```

---

## Issues Identified

### 1. `auth.py` in Root (Should be in `backend/auth/`)

**Current**: `backend/auth.py` (3,020 bytes)
**Should be**: `backend/auth/auth.py` or `backend/auth/password.py`

**Why it's misplaced**:
- There's already a `backend/auth/` directory containing:
  - `__init__.py`
  - `m365_oauth.py`
- The root `auth.py` contains password hashing and session management
- It creates confusion: is auth in root or in the auth/ directory?

**Contents of `auth.py`**:
```python
def hash_password(password)
def verify_password(password, stored_hash)
def generate_session_token()
def init_default_user(memory)
def create_session(memory, user_id)
def require_auth(f)
def require_admin(f)
```

**Recommendation**:
- Move to `backend/auth/password.py` or `backend/auth/session.py`
- Update imports across codebase
- OR consolidate into `backend/auth/__init__.py` if it's the main auth module

---

### 2. `migrate_add_metadata.py` in Root (Should be in `backend/migrations/`)

**Current**: `backend/migrate_add_metadata.py` (1,679 bytes)
**Should be**: `backend/migrations/002_add_turns_metadata.py`

**Why it's misplaced**:
- There's already a `backend/migrations/` directory with:
  - `001_add_action_tables.py`
  - `002_add_turns_metadata.py` ← This already exists!
  - `003_add_mode_to_sessions.py`
  - `README.md`

**Analysis**:
```bash
$ diff migrate_add_metadata.py migrations/002_add_turns_metadata.py
```

**Finding**: These files have similar purposes (both add metadata to turns table).

**Recommendation**:
- Check if `migrate_add_metadata.py` is a duplicate of `002_add_turns_metadata.py`
- If duplicate: **DELETE** `migrate_add_metadata.py`
- If different: Rename and move to `migrations/00X_...py`

---

### 3. `test_m365_auth.py` in Root (Should be in `backend/tests/`)

**Current**: `backend/test_m365_auth.py` (2,961 bytes)
**Should be**: `backend/tests/auth/test_m365_oauth.py` or `backend/scripts/test_m365_auth.py`

**Why it's misplaced**:
- Not in the standard `backend/tests/` directory
- Tests should be organized with other tests

**Contents**:
- Manual OAuth device code flow test
- Used for debugging M365 authentication
- Not a unit test (more like a diagnostic script)

**Recommendation**:
- If it's a **diagnostic script**: Move to `backend/scripts/test_m365_auth.py`
- If it's a **real test**: Move to `backend/tests/auth/test_m365_oauth.py`
- Most likely: It's a diagnostic script (should go in scripts/)

---

### 4. `reset_password.py` in Root (Should be in `backend/scripts/`)

**Current**: `backend/reset_password.py` (1,529 bytes)
**Should be**: `backend/scripts/reset_password.py`

**Why it's misplaced**:
- It's a CLI utility script, not a core module
- Should be organized with other utility scripts

**Contents**:
```python
#!/usr/bin/env python3
"""Password Reset Utility for THEO"""

Usage:
    python reset_password.py <username> <new_password>
```

**Recommendation**:
- Create `backend/scripts/` directory
- Move `reset_password.py` there
- Update documentation to reflect new path

---

## Proposed New Structure

```
backend/
├── app.py                      # Main Flask application
├── config.py                   # Configuration
├── db_backup.py                # Database backup module
├── requirements.txt
├── Dockerfile
├── pytest.ini
├── .coveragerc
│
├── actions/                    # Action system
├── auth/                       # Authentication modules
│   ├── __init__.py
│   ├── password.py             # ← MOVED from root auth.py
│   ├── session.py              # ← OR split auth.py into this
│   └── m365_oauth.py
│
├── core/                       # Core modules
├── migrations/                 # Database migrations
│   ├── 001_add_action_tables.py
│   ├── 002_add_turns_metadata.py
│   ├── 003_add_mode_to_sessions.py
│   └── README.md
│   # migrate_add_metadata.py removed (duplicate)
│
├── providers/                  # AI providers
├── routes/                     # Flask blueprints
│
├── scripts/                    # ← NEW DIRECTORY
│   ├── reset_password.py       # ← MOVED from root
│   └── test_m365_auth.py       # ← MOVED from root
│
├── tests/                      # Test suite
│   ├── auth/                   # ← ADD if needed
│   ├── core/
│   ├── memory/
│   ├── routes/
│   └── ...
│
├── voice/
└── venv/
```

---

## Recommended Actions

### Priority 1: Create Scripts Directory
```bash
mkdir -p backend/scripts
```

### Priority 2: Move Utility Scripts
```bash
# Move password reset utility
mv backend/reset_password.py backend/scripts/

# Move M365 auth test script
mv backend/test_m365_auth.py backend/scripts/
```

### Priority 3: Consolidate Auth Module
**Option A: Move to auth directory**
```bash
mv backend/auth.py backend/auth/password.py
```

**Option B: Merge into auth/__init__.py**
```bash
# Manually merge auth.py into auth/__init__.py
# Delete auth.py
```

**Recommendation**: Choose Option A (clearer separation)

### Priority 4: Clean Up Migration File
```bash
# Compare files first
diff backend/migrate_add_metadata.py backend/migrations/002_add_turns_metadata.py

# If duplicate, delete
rm backend/migrate_add_metadata.py

# If different, move to migrations with proper number
mv backend/migrate_add_metadata.py backend/migrations/00X_add_metadata.py
```

---

## Import Updates Required

After reorganizing, update imports in these files:

### Files importing `auth.py`:
```bash
grep -r "from auth import" backend --include="*.py" | grep -v venv
grep -r "import auth" backend --include="*.py" | grep -v venv
```

**Found in**:
- `backend/app.py`: `from auth import init_default_user`
- `backend/reset_password.py`: `from auth import hash_password`
- `backend/routes/auth_routes.py`: `from auth import hash_password, verify_password, ...`

**Update to**:
```python
# Before
from auth import hash_password

# After (if moved to auth/password.py)
from auth.password import hash_password

# OR (if merged into auth/__init__.py)
from auth import hash_password  # No change needed
```

### Files importing `migrate_add_metadata.py`:
Likely none (it's a standalone script).

---

## Files to Keep in Root

These files are **correctly placed** in the backend root:

1. **`app.py`** - Main application entry point (standard Flask pattern)
2. **`config.py`** - Configuration module (standard pattern)
3. **`db_backup.py`** - Database backup module (reasonable in root)
4. **`requirements.txt`** - Python dependencies (must be in root)
5. **`Dockerfile`** - Docker configuration (must be in root)
6. **`pytest.ini`** - Pytest configuration (standard location)
7. **`.coveragerc`** - Coverage configuration (standard location)

---

## Summary of Changes

| File | Current Location | Recommended Location | Action |
|------|------------------|---------------------|--------|
| `auth.py` | `backend/` | `backend/auth/password.py` | Move + Update imports |
| `migrate_add_metadata.py` | `backend/` | Check if duplicate of `002_*` | Compare, then delete or move |
| `test_m365_auth.py` | `backend/` | `backend/scripts/` | Move (diagnostic script) |
| `reset_password.py` | `backend/` | `backend/scripts/` | Move (CLI utility) |

**Impact**:
- ✅ Cleaner backend root
- ✅ Better organization
- ✅ Easier to find utility scripts
- ✅ Consistent with Python project best practices
- ⚠️ Requires import updates in ~5 files

---

## Migration Plan

### Step 1: Create Scripts Directory
```bash
mkdir -p backend/scripts
echo "# THEO Utility Scripts" > backend/scripts/README.md
```

### Step 2: Move Scripts (Low Risk)
```bash
mv backend/reset_password.py backend/scripts/
mv backend/test_m365_auth.py backend/scripts/
```

Update documentation:
```bash
# Update any references in docs/
grep -r "reset_password.py" docs/
```

### Step 3: Handle Migration File (Check First)
```bash
# Compare the two files
diff backend/migrate_add_metadata.py backend/migrations/002_add_turns_metadata.py

# If identical or redundant, delete
rm backend/migrate_add_metadata.py

# If different and needed, move to migrations/
mv backend/migrate_add_metadata.py backend/migrations/004_add_metadata.py
```

### Step 4: Consolidate Auth (Medium Risk)
```bash
# Option A: Move to auth/password.py
mv backend/auth.py backend/auth/password.py

# Update auth/__init__.py to export functions
echo "from .password import *" >> backend/auth/__init__.py
echo "from .m365_oauth import *" >> backend/auth/__init__.py
```

**OR**

```bash
# Option B: Merge into auth/__init__.py
cat backend/auth.py >> backend/auth/__init__.py
rm backend/auth.py
```

### Step 5: Update Imports
Update imports in:
- `backend/app.py`
- `backend/routes/auth_routes.py`
- `backend/scripts/reset_password.py` (if moved)

### Step 6: Test
```bash
# Run tests
cd backend
pytest

# Test password reset script
python scripts/reset_password.py --help

# Test M365 auth script
python scripts/test_m365_auth.py
```

---

## Conclusion

**Current State**: Backend root has 4 misplaced files that should be organized into subdirectories.

**Recommended**: Create `backend/scripts/` directory and reorganize files for better maintainability.

**Risk Level**: Low to Medium
- Moving scripts: Low risk (just update docs)
- Moving auth.py: Medium risk (requires import updates in ~5 files)

**Effort**: 15-30 minutes to complete reorganization + testing.

---

## Next Steps

1. ✅ Review this analysis
2. Create `backend/scripts/` directory
3. Move utility scripts
4. Compare and handle `migrate_add_metadata.py`
5. Decide on auth.py consolidation strategy
6. Update imports
7. Test all changes
8. Update documentation
