# THEO Architecture

This document provides a comprehensive overview of THEO's system architecture, design decisions, and technical implementation.

---

## 📐 System Overview

THEO follows a clean three-tier architecture:

```
┌─────────────────────────────────────────────────┐
│          Frontend (Svelte/Vite)                 │
│  - Chat Interface                               │
│  - Settings Management                          │
│  - Real-time Streaming (SSE)                    │
└──────────────────┬──────────────────────────────┘
                   │ HTTP/SSE
                   ↓
┌─────────────────────────────────────────────────┐
│          Backend (Flask/Python)                 │
│  - REST API (63+ endpoints)                     │
│  - Intent Classification                        │
│  - Multi-Model Routing                          │
│  - Action Execution                             │
│  - Provider Health Monitoring                   │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        ↓                     ↓
┌───────────────┐    ┌────────────────┐
│   SQLite DB   │    │  External APIs │
│  (+ S3 Backup)│    │  - OpenAI      │
│               │    │  - Anthropic   │
│               │    │  - M365 Graph  │
└───────────────┘    └────────────────┘
```

---

## 🗂️ Backend Architecture

### Modular Structure

The backend has been refactored into a highly modular architecture:

```
backend/
├── app.py                      # Flask app (135 lines, 94% reduction)
├── routes/                     # 14 modular blueprints
│   ├── auth_routes.py          # Authentication
│   ├── session_routes.py       # Chat sessions
│   ├── message_routes.py       # Messages
│   ├── memory_routes.py        # Memory CRUD
│   ├── provider_routes.py      # AI providers
│   ├── intent_routes.py        # Intent management
│   ├── routing_routes.py       # Routing rules
│   ├── mode_routes.py          # Work/Personal modes
│   ├── m365_routes.py          # Microsoft 365
│   ├── service_provider_routes.py
│   ├── settings_routes.py      # System settings
│   ├── calendar_routes.py      # Calendar operations
│   ├── confirmation_routes.py  # Action approvals
│   └── health_routes.py        # Health monitoring
├── core/
│   ├── router.py               # Intent classification
│   ├── action_router.py        # Action dispatch
│   ├── context.py              # Context building
│   ├── confirmation_manager.py # Approval workflow
│   ├── provider_registry.py    # Provider management
│   ├── actions/                # 5 action handler modules
│   │   ├── base_handler.py     # Base class
│   │   ├── helpers.py          # Utilities
│   │   ├── calendar_handlers.py
│   │   ├── email_handlers.py
│   │   └── confirmation_handlers.py
│   └── memory/                 # 12 memory modules
│       ├── store.py            # Main MemoryStore
│       ├── schema.py           # Database tables
│       ├── base.py             # Base operations
│       ├── memories.py         # Memory CRUD
│       ├── intents.py          # Intent operations
│       ├── sessions.py         # Session management
│       ├── providers.py        # Provider operations
│       ├── users.py            # User management
│       ├── modes.py            # Mode configuration
│       ├── service_providers.py
│       ├── m365.py             # M365 credentials
│       └── actions.py          # Action tracking
├── providers/                  # AI provider integrations
│   ├── base.py                 # Abstract interface
│   ├── mock.py                 # Testing provider
│   ├── openai.py               # OpenAI integration
│   └── anthropic.py            # Anthropic (streaming)
└── actions/                    # Action providers
    ├── base.py                 # Abstract interface
    ├── action_registry.py      # Lifecycle management
    └── m365_provider.py        # Microsoft 365 Graph API
```

### Key Components

#### 1. Router (`core/router.py`)

The router is the brain of THEO, handling:

**Intent Classification:**
```python
def classify_intent(text, intents, debug=False):
    # Context-aware keyword matching
    # Priority-based tie-breaking
    # Fallback intent handling
    return classified_intent
```

**Provider Selection Logic:**
1. Check for forced provider (user override)
2. Apply user routing rules (intent → provider)
3. Use intent default provider
4. Health-based fallback (circuit breaker)

#### 2. Memory Store (`core/memory/`)

Modular memory architecture with 9 specialized modules:

- **memories.py**: CRUD operations for facts, preferences, goals
- **intents.py**: Intent and routing preference management
- **sessions.py**: Chat session and turn tracking
- **providers.py**: AI provider configuration and health
- **users.py**: User accounts and authentication
- **modes.py**: Work/Personal mode settings
- **service_providers.py**: External service integrations
- **m365.py**: Microsoft 365 credential management
- **actions.py**: Action and confirmation tracking

**Benefits:**
- Each module is independently testable
- Clear separation of concerns
- Easy to extend with new features
- Maintains backwards compatibility via inheritance

#### 3. Action System

Two-step confirmation workflow:

