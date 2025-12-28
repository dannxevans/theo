# THEO Refactoring Implementation Plan

**Created:** December 28, 2025
**Issue:** #46 - Full Code Review
**Status:** Ready to implement

## Quick Summary

This document provides step-by-step instructions for refactoring THEO's codebase to improve maintainability and organization.

## Route Categorization (app.py - 2,090 lines, 63 routes)

### Health Routes (4 routes)
- GET `/health`
- GET `/api/health`
- GET `/api/health/overview`
- POST `/api/health/test-m365`

### Auth Routes (4 routes)
- POST `/api/auth/login`
- POST `/api/auth/logout`
- GET `/api/auth/verify`
- POST `/api/auth/change-password`

### Session Routes (7 routes)
- GET `/api/session/<session_id>`
- GET `/api/sessions`
- GET `/api/sessions/<session_id>/messages`
- DELETE `/api/sessions/<session_id>`
- GET `/api/sessions/<session_id>/export`
- POST `/api/sessions/<session_id>/fork`
- POST `/api/sessions/<session_id>/generate-title`

### Message Routes (2 routes)
- POST `/api/chat`
- GET `/api/stream/<session_id>`

### Memory Routes (7 routes)
- POST `/api/memory/remember`
- POST `/api/memory/forget`
- GET `/api/memories`
- POST `/api/memories`
- DELETE `/api/memories/<int:memory_id>`
- POST `/api/memories/<int:memory_id>/pin`
- GET `/api/memories/relevant`

### Provider Routes (5 routes)
- GET `/api/providers`
- POST `/api/providers`
- DELETE `/api/providers/<provider_id>`
- GET `/api/providers/health`
- GET `/api/providers/<provider_id>/metadata`
- POST `/api/providers/<provider_id>/metadata`

### Intent Routes (5 routes)
- GET `/api/intents`
- GET `/api/intents/<intent_id>`
- POST `/api/intents`
- PUT `/api/intents/<intent_id>`
- DELETE `/api/intents/<intent_id>`

### Routing Routes (3 routes)
- GET `/api/routing`
- POST `/api/routing`
- DELETE `/api/routing/<intent>`

### Mode Routes (9 routes)
- GET `/api/mode`
- POST `/api/mode`
- GET `/api/mode/settings`
- GET `/api/mode/settings/<mode>`
- POST `/api/mode/settings/<mode>`
- GET `/api/mode/work/subtab/<subtab>`
- POST `/api/mode/work/subtab/<subtab>`
- GET `/api/mode/work/subtabs`

### M365 Routes (4 routes)
- POST `/api/m365/auth/start`
- POST `/api/m365/auth/poll`
- GET `/api/m365/status`
- POST `/api/m365/disconnect`

### Service Provider Routes (4 routes)
- GET `/api/service-providers`
- POST `/api/service-providers`
- GET `/api/service-providers/<int:provider_id>`
- PUT `/api/service-providers/<int:provider_id>`
- DELETE `/api/service-providers/<int:provider_id>`

### Settings Routes (3 routes)
- GET `/api/settings/debug`
- POST `/api/settings/debug`
- GET `/api/settings/system-prompt`
- POST `/api/settings/system-prompt`

### Calendar Routes (1 route)
- POST `/api/calendar/query`

### Confirmation Routes (3 routes)
- GET `/api/confirmations/pending`
- POST `/api/confirmations/<int:confirmation_id>/approve`
- POST `/api/confirmations/<int:confirmation_id>/reject`

## Phase 1: Backend Refactoring

### Step 1.1: Create Routes Directory Structure

```bash
mkdir -p backend/routes
touch backend/routes/__init__.py
touch backend/routes/health_routes.py
touch backend/routes/auth_routes.py
touch backend/routes/session_routes.py
touch backend/routes/message_routes.py
touch backend/routes/memory_routes.py
touch backend/routes/provider_routes.py
touch backend/routes/intent_routes.py
touch backend/routes/routing_routes.py
touch backend/routes/mode_routes.py
touch backend/routes/m365_routes.py
touch backend/routes/service_provider_routes.py
touch backend/routes/settings_routes.py
touch backend/routes/calendar_routes.py
touch backend/routes/confirmation_routes.py
```

