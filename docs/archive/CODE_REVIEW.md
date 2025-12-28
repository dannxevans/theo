# THEO Code Review & Refactoring Plan

**Date:** December 28, 2025
**Status:** In Progress

## Executive Summary

This document outlines the code quality issues identified in the THEO codebase and provides a comprehensive refactoring plan to improve maintainability, testability, and documentation.

## Issues Identified

### 1. Large Files Requiring Refactoring

| File | Lines | Priority | Proposed Action |
|------|-------|----------|----------------|
| `frontend/src/components/Settings.svelte` | 2,777 | HIGH | Split into sub-components |
| `backend/core/action_router.py` | 2,369 | HIGH | Extract action handlers into separate modules |
| `backend/core/memory.py` | 2,207 | MEDIUM | Extract query builders and utilities |
| `backend/app.py` | 2,090 | HIGH | Extract routes into blueprints/routers |

### 2. CSS Organization Issues

**Current State:**
- CSS scattered across multiple component files
- Inline styles mixed with component logic
- Main stylesheet at 1,276 lines

**Proposed Solution:**
- Consolidate component-specific CSS into dedicated files
- Use CSS modules or component-scoped styles
- Extract common utilities to shared CSS files

### 3. Testing Gaps

**Current Test Coverage:**
```
backend/tests/
  └── test_confirmation_manager.py (332 lines)
```

**Missing Tests:**
- Action router handlers
- M365 provider integration
- Memory store operations
- API endpoints
- Frontend components

### 4. Documentation Needs

**Current Documentation:**
- README.md (basic)
- IMPLEMENTATION_PLAN.md (detailed)
- Missing: Architecture docs, API docs, deployment guide

## Refactoring Plan

### Phase 1: Backend Modularization (Priority: HIGH)

#### 1.1 Split `app.py` (2,090 lines)

**Create route blueprints:**
```
backend/routes/
  ├── __init__.py
  ├── auth_routes.py          # Login, logout, session management
  ├── session_routes.py        # Chat sessions CRUD
  ├── message_routes.py        # Message operations
  ├── provider_routes.py       # AI provider management
  ├── intent_routes.py         # Intent management
  ├── memory_routes.py         # Memory operations
  ├── m365_routes.py          # M365 OAuth and operations
  ├── confirmation_routes.py   # Confirmation approvals
  └── health_routes.py        # Health monitoring
```

**Benefits:**
- Each route file < 300 lines
- Clear separation of concerns
- Easier testing and maintenance
- Better code navigation

#### 1.2 Split `action_router.py` (2,369 lines)

**Extract action handlers:**
```
backend/core/actions/
  ├── __init__.py
  ├── base_handler.py         # Base action handler class
  ├── calendar_handlers.py    # Calendar operations (read, book, update, cancel)
  ├── email_handlers.py       # Email operations (read, compose, send)
  └── confirmation_handlers.py # Approval/rejection handlers
```

**Current structure:**
- `_handle_read_calendar()` - 100+ lines
- `_handle_book_appointment()` - 200+ lines
- `_handle_update_appointment()` - 150+ lines
- `_handle_cancel_appointment()` - 100+ lines
- `_handle_read_email()` - 100+ lines
- `_handle_compose_email()` - 300+ lines
- `_handle_approve_confirmation()` - 70 lines
- `_handle_reject_confirmation()` - 70 lines

**Benefits:**
- Each handler file < 500 lines
- Reusable base handler class
- Easier to add new action types
- Better test isolation

#### 1.3 Refactor `memory.py` (2,207 lines)

**Extract components:**
```
backend/core/memory/
  ├── __init__.py
  ├── store.py               # Main MemoryStore class (< 500 lines)
  ├── queries.py             # Query builders
  ├── providers.py           # Provider operations
  ├── sessions.py            # Session operations
  ├── memories.py            # Memory CRUD operations
  └── utils.py               # Helper functions
```

**Benefits:**
- Logical grouping of related operations
- Easier to understand and maintain
- Better test coverage possible

### Phase 2: Frontend Refactoring (Priority: HIGH)

#### 2.1 Split `Settings.svelte` (2,777 lines)

