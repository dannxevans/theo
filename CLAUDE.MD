# CLAUDE.MD - AI Assistant Guide for THEO

This document provides context for AI assistants (like Claude) working on the THEO codebase.

## Project Overview

THEO is a self-hosted personal AI assistant that intelligently routes requests to the most appropriate AI model based on intent, while maintaining conversation continuity and context across models.

**Philosophy**: Not "one model to rule them all" - use different models for different tasks while preserving seamless user experience.

## Tech Stack

- **Backend**: Python 3.9+ with Flask
- **Frontend**: Svelte 4 with Vite 5
- **Database**: SQLite with SQLAlchemy ORM
- **Real-time Communication**: Socket.IO with Flask-SocketIO
- **Authentication**: Session tokens + API keys (bcrypt hashing)
- **Testing**: pytest (backend), coverage tracking
- **Deployment**: Docker, AWS ECS (historical)

## Project Structure

```
theo/
├── dev-docs/                       # Implementation plans for active development
├── backend/
│   ├── app.py                      # Main Flask application entry point
│   ├── config.py                   # Configuration management
│   ├── requirements.txt            # Python dependencies
│   │
│   ├── routes/                     # 16+ modular Flask blueprints
│   │   ├── auth_routes.py          # Authentication endpoints
│   │   ├── chat_routes.py          # Chat/conversation endpoints
│   │   ├── memory_routes.py        # Memory management endpoints
│   │   ├── provider_routes.py      # AI provider configuration
│   │   ├── intent_routes.py        # Intent management
│   │   ├── voice_routes.py         # TTS/STT endpoints
│   │   └── ...                     # Additional route modules
│   │
│   ├── core/                       # Core business logic
│   │   ├── intent_classifier.py    # Intent detection & classification
│   │   ├── intent_reasoning.py     # AI-powered intent reasoning (#363)
│   │   ├── action_router.py        # Routes actions to providers
│   │   ├── context.py              # Context building & management
│   │   ├── confirmation_manager.py # Two-step action confirmations
│   │   ├── logging_handler.py      # Structured logging
│   │   ├── pii_filter.py           # PII detection & filtering
│   │   ├── classification_audit.py # Intent classification auditing
│   │   ├── here_service.py         # HERE Maps integration
│   │   ├── traffic_service.py      # Traffic/routing with smart location inference
│   │   │
│   │   ├── orchestration/          # Multi-service orchestration (#371, #374)
│   │   │   └── orchestrator.py     # LLM-first orchestration engine
│   │   │
│   │   ├── actions/                # Action handlers
│   │   │   ├── action_handler.py
│   │   │   ├── calendar_handler.py
│   │   │   ├── email_handler.py
│   │   │   ├── planning_handler.py
│   │   │   └── web_fetch_handler.py
│   │   │
│   │   └── memory/                 # Memory system (12 modules)
│   │       ├── memory_manager.py   # Main memory coordinator
│   │       ├── chunking.py         # Text chunking strategies
│   │       ├── compression.py      # Memory compression
│   │       ├── deduplication.py    # Duplicate detection
│   │       ├── embedding.py        # Vector embeddings
│   │       ├── lifecycle.py        # Memory lifecycle management
│   │       ├── pinning.py          # Pin important memories
│   │       ├── ranking.py          # Relevance scoring
│   │       ├── retrieval.py        # Context retrieval
│   │       ├── storage.py          # Database operations
│   │       ├── summarization.py    # Memory summarization
│   │       └── validation.py       # Input validation
│   │
│   ├── providers/                  # AI provider integrations
│   │   ├── base_provider.py        # Abstract base class
│   │   ├── openai_provider.py      # OpenAI GPT integration
│   │   ├── anthropic_provider.py   # Anthropic Claude integration
│   │   ├── mock_provider.py        # Testing mock provider
│   │   ├── health_monitor.py       # Provider health checks
│   │   └── circuit_breaker.py      # Failure recovery
│   │
│   ├── actions/                    # External action providers
│   │   ├── m365_provider.py        # Microsoft 365 (Calendar, Email)
│   │   ├── weather_provider.py     # Weather data
│   │   └── service_booking.py      # Service provider booking
│   │
│   ├── auth/                       # Authentication system
│   │   ├── auth_manager.py         # Auth logic
│   │   ├── session_manager.py      # Session handling
│   │   └── api_key_manager.py      # API key management
│   │
│   ├── migrations/                 # Database migration scripts
│   ├── scripts/                    # Utility scripts
│   └── tests/                      # 779 backend tests (100% passing)
│       ├── memory/                 # Memory system tests
│       ├── core/                   # Core logic tests
│       └── routes/                 # API endpoint tests
│
└── frontend/
    ├── package.json                # Node dependencies
    ├── vite.config.js              # Vite configuration
    ├── index.html                  # Entry HTML
    │
    ├── src/
    │   ├── App.svelte              # Main application component
    │   ├── main.js                 # Application entry point
    │   │
    │   ├── components/
    │   │   ├── Chat.svelte         # Main chat interface
    │   │   ├── Login.svelte        # Login form
    │   │   ├── VoiceControls.svelte # Voice UI controls
    │   │   │
    │   │   └── settings/           # 11+ modular settings components
    │   │       ├── GeneralSettings.svelte
    │   │       ├── ProvidersTab.svelte
    │   │       ├── IntentsTab.svelte
    │   │       ├── RoutingTab.svelte
    │   │       ├── MemoryTab.svelte
    │   │       ├── VoiceTab.svelte
    │   │       ├── ActionsTab.svelte
    │   │       ├── ConfirmationCard.svelte  # Action confirmation UI (Phase 4)
    │   │       └── ...
    │   │
    │   ├── lib/
    │   │   └── api.js              # REST API client
    │   │
    │   └── styles/
    │       ├── global.css          # Global styles
    │       └── theme.css           # Theme variables
    │
    └── tests/                      # Frontend tests
```

