# Phase 3: Comprehensive Testing - Implementation Plan

**Started:** December 28, 2025
**Goal:** Achieve 70%+ test coverage across the entire THEO project

## Current State

**Existing Tests:**
- ✅ `backend/tests/test_action_router.py` (5,982 lines)
- ✅ `backend/tests/test_confirmation_manager.py` (10,710 lines)
- ✅ `backend/tests/test_router.py` (empty placeholder)
- ✅ `backend/tests/core/actions/test_base_handler.py`
- ✅ `backend/tests/core/actions/test_calendar_handlers.py`
- ✅ `backend/tests/core/actions/test_helpers.py`

**Current Coverage:** ~984 lines of test code (partial coverage)

**Missing:**
- Route tests (14 blueprints × 0 tests = 0%)
- Memory store tests (9 modules × 0 tests = 0%)
- Frontend tests (0 files = 0%)

## Phase 3.1: Backend Testing Infrastructure

### Step 1: Install Testing Dependencies

```bash
cd backend
pip install pytest pytest-cov pytest-mock pytest-flask
```

**Dependencies:**
- `pytest` - Test runner
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `pytest-flask` - Flask testing helpers

### Step 2: Create pytest Configuration

**File:** `backend/pytest.ini`
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --cov=.
    --cov-report=html
    --cov-report=term-missing
    --cov-config=.coveragerc
```

**File:** `backend/.coveragerc`
```ini
[run]
source = .
omit =
    */venv/*
    */tests/*
    */migrations/*
    */__pycache__/*
    */site-packages/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
```

## Phase 3.2: Backend Route Tests

**Goal:** 80% coverage for all 14 blueprints

### Directory Structure
```
backend/tests/routes/
├── __init__.py
├── conftest.py (shared fixtures)
├── test_health_routes.py
├── test_auth_routes.py
├── test_session_routes.py
├── test_message_routes.py
├── test_memory_routes.py
├── test_provider_routes.py
├── test_intent_routes.py
├── test_routing_routes.py
├── test_mode_routes.py
├── test_m365_routes.py
├── test_service_provider_routes.py
├── test_settings_routes.py
├── test_calendar_routes.py
└── test_confirmation_routes.py
```

### Shared Fixtures (conftest.py)
```python
import pytest
from app import create_app
from core.memory import MemoryStore

@pytest.fixture
def app():
    app = create_app(test_config={'TESTING': True})
    yield app

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def memory_store(app):
    return MemoryStore("sqlite:///:memory:")

@pytest.fixture
def auth_headers(client):
    # Login and return auth headers
    response = client.post('/api/auth/login', json={
        'username': 'test',
        'password': 'test'
    })
    token = response.json['token']
    return {'Authorization': f'Bearer {token}'}