**Extract sub-components:**
```
frontend/src/components/settings/
  ├── SettingsContainer.svelte      # Main container (< 200 lines)
  ├── GeneralSettings.svelte        # System prompt config
  ├── IntentsSettings.svelte        # Intent management
  ├── RoutingSettings.svelte        # Routing rules
  ├── MemorySettings.svelte         # Memory management
  ├── AIProvidersSettings.svelte    # AI provider config
  ├── IntegrationsSettings.svelte   # M365/OAuth
  ├── ServiceProvidersSettings.svelte # Service providers
  ├── WorkModeSettings.svelte       # Work mode config
  ├── PersonalModeSettings.svelte   # Personal mode config
  ├── AccountSettings.svelte        # Password & security
  └── HealthMonitorSettings.svelte  # Health dashboard
```

**Benefits:**
- Each component < 300 lines
- Clear single responsibility
- Easier to test components individually
- Better code reusability

#### 2.2 CSS Consolidation

**Extract component styles:**
```
frontend/src/styles/
  ├── global.css              # Global styles
  ├── variables.css           # CSS variables
  ├── components/
  │   ├── buttons.css
  │   ├── forms.css
  │   ├── cards.css
  │   ├── modals.css
  │   └── health-monitor.css
  └── utilities.css           # Utility classes
```

**Move inline styles to:**
- Component-scoped `<style>` blocks
- CSS modules
- Shared utility classes

### Phase 3: Testing (Priority: MEDIUM)

#### 3.1 Backend Tests

**Add test files:**
```
backend/tests/
  ├── test_action_router.py          # Action router tests
  ├── test_calendar_handlers.py      # Calendar action tests
  ├── test_email_handlers.py         # Email action tests
  ├── test_memory_store.py           # Memory operations tests
  ├── test_m365_provider.py          # M365 integration tests
  ├── test_router.py                 # Intent routing tests
  ├── test_api_auth.py               # Auth endpoints tests
  ├── test_api_sessions.py           # Session endpoints tests
  └── test_api_messages.py           # Message endpoints tests
```

**Target Coverage:**
- Backend: 70%+
- Critical paths: 90%+

#### 3.2 Frontend Tests

**Add test files:**
```
frontend/tests/
  ├── unit/
  │   ├── api.test.js
  │   ├── components/
  │   │   ├── Chat.test.js
  │   │   ├── Settings.test.js
  │   │   └── ...
  └── integration/
      ├── login-flow.test.js
      ├── chat-flow.test.js
      └── settings-flow.test.js
```

### Phase 4: Documentation (Priority: MEDIUM)

#### 4.1 README Updates

**Add sections:**
- Architecture overview with diagrams
- Detailed setup instructions
- Configuration guide
- Deployment instructions
- Troubleshooting guide
- Contributing guidelines

#### 4.2 GitHub Wiki

**Create wiki pages:**
- Home (overview & quick start)
- Architecture
  - System Architecture
  - Database Schema
  - API Design
  - Frontend Architecture
- Features
  - Multi-model Routing
  - Action System
  - Confirmation Flow
  - M365 Integration
  - Memory System
- Development
  - Setup Guide
  - Code Standards
  - Testing Guide
  - Debugging Tips
- Deployment
  - AWS Deployment
  - Environment Variables
  - Database Migrations
- API Reference
  - Authentication
  - Sessions
  - Messages
  - Providers
  - M365 Operations

#### 4.3 Inline Documentation

**Add JSDoc/docstrings:**
- All public functions
- Complex algorithms
- API endpoints
- Component props

## Implementation Timeline

### Week 1: Backend Refactoring
- [ ] Split app.py into route blueprints
- [ ] Extract action handlers from action_router.py
- [ ] Add tests for extracted modules

### Week 2: Frontend Refactoring
- [ ] Split Settings.svelte into sub-components
- [ ] Consolidate CSS into organized files
- [ ] Add component tests

### Week 3: Testing & Documentation
- [ ] Increase test coverage to 70%
- [ ] Update README with comprehensive docs
- [ ] Create GitHub Wiki structure
- [ ] Add inline documentation

## Success Metrics

- [ ] No file exceeds 1,000 lines
- [ ] Test coverage > 70%
- [ ] All public APIs documented
- [ ] README comprehensive enough for new developers
- [ ] Wiki covers all major features

## Notes

- Maintain backward compatibility during refactoring
- Use feature flags for major changes
- Run full test suite after each refactor
- Update deployment scripts if needed

---

**Last Updated:** December 28, 2025
