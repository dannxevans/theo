# Backend Cleanup and Refactor Plan

**Date**: December 29, 2025
**Related Issues**: #65 (Backend Refactor), #66 (File Organization)
**Status**: Planning Phase

---

## Executive Summary

Both issues (#65 and #66) address different aspects of backend technical debt:
- **Issue #65**: Incomplete memory system refactor (70% complete)
- **Issue #66**: Misplaced files in backend root directory

These can be addressed together in a coordinated cleanup effort that will:
1. Organize misplaced files into proper directories
2. Complete the memory system refactor
3. Establish clear architecture patterns for future development

---

## Phase 1: Quick Wins - File Organization (Issue #66)

**Effort**: 15-30 minutes
**Risk**: Low
**Priority**: High (easy improvements)

### Step 1.1: Create Scripts Directory
```bash
mkdir -p backend/scripts
```

### Step 1.2: Move Utility Scripts
```bash
# Move CLI utilities
mv backend/reset_password.py backend/scripts/
mv backend/test_m365_auth.py backend/scripts/
```

**Files to update after move**:
- None (these are standalone scripts)
- Update any documentation referencing these paths

### Step 1.3: Handle Migration Duplicate
```bash
# Compare the two files
diff backend/migrate_add_metadata.py backend/migrations/002_add_turns_metadata.py

# Action based on comparison:
# - If identical/redundant: DELETE migrate_add_metadata.py
# - If different: Move to migrations/ with proper numbering
```

### Step 1.4: Consolidate Auth Module
**Option A (Recommended): Move to auth/password.py**
```bash
mv backend/auth.py backend/auth/password.py

# Update auth/__init__.py
cat >> backend/auth/__init__.py << 'EOF'
# Export password functions
from .password import (
    hash_password,
    verify_password,
    generate_session_token,
    init_default_user,
    create_session,
    require_auth,
    require_admin
)

# Export M365 OAuth
from .m365_oauth import *

__all__ = [
    'hash_password',
    'verify_password',
    'generate_session_token',
    'init_default_user',
    'create_session',
    'require_auth',
    'require_admin'
]
EOF
```

**Files to update**:
1. `backend/app.py`:
   ```python
   # Before
   from auth import init_default_user

   # After
   from auth import init_default_user  # No change needed if using __init__.py exports
   ```

2. `backend/routes/auth_routes.py`:
   ```python
   # Before
   from auth import hash_password, verify_password, ...

   # After
   from auth import hash_password, verify_password, ...  # No change if using exports
   ```

3. `backend/scripts/reset_password.py` (after move):
   ```python
   # Before
   from auth import hash_password

   # After
   import sys
   sys.path.append('../')  # Add parent to path
   from auth import hash_password
   ```

### Step 1.5: Testing
```bash
# Run tests
cd backend
pytest

# Test scripts
python scripts/reset_password.py --help
python scripts/test_m365_auth.py
```

---

## Phase 2: Memory System Refactor Completion (Issue #65)

**Effort**: 4-6 hours
**Risk**: Medium (comprehensive tests exist)
**Priority**: Medium (technical debt, but working)

### Current State Analysis

**Legacy System** (`memory_legacy.py`):
- 2,211 lines, 88 methods
- Contains all table definitions
- Base class for new system

**New System** (`backend/core/memory/`):
- Modular architecture (70% complete)
- 9 operation modules (all implemented)
- Inherits from legacy for compatibility

**The Problem**: Dual schema definitions
- `memory_legacy.py` - inline table definitions (currently used)
- `schema.py` - centralized schemas (for future use)
- Schema changes must update BOTH files ⚠️

### Step 2.1: Audit All Methods

Create a mapping of all 88 legacy methods:

```bash
# Extract all methods from legacy
grep -E "^    def " backend/core/memory_legacy.py > /tmp/legacy_methods.txt

# Extract all delegated methods from new store
grep -E "^    def " backend/core/memory/store.py > /tmp/new_methods.txt

# Compare
diff /tmp/legacy_methods.txt /tmp/new_methods.txt
```

**Expected Result**: List of methods not yet delegated to modular components.

### Step 2.2: Move Table Definitions to schema.py

**Currently** (`memory_legacy.py`):
```python
class MemoryStore:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.meta = MetaData()

        # Inline table definitions
        self.users = Table("users", self.meta, ...)
        self.sessions = Table("sessions", self.meta, ...)
        # ... all tables defined here
```

**Target** (`schema.py`):
```python
# Centralized schema
from sqlalchemy import MetaData, Table, Column, ...

def get_schema(meta: MetaData) -> dict:
    """Get all table definitions."""

    users = Table("users", meta, ...)
    sessions = Table("sessions", meta, ...)
    # ... all tables

    return {
        "users": users,
        "sessions": sessions,
        # ...
    }
```

**New store.py** (no inheritance):
```python
from .schema import get_schema

class MemoryStore:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.meta = MetaData()

        # Get tables from centralized schema
        tables = get_schema(self.meta)
        self.users = tables["users"]
        self.sessions = tables["sessions"]
        # ...

        # Create all tables
        self.meta.create_all(self.engine)

        # Initialize session maker
        self.Session = sessionmaker(bind=self.engine)

        # Initialize modular operations
        self._memory_ops = MemoryOperations(tables, self.Session, self.engine)
        # ...
```

### Step 2.3: Remove Legacy Inheritance

**Before**:
```python
from core.memory_legacy import MemoryStore as LegacyMemoryStore

class MemoryStore(LegacyMemoryStore):
    def __init__(self, db_url):
        super().__init__(db_url)  # ← Remove this
        # ...
```

**After**:
```python
class MemoryStore:
    def __init__(self, db_url):
        # Initialize engine and metadata directly
        self.engine = create_engine(db_url)
        self.meta = MetaData()
        # ...
```

### Step 2.4: Implement Any Missing Methods

Check the diff from Step 2.1. For any methods not yet delegated:
- Implement in appropriate operation module
- Add delegation in `store.py`

### Step 2.5: Testing

```bash
# Run full test suite
cd backend
pytest tests/memory/ -v
pytest tests/routes/ -v

# Integration tests
pytest tests/ -v

# Manual smoke tests
python -c "from core.memory import MemoryStore; from config import Config; m = MemoryStore(Config.DATABASE_URL); print('✓ Import works')"
```

### Step 2.6: Delete Legacy File

Only after all tests pass:
```bash
rm backend/core/memory_legacy.py
```

### Step 2.7: Update Documentation

Update:
- `docs/REFACTOR_ANALYSIS.md` - Mark as complete
- `README.md` - Update architecture section
- Inline comments in `store.py` - Remove "backwards compatibility" notes

---

## Phase 3: Establish Best Practices

### Directory Structure Standard

Document the final structure:

```
backend/
├── app.py                  # Main Flask application
├── config.py               # Configuration
├── db_backup.py            # Database utilities
├── requirements.txt        # Dependencies
├── Dockerfile              # Container config
├── pytest.ini              # Test config
│
├── actions/                # Action/tool system
├── auth/                   # Authentication
│   ├── __init__.py        # Public API
│   ├── password.py        # Password & session management
│   └── m365_oauth.py      # OAuth implementation
│
├── core/                   # Core modules
│   ├── memory/            # Memory system (modular)
│   │   ├── __init__.py
│   │   ├── store.py       # Main facade
│   │   ├── schema.py      # ✅ Single source of truth for schemas
│   │   ├── base.py
│   │   ├── actions.py
│   │   ├── intents.py
│   │   ├── memories.py
│   │   ├── modes.py
│   │   ├── providers.py
│   │   ├── sessions.py
│   │   ├── users.py
│   │   ├── m365.py
│   │   └── service_providers.py
│   ├── router.py
│   ├── context.py
│   └── ...
│
├── migrations/             # Database migrations
│   ├── 001_*.py
│   ├── 002_*.py
│   ├── 003_*.py
│   └── README.md
│
├── providers/              # AI provider implementations
├── routes/                 # Flask blueprints
│
├── scripts/                # ✅ NEW - Utility scripts
│   ├── reset_password.py
│   └── test_m365_auth.py
│
├── tests/                  # Test suite
│   ├── memory/
│   ├── routes/
│   └── ...
│
├── voice/                  # Voice features
└── venv/                   # Virtual environment
```

### Schema Change Process

Going forward, when adding database columns:

1. ✅ Update `backend/core/memory/schema.py` (single source of truth)
2. ✅ Create migration in `backend/migrations/00X_description.py`
3. ✅ Run migration
4. ✅ Update tests
5. ❌ NO MORE updating multiple files for schema changes!

---

## Implementation Timeline

### Option A: All At Once (Recommended if time available)
**Total Time**: 5-7 hours
**Sequence**:
1. Phase 1 (file org): 30 min
2. Test Phase 1: 15 min
3. Phase 2 (refactor): 4-6 hours
4. Test Phase 2: 30 min
5. Documentation: 30 min

**Benefits**:
- ✅ Clean slate, no intermediate states
- ✅ All related work done together
- ✅ Complete closure on technical debt

**Drawbacks**:
- ⚠️ Requires extended focused time
- ⚠️ Higher risk if something breaks

### Option B: Phased Approach (Recommended for safety)
**Total Time**: Same, but spread over 2-3 sessions

**Session 1 (30 min)**:
- Complete Phase 1 (file organization)
- Test thoroughly
- Commit changes
- Deploy if needed

**Session 2 (4-6 hours)**:
- Complete Phase 2 (memory refactor)
- Extensive testing
- Commit changes

**Session 3 (30 min)**:
- Update documentation
- Final cleanup
- Close issues

**Benefits**:
- ✅ Lower risk - can rollback between phases
- ✅ Can validate each phase independently
- ✅ Easier to fit into schedule

**Drawbacks**:
- ⚠️ Intermediate states (but each is stable)

---

## Risk Assessment

### Low Risk (Phase 1 - File Organization)
- ✅ Comprehensive test suite exists
- ✅ Changes are mostly file moves
- ✅ Import updates are straightforward
- ✅ Easy to rollback

### Medium Risk (Phase 2 - Refactor Completion)
- ✅ Good test coverage
- ✅ 70% already complete
- ⚠️ Schema migration is critical
- ⚠️ Must verify all 88 methods covered
- ✅ Can test extensively before deleting legacy

### Mitigation Strategies

1. **Database Backup**:
   ```bash
   cp data/theo.db data/theo.db.backup.$(date +%Y%m%d)
   ```

2. **Git Branch**:
   ```bash
   git checkout -b refactor/backend-cleanup
   # Make changes
   # Test extensively
   # Only merge when confident
   ```

3. **Staged Rollout**:
   - Test locally first
   - Deploy to dev/staging
   - Monitor for issues
   - Deploy to production

4. **Comprehensive Testing**:
   ```bash
   # Unit tests
   pytest tests/memory/ -v

   # Integration tests
   pytest tests/routes/ -v

   # Manual smoke tests
   - Test login
   - Test chat
   - Test mode switching
   - Test PII filtering
   - Test all settings pages
   ```

---

## Success Criteria

### Phase 1 Complete When:
- ✅ All 4 misplaced files reorganized
- ✅ All tests passing
- ✅ Scripts work from new locations
- ✅ No import errors
- ✅ Documentation updated

### Phase 2 Complete When:
- ✅ `memory_legacy.py` deleted
- ✅ All tests passing
- ✅ Schema in single location (`schema.py`)
- ✅ No inheritance from legacy
- ✅ All 88 methods accounted for
- ✅ Application works identically
- ✅ Documentation updated

### Overall Success When:
- ✅ Both GitHub issues closed
- ✅ Cleaner codebase
- ✅ Single source of truth for schemas
- ✅ Better organization
- ✅ Future developers can understand architecture easily

---

## Rollback Plan

If issues arise during Phase 2:

1. **Revert Git Changes**:
   ```bash
   git checkout main
   git branch -D refactor/backend-cleanup
   ```

2. **Restore Database** (if needed):
   ```bash
   cp data/theo.db.backup.YYYYMMDD data/theo.db
   ```

3. **Restart Services**:
   ```bash
   # Backend
   pkill -f "python.*app.py"
   python backend/app.py &

   # Frontend
   cd frontend && npm run dev
   ```

---

## Recommended Next Steps

1. **Review this plan** - Make sure approach makes sense
2. **Choose implementation strategy** - All at once vs phased
3. **Schedule time** - Block 5-7 hours if doing all at once
4. **Create git branch** - `git checkout -b refactor/backend-cleanup`
5. **Backup database** - Safety first
6. **Execute Phase 1** - Quick wins
7. **Test Phase 1** - Verify everything works
8. **Execute Phase 2** - Complete refactor
9. **Extensive testing** - Don't skip this!
10. **Update docs and close issues** - Celebrate! 🎉

---

## Notes

- The modular architecture is already 70% complete - we're finishing what was started
- Phase 1 is low-risk and provides immediate benefits
- Phase 2 is higher effort but eliminates the dual-schema problem
- Both phases together create a much cleaner, more maintainable codebase
- Future schema changes will be much easier (single file to update)

---

## Questions to Resolve

1. **Timing**: Do this all at once or spread across multiple sessions?
2. **Testing**: Any specific scenarios we should test beyond the standard suite?
3. **Deployment**: Test in dev environment first or go straight to production after local testing?
4. **Documentation**: Any other docs that need updating beyond what's listed?

---

## Conclusion

Both issues (#65 and #66) are related to backend organization and can be efficiently addressed together. The work is well-scoped, has clear success criteria, and comes with appropriate risk mitigation strategies.

**Total Effort**: 5-7 hours
**Risk Level**: Low to Medium (with mitigation)
**Impact**: High (cleaner architecture, easier maintenance)
**Recommendation**: Proceed with phased approach for safety