```

### Test Template Example (test_health_routes.py)
```python
def test_health_endpoint(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json['status'] == 'healthy'

def test_api_health_endpoint(client):
    response = client.get('/api/health')
    assert response.status_code == 200

def test_health_overview(client, auth_headers):
    response = client.get('/api/health/overview', headers=auth_headers)
    assert response.status_code == 200
    assert 'ai_providers' in response.json
```

## Phase 3.3: Backend Memory Store Tests

**Goal:** 75% coverage for memory operations

### Directory Structure
```
backend/tests/memory/
├── __init__.py
├── conftest.py
├── test_store.py (main MemoryStore class)
├── test_memories.py (memory operations)
├── test_intents.py (intent operations)
├── test_sessions.py (session operations)
├── test_providers.py (provider operations)
├── test_users.py (user operations)
├── test_modes.py (mode operations)
├── test_service_providers.py (service provider ops)
├── test_m365.py (M365 credential ops)
└── test_actions.py (action/confirmation ops)
```

### Test Example (test_memories.py)
```python
def test_create_memory(memory_store):
    memory_id = memory_store.create_memory(
        user_id=1,
        memory_type="fact",
        key="name",
        value="John Doe"
    )
    assert memory_id is not None

def test_get_memories(memory_store):
    memory_store.create_memory(1, "fact", "key1", "value1")
    memories = memory_store.get_memories(user_id=1)
    assert len(memories) == 1
    assert memories[0]['key'] == 'key1'
```

## Phase 3.4: Frontend Testing Infrastructure

### Step 1: Install Testing Dependencies

```bash
cd frontend
npm install -D vitest @testing-library/svelte @testing-library/jest-dom jsdom
```

**Dependencies:**
- `vitest` - Modern test runner (Vite-native)
- `@testing-library/svelte` - Svelte component testing
- `@testing-library/jest-dom` - DOM assertions
- `jsdom` - Browser environment simulation

### Step 2: Configure Vitest

**File:** `frontend/vitest.config.js`
```javascript
import { defineConfig } from 'vitest/config'
import { svelte } from '@sveltejs/vite-plugin-svelte'

export default defineConfig({
  plugins: [svelte({ hot: !process.env.VITEST })],
  test: {
    globals: true,
    environment: 'jsdom',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      exclude: [
        'node_modules/',
        'dist/',
        '**/*.config.js'
      ]
    }
  }
})
```

## Phase 3.5: Frontend Component Tests

**Goal:** 70% coverage for components

### Directory Structure
```
frontend/tests/
├── unit/
│   ├── api.test.js
│   ├── components/
│   │   ├── Chat.test.js
│   │   ├── Login.test.js
│   │   ├── Settings.test.js
│   │   └── settings/
│   │       ├── GeneralSettings.test.js
│   │       ├── IntentsSettings.test.js
│   │       ├── MemorySettings.test.js
│   │       └── HealthMonitorSettings.test.js
└── integration/
    ├── login-flow.test.js
    ├── chat-flow.test.js
    └── settings-flow.test.js
```

### Test Example (Chat.test.js)
```javascript
import { render, fireEvent } from '@testing-library/svelte'
import Chat from '../../src/components/Chat.svelte'

describe('Chat Component', () => {
  it('renders chat input', () => {
    const { getByPlaceholder } = render(Chat)
    expect(getByPlaceholder('Type your message...')).toBeTruthy()
  })

  it('sends message on submit', async () => {
    const { getByPlaceholder, getByText } = render(Chat)
    const input = getByPlaceholder('Type your message...')

    await fireEvent.input(input, { target: { value: 'Hello' } })
    await fireEvent.submit(input.closest('form'))

    // Assert message sent
  })
})
```

## Phase 3.6: Integration Tests

**Goal:** Critical user flows covered

### Test Scenarios

1. **Login Flow**
   - User can login with valid credentials
   - User receives error with invalid credentials
   - Token is stored and used for authenticated requests

2. **Chat Flow**
   - User can create new session
   - User can send message
   - Response is received and displayed
   - Session is saved to sidebar

3. **Settings Flow**
   - User can update system prompt
   - User can create/edit/delete intents
   - User can add AI providers
   - Changes persist across page reload

## Phase 3.7: Coverage Goals

**Target Coverage:**
- Backend Routes: **80%**
- Backend Memory: **75%**
- Backend Actions: **85%** (already tested)
- Frontend Components: **70%**
- Frontend Integration: **60%**

**Overall Target:** **70%+** across entire project

## Implementation Timeline

**Estimated Time:** 2-3 days

**Day 1: Backend Testing**
- Set up pytest infrastructure (1 hour)
- Write route tests for 14 blueprints (4 hours)
- Write memory store tests (3 hours)

**Day 2: Frontend Testing**
- Set up Vitest infrastructure (1 hour)
- Write component unit tests (5 hours)
- Write integration tests (2 hours)

**Day 3: Coverage & Polish**
- Run full test suite (1 hour)
- Identify gaps and add tests (4 hours)
- Generate coverage reports (1 hour)
- Document results (2 hours)

## Success Criteria

✅ All test suites pass
✅ Backend coverage > 70%
✅ Frontend coverage > 70%
✅ Critical user flows tested
✅ CI/CD ready (tests can run in pipeline)
✅ Coverage reports generated

## Commands Reference

**Backend:**
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/routes/test_auth_routes.py

# Run specific test
pytest tests/routes/test_auth_routes.py::test_login
```

**Frontend:**
```bash
# Run all tests
npm run test

# Run with coverage
npm run test:coverage

# Run in watch mode
npm run test:watch
```

---

**Status:** Ready to implement
**Next:** Install testing dependencies and create infrastructure