### Step 1.2: Extract Routes to Blueprints

Each route file should:
1. Import Flask Blueprint
2. Define blueprint with appropriate prefix
3. Move route handlers from app.py
4. Import necessary dependencies
5. Maintain same functionality

**Example template (health_routes.py):**

```python
from flask import Blueprint, jsonify

health_bp = Blueprint('health', __name__)

@health_bp.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

@health_bp.route("/api/health")
def api_health():
    return jsonify({"status": "healthy"}), 200

# ... more health routes
```

### Step 1.3: Register Blueprints in app.py

```python
from routes.health_routes import health_bp
from routes.auth_routes import auth_bp
# ... import all blueprints

app.register_blueprint(health_bp)
app.register_blueprint(auth_bp)
# ... register all blueprints
```

### Step 1.4: Extract Action Handlers

```bash
mkdir -p backend/core/actions
touch backend/core/actions/__init__.py
touch backend/core/actions/base_handler.py
touch backend/core/actions/calendar_handlers.py
touch backend/core/actions/email_handlers.py
touch backend/core/actions/confirmation_handlers.py
```

Move handlers from `action_router.py` to specific files:
- Calendar: `_handle_read_calendar`, `_handle_book_appointment`, `_handle_update_appointment`, `_handle_cancel_appointment`
- Email: `_handle_read_email`, `_handle_compose_email`
- Confirmation: `_handle_approve_confirmation`, `_handle_reject_confirmation`

### Step 1.5: Refactor memory.py

```bash
mkdir -p backend/core/memory
touch backend/core/memory/__init__.py
touch backend/core/memory/store.py
touch backend/core/memory/queries.py
touch backend/core/memory/providers.py
touch backend/core/memory/sessions.py
touch backend/core/memory/memories.py
touch backend/core/memory/utils.py
```

Extract components:
- `store.py`: Main MemoryStore class
- `queries.py`: SQL query builders
- `providers.py`: Provider-related methods
- `sessions.py`: Session-related methods
- `memories.py`: Memory CRUD operations
- `utils.py`: Helper functions

## Phase 2: Frontend Refactoring

### Step 2.1: Split Settings.svelte

```bash
mkdir -p frontend/src/components/settings
touch frontend/src/components/settings/SettingsContainer.svelte
touch frontend/src/components/settings/GeneralSettings.svelte
touch frontend/src/components/settings/IntentsSettings.svelte
touch frontend/src/components/settings/RoutingSettings.svelte
touch frontend/src/components/settings/MemorySettings.svelte
touch frontend/src/components/settings/AIProvidersSettings.svelte
touch frontend/src/components/settings/IntegrationsSettings.svelte
touch frontend/src/components/settings/ServiceProvidersSettings.svelte
touch frontend/src/components/settings/WorkModeSettings.svelte
touch frontend/src/components/settings/PersonalModeSettings.svelte
touch frontend/src/components/settings/AccountSettings.svelte
touch frontend/src/components/settings/HealthMonitorSettings.svelte
```

Each component should:
- Handle its own state
- Accept props from parent container
- Emit events for user actions
- Be < 300 lines

### Step 2.2: CSS Consolidation

```bash
mkdir -p frontend/src/styles/components
touch frontend/src/styles/global.css
touch frontend/src/styles/variables.css
touch frontend/src/styles/components/buttons.css
touch frontend/src/styles/components/forms.css
touch frontend/src/styles/components/cards.css
touch frontend/src/styles/components/modals.css
touch frontend/src/styles/components/health-monitor.css
touch frontend/src/styles/utilities.css
```

Extract:
- Global styles from public/style.css
- Component-specific styles from .svelte files
- Common patterns into utility classes

## Phase 3: Testing

### Step 3.1: Backend Tests