```
User Request → Intent Detection → Action Creation → Approval Request
                                                            ↓
                                                    User Approves/Rejects
                                                            ↓
                                                    Execute or Cancel
```

**Action Handlers:**
- Calendar: Create, update, delete events
- Email: Read, compose, reply, send
- Confirmations: Approve, reject, expire

#### 4. Provider Health Monitoring

Circuit breaker pattern for reliability:

```python
States:
  CLOSED → Normal operation
  OPEN → Too many failures, circuit broken
  HALF_OPEN → Testing if provider recovered

Metrics Tracked:
  - Success rate
  - Average latency
  - Total requests
  - Cost estimation
```

---

## 🎨 Frontend Architecture

### Component Structure

```
frontend/src/
├── App.svelte                  # Main router & state
├── components/
│   ├── Chat.svelte             # Chat interface
│   ├── Login.svelte            # Authentication UI
│   ├── MessageList.svelte      # Message rendering
│   ├── Sidebar.svelte          # Session list
│   └── settings/               # 10 modular components
│       ├── SettingsContainer.svelte
│       ├── GeneralSettings.svelte
│       ├── IntentsSettings.svelte
│       ├── RoutingSettings.svelte
│       ├── MemorySettings.svelte
│       ├── AIProvidersSettings.svelte
│       ├── WorkModeSettings.svelte
│       ├── PersonalModeSettings.svelte
│       ├── AccountSettings.svelte
│       └── HealthMonitorSettings.svelte
├── lib/
│   └── api.js                  # REST client (50+ endpoints)
└── styles/
    ├── global.css
    ├── variables.css
    ├── components/             # Component-specific styles
    └── utilities.css
```

### State Management

THEO uses Svelte's reactive stores for state management:

```javascript
// Global state
let currentUser = null
let currentSession = null
let currentMode = 'personal'

// Reactive updates
$: sessionMessages = loadMessages(currentSession)
$: providers = loadProviders()
```

### Real-time Streaming

Server-Sent Events (SSE) for streaming responses:

```javascript
const eventSource = new EventSource(
  `/api/stream/${sessionId}?text=${text}&work_subtab=${subtab}`
)

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  if (data.token) {
    appendToken(data.token)
  }
}
```

---

## 🗄️ Database Schema

### Tables Overview

**Authentication & Users:**
- `users` - User accounts (id, username, password_hash, is_admin)
- `auth_sessions` - Session tokens (token, user_id, expires_at)

**Configuration:**
- `system_prompt_config` - Global system prompt settings
- `user_mode_config` - Current mode per user
- `mode_settings` - Mode-specific configurations
- `work_mode_subtab_config` - Work subtab settings

**Intents & Routing:**
- `intents` - User-defined intents (name, keywords, priority)
- `routing_preferences` - Intent → Provider mappings

**Memory:**
- `memories` - Structured memory (type, key, value, score, pinned)
- `preferences` - Legacy key-value store

**Conversations:**
- `sessions` - Chat sessions (id, user_id, title, mode)
- `turns` - Messages (session_id, role, content, provider, model)
- `summaries` - Rolling summaries (session_id, summary)
- `session_providers` - Last provider used per session

**Providers:**
- `providers` - LLM configs (type, model, api_key, enabled)
- `provider_metadata` - Health metrics (success_rate, latency, cost)
- `request_logs` - Request history (provider, success, latency)

**Actions & Integrations:**
- `service_providers` - External services (category, config)
- `m365_credentials` - OAuth tokens (access_token, refresh_token)
- `actions` - Action history (type, status, parameters, result)
- `confirmations` - Pending approvals (action_id, status, expires_at)

---

## 🔄 Request Flow

### Chat Message Flow

```
1. User types message in Chat.svelte
   ↓
2. Frontend calls GET /api/stream/{session_id}?text=...
   ↓
3. Backend router.py:
   a. Check for pending confirmations
   b. Classify intent from text
   c. Check if action intent (calendar/email)
   d. Select provider (forced/rules/default/health-based)
   ↓
4a. If Action Intent:
    → action_router.py handles
    → Creates confirmation request
    → Returns approval widget
    ↓
4b. If Standard Intent:
    → Build context (system prompt + memory + history)
    → Call selected provider
    → Stream tokens via SSE
    ↓
5. Frontend receives tokens and displays in real-time
   ↓
6. On completion:
   a. Save message to database
   b. Update session metadata
   c. Generate session title (if first message)
```

### Action Execution Flow