## Key Architecture Concepts

### 1. Intent-Based Routing

THEO uses a two-layer intent detection system:

1. **Keyword Matching** (core/intent_classifier.py): Fast, rule-based classification using user-defined intents with keywords and priorities
2. **AI Reasoning Layer** (core/intent_reasoning.py): LLM-powered analysis for complex or ambiguous requests (#363)

Intents are configured in the UI (Settings → Intents) and mapped to specific AI providers via routing rules.

### 2. Multi-Model Provider System

- **Abstract Base Class** (providers/base_provider.py): Defines provider interface
- **Concrete Providers**: OpenAI, Anthropic, Google, Perplexity, Mock
- **Health Monitoring** (providers/health_monitor.py): Tracks provider availability
- **Circuit Breaker** (providers/circuit_breaker.py): Automatic failover on provider failures (opens after 5 consecutive failures, 60-minute cooldown)
- **Provider Routing**: Checks primary provider health → fallback if unhealthy → auto-select if both fail

### 3. Memory System

Sophisticated memory management with 12 specialized modules:

- **Storage**: SQLite-backed persistent memory
- **Embedding**: Vector similarity for semantic search
- **Ranking**: Relevance scoring based on recency, frequency, semantic similarity
- **Chunking**: Intelligent text segmentation
- **Compression**: Summarization for long-term storage
- **Pinning**: User-marked important memories
- **Deduplication**: Prevents duplicate memories
- **Lifecycle**: Automatic memory aging and archival

### 4. Intelligent Multi-Service Orchestration (#371, #374)

**Status**: ✅ Production Ready (Phases 1-4 Complete, January 2026)

LLM-first orchestration engine that coordinates multiple services to answer complex, multi-faceted queries. Instead of requiring users to manually query each service, THEO intelligently orchestrates calendar, weather, traffic, and other services to provide contextual responses.

**Four-Phase Flow:**

1. **Phase 1: Intent Reasoning & Decision** (core/intent_reasoning.py)
   - LLM analyzes query and extracts entities (locations, times, people, activities)
   - Identifies service signals with confidence scores
   - Decides if orchestration is needed: `orchestrate: true/false`

2. **Phase 2: Service Planning & Context Gathering** (core/orchestration/orchestrator.py)
   - LLM creates service query plan
   - Executes queries in parallel (calendar, weather, traffic, etc.)
   - Smart location inference (routes from work during work hours)
   - Person address validation with multi-turn clarification

3. **Phase 3: Response Synthesis & Action Planning**
   - LLM transforms raw service data into natural language
   - Proposes actions (calendar events, tasks) based on context
   - Generates confirmation messages for user approval

4. **Phase 4: User Confirmation & Execution**
   - Frontend displays interactive confirmation card (ConfirmationCard.svelte)
   - User approves/rejects within 5 minutes
   - Action router executes approved actions (M365, tasks, etc.)
   - Results integrated back into conversation

**Example Query:**
```
"Buy groceries at Asda tomorrow"
→ Orchestrate: calendar (availability) + traffic (route to store)
→ Synthesize: "You're free after 5:30pm. Asda is 15 min from work."
→ Propose: Create event "Buy groceries at Asda" at 5:45pm
→ User approves → Event created
```

**Key Features:**
- Multi-turn clarification (e.g., "What is mum's address?" → stores fact → resumes)
- Smart location inference from calendar context
- Geographic bias (UK-focused geocoding via HERE Maps)
- Parallel service execution for performance (~7-11 seconds total)
- Token-efficient (~1,200 tokens per orchestration)

**Control:**
- UI toggle: Settings → Health Monitor → Advanced → "Disable Agentic AI"
- Database: `preferences.disable_agentic_mode`

### 5. Action System

Two-step confirmation workflow for external actions:

1. **Action Detection**: LLM identifies actionable requests (or orchestrator proposes actions)
2. **User Confirmation**: UI prompt for approval (core/confirmation_manager.py)
3. **Execution**: Action router dispatches to appropriate provider
4. **Result Handling**: Response integrated back into conversation

Supported actions:
- Microsoft 365 Calendar (create/update events)
- Microsoft 365 Email (send emails)
- Tasks (create/complete)
- Weather queries
- Traffic/routing (HERE Maps)
- Planning (weather + traffic + calendar context)
- Web fetching with SSRF protection (#361)
- WHOOP fitness data (sleep, recovery, workouts)
- Plex media library (search, history, playback)
- Perplexity search with citations

### 6. Work/Personal Modes

Dual-mode system with mode-specific configurations:
- Separate system prompts
- Different intents and routing rules
- Mode-specific context building
- **Note**: Personal actions (calendar, email, tasks) blocked in Work mode

### 7. Voice Features

- **TTS**: OpenAI text-to-speech with streaming (reduced latency from 25+ seconds to 2-3 seconds)
- **STT**: OpenAI speech-to-text (Whisper)
- **Auto-read Mode**: Automatic TTS for responses
- Voice controls in UI (VoiceControls.svelte)

### 8. Authentication

Three authentication methods:
- **Session Tokens**: Web UI login
- **API Keys**: Automation (Siri Shortcuts, etc.) - format: `theo_<64_hex_chars>`
- **OAuth 2.0**: Microsoft 365 integration with automatic token refresh

Default credentials (change immediately!):
- Username: `admin`
- Password: `admin`

## Database Schema

SQLite database with SQLAlchemy ORM. Key tables:

- `User`: User accounts
- `Session`: Active sessions
- `APIKey`: API keys for automation
- `Conversation`: Chat sessions
- `Message`: Individual messages
- `Memory`: Stored memories with embeddings
- `Provider`: AI provider configurations
- `Intent`: User-defined intents
- `routing_preferences`: Intent → Provider mappings with fallback options
- `provider_metadata`: Health tracking, circuit breaker state
- `M365Token`: OAuth tokens
- `ConfirmationRequest`: Pending action confirmations
- `ClassificationAudit`: Intent classification history
- `web_fetch_cache`: Cached web content with 1-hour TTL

## Recent Major Features (January 2026)

### #371 & #374 - Intelligent Multi-Service Orchestration (Phases 1-4)
**Status**: ✅ Production Ready

Complete LLM-first orchestration system that coordinates multiple services (calendar, weather, traffic) to answer complex queries. Key achievements:
- **Phase 1**: Intent Reasoning determines orchestration need with entity extraction and service signals
- **Phase 2**: LLM-planned parallel service queries with smart location inference
- **Phase 3**: Natural language synthesis with action proposals
- **Phase 4**: Two-step confirmation UI with 5-minute expiry and action execution

Example: "Buy groceries at Asda tomorrow" → checks calendar → calculates route → proposes calendar event → user approves → event created.

Features: Multi-turn clarification for missing info (person addresses), smart work location inference, UK geographic bias, graceful degradation on service failures.

### #367 - Intent and Behaviour Fix
Latest improvements to intent classification and behaviour routing. Fixed Work mode bug where text rewriting requests were incorrectly classified as email composition actions.

### #363 - AI-Powered Intent Reasoning Layer
Added LLM-powered intent reasoning for complex queries that don't match keyword patterns. Analyzes messages with conversation context, extracting rich entities and service signals. Now integrated with orchestration system (Phase 1).

### #361 - Web Reading and Link Fetching
Added secure web content fetching with SSRF protection and intelligent caching (1-hour TTL).

### #290 - Database Audit Interface
Admin interface to inspect all sessions and conversation turns with filtering and pagination.

### #239 - API Key Authentication
Secure API keys for Siri Shortcuts and automation workflows.

### Perplexity Search Integration
Real-time web search with inline citations, UK regional bias, and collapsible sources.

### Streaming TTS
Reduced audio latency from 25+ seconds to 2-3 seconds using streaming endpoints.

### WHOOP Integration
Fitness tracker queries (sleep, recovery, workouts) with proactive notifications.

### Context-Aware Planning
Calendar enrichment with weather and traffic data via LLM summarization.

### Plex Integration
Natural language queries for library, viewing history, and playback control.

### User Management
Multi-user support with role-based access control.

## Testing

### Backend Tests: 779/779 passing (100%)

Run tests:
```bash
cd backend
pip install -e .
pytest                              # Run all tests
pytest tests/memory                 # Memory system tests
pytest tests/core                   # Core logic tests
pytest tests/routes                 # API endpoint tests
pytest --cov=. --cov-report=html    # With coverage report
```

Test structure:
- `tests/memory/`: Memory system unit tests
- `tests/core/`: Core business logic tests
- `tests/routes/`: API endpoint integration tests
- `conftest.py`: Shared fixtures and test utilities

### Coverage
- Overall Backend: 51%
- Core Modules: Higher coverage (~60-80%)

**Note**: Frontend tests were removed as of 2026-01-01. Future frontend testing will use a different approach.

## Development Workflow

### Standard Development Process

1. **Plan changes** - Identify affected files and components
   - Store implementation plans in `/dev-docs/` directory
   - Present plan to user for approval before implementation
2. **Update database schema** - If needed, create migration in `run_migrations.py` and `db_backup.py`
3. **Add/update backend operations** - Implement business logic
4. **Create/update API endpoints** - Add or modify routes
5. **Update frontend components** - Modify UI as needed
6. **Write tests** - Ensure coverage for new functionality
   - **CRITICAL**: All tests must pass at 100% before completion
7. **Verify** - User commits from VS Code (AI assistants do NOT commit to GitHub)

### Local Development

1. **Backend**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python app.py
   ```
   Runs at `http://localhost:1066`

2. **Frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Runs at `http://localhost:5174`

### Git Workflow

This is a git worktree for branch `frosty-edison`:
- Main repository: `/Users/dannyblack/Development/theo`
- Worktree path: `/Users/dannyblack/.claude-worktrees/theo/frosty-edison`
- Main branch: `main`
- Current status: Clean working tree

See `.github/BRANCHING.md` for git workflow details.

## Configuration Files

- `backend/config.py`: Environment-based configuration
- `backend/.env`: Environment variables (not in repo)
- `frontend/vite.config.js`: Vite build configuration
- `.github/workflows/`: CI/CD pipeline definitions

## Important Design Patterns

### 1. Blueprint Pattern (Flask Routes)
All routes are modular Flask blueprints for better organization and testing.

### 2. Provider Pattern
Abstract base class with concrete implementations for each AI provider.

### 3. Strategy Pattern (Memory)
Different strategies for chunking, ranking, compression, etc.

### 4. Circuit Breaker Pattern
Automatic failover when providers become unhealthy. Opens after 5 consecutive failures with configurable cooldown (default: 60 minutes). Automatically retries in half-open state.

### 5. Two-Step Confirmation
All external actions require explicit user approval before execution.

### 6. Memory Delegation Pattern
The MemoryStore delegates operations to specialized modules (IntentOperations, ProviderOperations, SessionOperations, MemoryOperations).

## Common Development Tasks

### Adding a New AI Provider

1. Create provider class in `backend/providers/` extending `base_provider.py`
2. Implement required methods: `generate_response()`, `stream_response()`
3. Add provider type to UI in `frontend/src/components/settings/ProvidersTab.svelte`
4. Test with mock responses first

### Adding a New Intent

1. UI: Settings → Intents → Create Intent
2. Define keywords, priority (0-100)
3. Create routing rule: Intent → Provider

### Adding a New Action Type

1. Create handler in `backend/core/actions/`
2. Extend action router in `core/action_router.py`
3. Add UI component in `frontend/src/components/settings/ActionsTab.svelte`
4. Implement confirmation flow

### Adding a New Route

1. Create blueprint in `backend/routes/`
2. Register in `app.py`
3. Add tests in `backend/tests/routes/`

## Security Considerations

- **PII Filtering**: `core/pii_filter.py` detects and filters sensitive data
- **Password Hashing**: bcrypt for all passwords
- **API Key Format**: `theo_<64_hex_chars>` for easy identification and security
- **Session Management**: Secure session tokens with expiration
- **OAuth 2.0**: Microsoft 365 with automatic token refresh
- **Classification**: Designed for UK Government OFFICIAL classification

## Performance Optimizations

- **Streaming Responses**: SSE for real-time token streaming
- **Memory Chunking**: Efficient text segmentation for retrieval
- **Database Indexing**: Optimized queries on frequently accessed tables
- **Provider Caching**: Circuit breaker reduces redundant health checks
- **Connection Pooling**: SQLAlchemy connection pool

## Common Gotchas & Best Practices

### Project Workflow Requirements

1. **Planning**: Always create implementation plans in `/dev-docs/` directory and get user approval before starting work

2. **Testing**: All tests MUST pass at 100% before marking work as complete

3. **Git Commits**: DO NOT commit to GitHub - the user will commit manually from VS Code

4. **Documentation Sources**: Always read the [Claude Developer Onboarding Wiki](https://github.com/dannxevans/theo/wiki/Claude-Developer-Onboarding) at the start of new sessions

### Critical Implementation Details

1. **User ID Normalization**: Always use `normalize_user_id()` utility for backwards compatibility when handling user IDs (handles legacy "local" strings → integers)

2. **Provider Class Names**: Check actual provider files for correct class names (e.g., `GoogleProvider`, not `GeminiProvider`)

3. **API Patterns**: Use `provider.chat()` method, NOT `.generate()` when making LLM requests

4. **Route All LLM Calls**: Use `route_request()` for all LLM calls to respect routing preferences

5. **Database Migrations**: Only add ALTER TABLE migrations to `run_migrations.py`; SQLAlchemy handles initial table creation

6. **Frontend Display**: Backend metadata fields take precedence over pattern matching

7. **Return Complex Data**: Return tuples for complex data requiring metadata, not just single values

8. **Variable Initialization**: Always initialize variables before conditional blocks to avoid reference errors

9. **AI Attribution**: Only show AI attribution when AI was actually used in the response

10. **Planning Intent Patterns**: Test thoroughly to prevent false positives in intent detection

11. **Test Mocking**: Mock at appropriate levels in tests (don't over-mock or under-mock)

12. **Investigate First**: Always investigate existing code before assuming features don't exist

### Provider Routing Flow

```
Check primary provider health → fallback if unhealthy → auto-select if both fail
```

## Known Limitations

- SQLite for simplicity (PostgreSQL recommended for high-load deployments)
- Memory embeddings computed on-demand (no background workers yet)
- Multi-user support recently added but still evolving

## Useful Commands

```bash
# Backend
pytest tests/                       # Run all tests
pytest --cov=. --cov-report=html   # Coverage report
python cleanup_test_users.py       # Clean test data

# Frontend
npm run dev                         # Development server
npm run build                       # Production build
npm run preview                     # Preview production build

# Docker
docker-compose up -d               # Start containers
docker-compose logs -f backend     # View backend logs
```

## Documentation References

- **CLAUDE.MD** (this file): AI assistant onboarding and codebase reference
- **[Claude Developer Onboarding Wiki](https://github.com/dannxevans/theo/wiki/Claude-Developer-Onboarding)**: Canonical source for AI assistant guidelines
- **README.md**: Main project documentation
- **[GitHub Wiki](https://github.com/dannxevans/theo/wiki)**: Comprehensive guides
  - Architecture Overview
  - API Reference
  - Configuration Guide
  - Testing Guide
  - Test Results
- **docs/**: Technical documentation (authentication, M365, deployment, etc.)
- **DOCS/**: User-facing documentation (voice features, etc.)
- **.github/**: CI/CD, branching strategy, quick start

## Environment Variables

```bash
# Required
ENV=prod|dev                        # Environment mode

# Optional (if not set, uses defaults)
DATABASE_URL=sqlite:///data/theo.db # Database connection
```

## Recent Changes (Latest Commits)

1. **caf4e9b**: Intent reasoning fix for work mode
2. **32bfbd0**: #374: Phase 4 - Action Confirmation & Execution for Orchestration
3. **49d4ce2**: Stage: #371 Intelligent Multi-Service Orchestration
4. **cf5d597**: Intent and Behaviour Fix (#367)
5. **f3372f2**: AI-Powered Intent Reasoning Layer (#365)

---

**Last Updated**: January 13, 2026
**Current Branch**: awesome-satoshi
**Main Repository**: /Users/dannyblack/Development/theo