```bash
mkdir -p backend/tests/routes
mkdir -p backend/tests/actions
mkdir -p backend/tests/memory

touch backend/tests/routes/test_auth_routes.py
touch backend/tests/routes/test_session_routes.py
touch backend/tests/routes/test_message_routes.py
# ... etc

touch backend/tests/actions/test_calendar_handlers.py
touch backend/tests/actions/test_email_handlers.py
touch backend/tests/actions/test_confirmation_handlers.py

touch backend/tests/memory/test_store.py
touch backend/tests/memory/test_providers.py
touch backend/tests/memory/test_sessions.py
```

**Test Coverage Goals:**
- Routes: 80%
- Action handlers: 85%
- Memory operations: 75%
- Overall backend: 70%+

### Step 3.2: Frontend Tests

```bash
mkdir -p frontend/tests/unit/components
mkdir -p frontend/tests/integration

touch frontend/tests/unit/api.test.js
touch frontend/tests/unit/components/Chat.test.js
touch frontend/tests/unit/components/Settings.test.js
touch frontend/tests/integration/login-flow.test.js
touch frontend/tests/integration/chat-flow.test.js
```

## Phase 4: Documentation

### Step 4.1: Update README.md

Add sections:
- [ ] Architecture overview diagram
- [ ] Detailed setup instructions
- [ ] Configuration guide
- [ ] API documentation summary
- [ ] Deployment guide
- [ ] Troubleshooting
- [ ] Contributing guidelines

### Step 4.2: Create GitHub Wiki

Create pages:
- [ ] Home (overview & quick start)
- [ ] Architecture
  - [ ] System Architecture
  - [ ] Database Schema
  - [ ] API Design
  - [ ] Frontend Architecture
- [ ] Features
  - [ ] Multi-model Routing
  - [ ] Action System
  - [ ] Confirmation Flow
  - [ ] M365 Integration
  - [ ] Memory System
- [ ] Development
  - [ ] Setup Guide
  - [ ] Code Standards
  - [ ] Testing Guide
  - [ ] Debugging Tips
- [ ] Deployment
  - [ ] AWS Deployment
  - [ ] Environment Variables
  - [ ] Database Migrations
- [ ] API Reference
  - [ ] Authentication
  - [ ] Sessions
  - [ ] Messages
  - [ ] Providers
  - [ ] M365 Operations

### Step 4.3: Add Inline Documentation

- [ ] Add docstrings to all public functions
- [ ] Document complex algorithms
- [ ] Add JSDoc comments to frontend functions
- [ ] Document component props
- [ ] Add API endpoint documentation

## Implementation Order

**Recommended sequence:**

1. **Week 1: Core Backend (Highest Impact)**
   - Day 1-2: Create route blueprints structure
   - Day 3-4: Extract and test health, auth, session routes
   - Day 5: Extract and test remaining routes

2. **Week 2: Action Router & Memory**
   - Day 1-2: Extract action handlers
   - Day 3-4: Refactor memory.py
   - Day 5: Add tests for extracted modules

3. **Week 3: Frontend**
   - Day 1-3: Split Settings.svelte
   - Day 4: Consolidate CSS
   - Day 5: Add component tests

4. **Week 4: Documentation & Polish**
   - Day 1-2: Expand test coverage
   - Day 3: Update README
   - Day 4-5: Create GitHub Wiki

## Testing Strategy

**After each refactor:**
1. Run existing tests: `pytest backend/tests/`
2. Test manually in browser
3. Check all routes still work
4. Verify no regressions

**Before committing:**
1. Run full test suite
2. Check linting
3. Verify build succeeds
4. Test critical user flows

## Rollback Plan

If issues arise:
1. Each refactor should be in its own commit
2. Use feature branches for major changes
3. Can revert individual commits
4. Keep old code commented until verified

## Success Criteria

- [ ] No file exceeds 1,000 lines
- [ ] All routes extracted to blueprints
- [ ] Action handlers modularized
- [ ] Settings.svelte split into < 300 line components
- [ ] CSS organized and consolidated
- [ ] Test coverage > 70%
- [ ] README comprehensive
- [ ] Wiki created with major sections
- [ ] All public APIs documented

## Notes

- Maintain backward compatibility
- Keep existing functionality intact
- Add tests before refactoring when possible
- Document as you go
- Use TODO comments for future improvements

---

**Next Steps:** Start with Step 1.1 - Create routes directory structure