```
1. User approves action via Confirmation Widget
   ↓
2. Frontend calls POST /api/confirmations/{id}/approve
   ↓
3. Backend confirmation_manager.py:
   a. Validate confirmation exists
   b. Check not expired
   c. Mark as approved
   d. Retrieve associated action
   ↓
4. action_router.py executes action:
   a. Load action parameters
   b. Call appropriate handler (calendar/email)
   c. Execute external API call (M365 Graph)
   d. Update action status
   e. Return result
   ↓
5. Frontend displays success/failure message
```

---

## 🔐 Security Architecture

### Authentication Flow

```
1. User submits username/password
   ↓
2. Backend validates against users table:
   - Hash password with stored salt
   - Compare with stored hash (SHA-256)
   ↓
3. If valid:
   a. Generate 32-byte random session token
   b. Store in auth_sessions with 7-day expiration
   c. Return token to frontend
   ↓
4. Frontend stores token in localStorage
   ↓
5. All subsequent requests include:
   Authorization: Bearer {token}
```

### Security Layers

1. **Password Hashing**: SHA-256 with 16-byte random salt
2. **Session Tokens**: Cryptographically random, 7-day expiration
3. **CORS Protection**: Configured for specific origins
4. **Input Validation**: All user inputs sanitized
5. **SQL Injection Protection**: SQLAlchemy ORM with parameterized queries

**Note**: For production, consider upgrading to bcrypt/argon2 and adding rate limiting.

---

## 📡 API Design

### RESTful Principles

- **Resource-based URLs**: `/api/sessions/{id}`
- **HTTP Methods**: GET (read), POST (create), PUT (update), DELETE (remove)
- **JSON Payloads**: All requests/responses use JSON
- **Authentication**: Bearer token in Authorization header
- **Error Handling**: Consistent error format with status codes

### Streaming Endpoints

SSE (Server-Sent Events) for real-time streaming:

```
GET /api/stream/{session_id}?text=...&work_subtab=...

Response:
  data: {"token": "Hello"}
  data: {"token": " world"}
  data: {"done": true, "provider": "openai", "model": "gpt-4"}
```

---

## 🚀 Deployment Architecture

### Local Development

```
┌─────────────┐      ┌──────────────┐
│   Frontend  │      │   Backend    │
│   (Vite)    │ ───► │   (Flask)    │
│  Port 5174  │      │  Port 1066   │
└─────────────┘      └──────────────┘
                            │
                            ↓
                     ┌──────────────┐
                     │   SQLite     │
                     │  theo.db     │
                     └──────────────┘
```

### Docker Deployment

```
┌─────────────────────────────────────┐
│         Docker Compose              │
├─────────────────────────────────────┤
│  ┌────────────┐   ┌──────────────┐ │
│  │  Frontend  │   │   Backend    │ │
│  │   (Nginx)  │   │   (Flask)    │ │
│  │  Port 8080 │   │  Port 1066   │ │
│  └────────────┘   └──────────────┘ │
│         │                 │         │
│         └────────┬────────┘         │
│                  ↓                  │
│         ┌──────────────┐            │
│         │   Volume     │            │
│         │  /data       │            │
│         └──────────────┘            │
└─────────────────────────────────────┘
```

### AWS ECS Deployment

```
┌────────────────────────────────────────────┐
│          CloudFront CDN                    │
└────────────────┬───────────────────────────┘
                 ↓
┌────────────────────────────────────────────┐
│          Application Load Balancer          │
└────────────────┬───────────────────────────┘
                 ↓
┌────────────────────────────────────────────┐
│            ECS Cluster                      │
├────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐     │
│  │  Frontend    │    │   Backend    │     │
│  │  Task        │    │   Task       │     │
│  └──────────────┘    └──────┬───────┘     │
└───────────────────────────────┼────────────┘
                                ↓
                    ┌───────────────────────┐
                    │   S3 Bucket           │
                    │   (Database Backups)  │
                    │   - Auto backup every │
                    │     5 minutes         │
                    └───────────────────────┘
```

---

## 🎯 Design Decisions

### Why Flask?

- Lightweight and flexible
- Excellent for RESTful APIs
- Large ecosystem of extensions
- Easy to deploy

### Why Svelte?

- Reactive by default
- Minimal boilerplate
- Excellent performance
- Small bundle size

### Why SQLite?

- Zero configuration
- Single file database
- Perfect for self-hosted
- S3 backup support for production

### Why Modular Architecture?

- **Maintainability**: Each module has single responsibility
- **Testability**: Modules can be tested independently
- **Scalability**: Easy to add new features
- **Team Collaboration**: Clear ownership boundaries

---

## 📚 Further Reading

- [[API Reference]] - Complete API documentation
- [[Database Schema]] - Detailed schema documentation
- [[Testing Architecture]] - Test structure and coverage
- [[Deployment Guide]] - Production deployment details

---

**Last Updated**: December 28, 2025
