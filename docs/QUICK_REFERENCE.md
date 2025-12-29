# Quick Reference - Backend Changes

**Date**: December 29, 2025

---

## What Changed?

### Files Moved
```
reset_password.py         → backend/scripts/reset_password.py
test_m365_auth.py         → backend/scripts/test_m365_auth.py
auth.py                   → backend/auth/password.py
```

### Files Deleted
```
migrate_add_metadata.py   (duplicate)
memory_legacy.py          (2,211 lines - refactored to modular)
```

---

## New File Locations

### Utility Scripts
**Old**: `python backend/reset_password.py admin newpass`
**New**: `python backend/scripts/reset_password.py admin newpass`

### Auth Module
**Old**: `from auth import hash_password`
**New**: `from auth import hash_password` (no change - still works!)

The auth module was reorganized but imports remain the same.

---

## Schema Changes

### Before (BAD)
Update schemas in TWO places:
1. `backend/core/memory_legacy.py`
2. `backend/core/memory/schema.py`

### After (GOOD)
Update schema in ONE place:
1. `backend/core/memory/schema.py` ✅

---

## Common Tasks

### Adding a Database Column
```python
# 1. Edit backend/core/memory/schema.py
def create_schema(meta: MetaData):
    my_table = Table(
        "my_table",
        meta,
        # ... existing columns ...
        Column("new_column", String, nullable=True),  # ← Add here
    )

# 2. Create migration in backend/migrations/
# 3. Run migration
# Done!
```

### Running Utility Scripts
```bash
# Password reset
python backend/scripts/reset_password.py <username> <password>

# Test M365 auth
python backend/scripts/test_m365_auth.py
```

### Importing Auth Functions
```python
# All these still work the same!
from auth import hash_password
from auth import verify_password
from auth import generate_session_token
from auth import init_default_user
from auth import require_auth
```

---

## Architecture

### Memory System (NEW)
```
backend/core/memory/
├── store.py           # Main facade (clean, no inheritance)
├── schema.py          # ✅ SINGLE SOURCE OF TRUTH (23 tables)
├── base.py            # Base operations class
├── memories.py        # Memory operations
├── intents.py         # Intent operations
├── sessions.py        # Session operations
├── providers.py       # Provider operations
├── users.py           # User operations
├── modes.py           # Mode operations
├── service_providers.py  # Service provider operations
├── m365.py            # M365 operations
└── actions.py         # Action operations
```

### No More Legacy!
- ❌ `memory_legacy.py` deleted
- ✅ 100% modular architecture
- ✅ Clean delegation pattern

---

## Testing

All functionality tested and working:
- ✅ MemoryStore initialization
- ✅ All 8 operation modules
- ✅ App integration
- ✅ Auth module
- ✅ Utility scripts

---

## If Something Breaks

### Rollback (unlikely needed)
```bash
# Restore from git (one commit back)
git checkout HEAD~1 -- backend/core/memory_legacy.py
git checkout HEAD~1 -- backend/core/memory/store.py

# Restart backend
pkill -f "python.*app.py"
python backend/app.py
```

### Check Logs
```bash
# Backend logs
tail -f backend/logs/app.log

# Database check
sqlite3 data/theo.db "PRAGMA table_info(sessions);"
```

---

## Documentation

Full details in:
- `docs/PHASE1_COMPLETE.md` - File organization details
- `docs/PHASE2_COMPLETE.md` - Memory refactor details
- `docs/BACKEND_CLEANUP_COMPLETE.md` - Complete summary

---

## Key Takeaways

1. **Schema changes are easier**: Update 1 file instead of 2
2. **Cleaner code**: 2,211 lines of legacy code removed
3. **Better organization**: Utility scripts in dedicated directory
4. **100% modular**: Memory system refactor complete
5. **Backwards compatible**: All existing code still works

---

**Questions?** Check the detailed docs in `docs/` directory.
