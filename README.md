# THEO – Personal Multi-Model AI Assistant

THEO is a self-hosted AI assistant that intelligently routes user requests to the most appropriate AI model based on intent, while maintaining conversation continuity and user context across models.

The philosophy is not "one model to rule them all", but rather:
- **Use different models for different tasks** - Leverage each model's strengths
- **Preserve user context when models change** - Seamless experience across providers
- **Remain fully under user control** - Self-hosted, transparent routing decisions

---

## 📚 Documentation

- **[Implementation Plan](docs/IMPLEMENTATION_PLAN.md)** - Development roadmap and feature tracking
- **[Authentication Guide](docs/AUTHENTICATION.md)** - Login, password management, and security
- **[Database Persistence Guide](docs/DATABASE_PERSISTENCE.md)** - S3 backup/restore for AWS deployments
- **[ECS Setup Guide](docs/ECS_DATABASE_SETUP.md)** - AWS ECS configuration and deployment
- **[M365 Integration Guide](docs/M365_INTEGRATION.md)** - Microsoft 365 setup and features

---

## ✨ Current Features

### Core Functionality
- **Multi-Model Routing**: Intelligent routing based on user-defined intents with keyword matching
- **Streaming Responses**: Real-time token streaming via Server-Sent Events (SSE)
- **Session Management**: Multi-turn conversations with persistent context and summaries
- **Memory System**: Structured memory (facts, preferences, goals) with relevance scoring and pinning
- **Authentication**: Secure session-based login with password management (7-day sessions)
- **Work/Personal Modes**: Dual-mode system with mode-specific configurations
- **Provider Health Monitoring**: Circuit breaker pattern, failure tracking, and automatic fallback
- **Action Execution**: Two-step confirmation workflow for external actions with UI approval widgets

### Microsoft 365 Integration
THEO includes comprehensive M365 integration via Microsoft Graph API:

**Calendar Management**
- **Read Events**: Fetch calendar events within date ranges
- **Create Events**: Book meetings with attendees, location, and descriptions
- **Update Events**: Modify existing calendar entries
- **Delete Events**: Remove calendar events
- **Smart Detection**: Flight/travel detection in calendar queries
- **Context-Aware Booking**: Generic verbs require calendar context (prevents false positives)

**Email Management**
- **Read Emails**: Access inbox with search and filtering
- **Smart Composition**: LLM-generated subjects and content from natural language
- **Draft Workflow**: Create → Review → Approve/Reject → Send/Delete
- **Reply to Emails**: Context-aware replies with original message threading
- **Signature Handling**: Intelligent signature stripping with comprehensive pattern matching
- **HTML Processing**: Clean conversion to readable plain text
- **Sent Items**: Automatic saving to Sent Items folder

**OAuth 2.0 Authentication**
- Automatic token refresh handling
- Secure credential storage in database
- Token expiration management

### Work Mode Features
When in work mode, THEO provides specialized subtabs:
- **Conversation**: General professional discussion context
- **Email Rewrites**: Configure tone and signature for email assistance
- **Code Development**: Set programming language, framework, and expertise context
  - Supports: ServiceNow JavaScript, JavaScript, TypeScript, Python, Java, C#

### Provider Support
- **Anthropic (Claude)**: Full streaming support
- **OpenAI (GPT)**: ChatGPT and GPT-4 models with LLM-powered email generation
- **Microsoft 365**: Calendar and email operations via Graph API
- **Mock Provider**: Deterministic testing provider
- **Extensible Architecture**: Plugin-style action providers, easy to add new integrations

### User Interface
- **Chat Interface**: ChatGPT-style UI with markdown rendering and syntax highlighting
- **Settings Panel**: Comprehensive configuration for:
  - System prompts and persona customization
  - Provider management (add/edit/delete)
  - Intent definitions and routing rules
  - Memory browser and management
  - Work/Personal mode settings
  - Account and debug options
- **Mobile-Responsive**: Touch-optimized interface
- **Session Management**: Export conversations (JSON/Markdown), fork sessions, auto-generated titles

### Deployment Ready
- **Docker Compose**: Single-command local deployment
- **AWS ECS**: Production-ready task definitions
- **S3 Database Backup**: Automatic backup/restore every 5 minutes
- **CloudFront Integration**: ALB and proxy-aware middleware

---

## 🏗️ Architecture

### Backend (Python/Flask)
```
backend/
├── app.py                    # Flask server (port 1066) with 70+ REST endpoints
├── auth.py                   # Authentication with SHA-256 hashing
├── db_backup.py              # S3 backup/restore manager
├── core/
│   ├── router.py             # Intent classification & provider selection
│   ├── action_router.py      # Action execution & email/calendar handling
│   ├── context.py            # Context building & system prompt injection
│   ├── memory.py             # SQLAlchemy ORM with 17+ database tables
│   ├── confirmation_manager.py # Two-step approval workflow
│   └── provider_registry.py # Runtime provider registry
├── providers/
│   ├── base.py               # Abstract provider interface
│   ├── mock.py               # Testing provider
│   ├── openai.py             # OpenAI integration
│   └── anthropic.py          # Anthropic integration (streaming SSE)
└── actions/
    ├── base.py               # Abstract action provider interface
    ├── action_registry.py    # Action provider lifecycle management
    └── m365_provider.py      # Microsoft 365 Graph API integration
```

**Routing Logic**:
1. Confirmation check (pending approvals)
2. Intent classification via context-aware keyword matching
3. Action routing (calendar/email operations)
4. Provider selection with fallback chain:
   - Forced provider (user override)
   - User routing rules (intent → provider mapping)
   - Intent-based defaults
   - Health-based fallback (circuit breaker)

### Frontend (Svelte)
```
frontend/
├── src/
│   ├── App.svelte           # Main router & session management
│   ├── components/
│   │   ├── Chat.svelte      # Message streaming & work mode subtabs
│   │   ├── Login.svelte     # Authentication UI
│   │   ├── Settings.svelte  # Multi-tab configuration
│   │   ├── MessageList.svelte  # Markdown rendering
│   │   └── Memory.svelte    # Memory browser
│   └── lib/
│       └── api.js           # REST client (50+ endpoints)
└── public/
    └── style.css            # Global styles
```

### Database Schema (SQLite + S3)

**Authentication**:
- `users` - User accounts with password hashes
- `auth_sessions` - Session tokens (7-day expiration)

**Configuration**:
- `system_prompt_config` - Persona, tone, style rules
- `user_mode_config` - Active mode per user (work/personal)
- `mode_settings` - Mode-specific system prompts and provider preferences
- `work_mode_subtab_config` - Subtab configurations (code language, email tone)

**Intent & Routing**:
- `intents` - User-defined intents with keywords and priorities
- `routing_preferences` - Intent → Provider mappings

**Memory**:
- `memories` - Structured memory with types (fact/preference/goal/context)
- `preferences` - Legacy key-value store

**Conversation**:
- `sessions` - Chat sessions with titles
- `turns` - Individual messages with provider/model metadata
- `summaries` - Rolling session summaries
- `session_providers` - Last used provider per session

**Provider Management**:
- `providers` - LLM provider configurations
- `provider_metadata` - Health status, costs, latency, circuit breaker state
- `request_logs` - Request history with success/failure tracking

**Action Execution & M365**:
- `service_providers` - External service provider configurations (M365, etc.)
- `m365_credentials` - OAuth tokens with automatic refresh
- `actions` - Action execution history with status tracking
- `confirmations` - Pending approval requests with expiration

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+
- Optional: AWS account for S3 backups (production)

### Local Development

#### 1. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Backend runs at: `http://localhost:1066`

#### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5174`

#### 3. Default Login
- **Username**: `admin`
- **Password**: `admin`
- **Important**: Change the default password immediately via Settings → Account!

### Docker Deployment

```bash
docker-compose up -d
```

Services:
- Backend: `http://localhost:1066`
- Frontend: `http://localhost:8080`

### AWS ECS Deployment

See **[ECS Setup Guide](docs/ECS_DATABASE_SETUP.md)** for complete instructions.

**Environment Variables**:
```bash
ENV=prod                                    # Development or production
DATABASE_URL=sqlite:///data/theo.db         # SQLite database path
THEO_S3_BACKUP_BUCKET=your-bucket-name      # S3 bucket for backups
THEO_S3_BACKUP_KEY=theo/theo.db            # S3 object key
```

**IAM Permissions**: Use `iam-policy-s3-database-backup.json` for S3 access.

---

## 🛠️ Configuration

### System Prompt
Customize THEO's personality via Settings → System Prompt:
- **Persona Name**: Default "THEO"
- **Tone**: Professional, conversational, direct
- **Style Rules**: No em dashes, concise first, full working solutions
- **Custom Instructions**: Additional behavioral guidelines

### Adding Providers
Settings → Providers → Add Provider:
- **Type**: mock, openai, anthropic
- **Model**: e.g., "gpt-4", "claude-sonnet-4.5"
- **API Key**: Your provider API key
- **Base URL**: Custom endpoint (optional)
- **Enabled**: Toggle provider availability

### Defining Intents
Settings → Intents → Create Intent:
- **Name**: e.g., "coding", "general", "research"
- **Keywords**: Comma-separated trigger words
- **Priority**: Higher priority wins in tie-breaking
- **Description**: Human-readable explanation

### Routing Rules
Settings → Routing Rules → Add Rule:
- **Intent**: Select from defined intents
- **Provider**: Target provider for this intent
- **Enabled**: Toggle rule on/off

Example: Route "coding" intent to Anthropic Claude for code generation tasks.

### Work/Personal Modes
Settings → Work Mode:
- **System Prompt Override**: Custom system prompt for work context
- **Preferred Provider**: Default provider for work mode
- **Work Subtabs**:
  - **Code Development**: Programming language, framework, additional context
  - **Email Rewrites**: Tone setting, signature
  - **Conversation**: General professional context

### Memory Management
Settings → Memory:
- **Add Memory**: Store facts, preferences, goals, or context
- **Pin Memory**: Always include in system prompt
- **Delete Memory**: Remove outdated information
- **Relevance Decay**: Automatic scoring with time-based decay

### Debug Mode
Settings → Debug → Enable Debug Logs

Or via API:
```bash
curl -X POST http://localhost:1066/api/settings/debug \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"enabled": true}'
```

Logs routing decisions, intent classification, and provider selection to backend console.

---

## 🔌 API Overview

### Authentication
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/logout` - Invalidate session token
- `GET /api/auth/verify` - Verify current session
- `POST /api/auth/change-password` - Update password

### Streaming
- `GET /api/stream/<session_id>?text=...&work_subtab=...` - SSE streaming endpoint

### Sessions
- `GET /api/sessions` - List all sessions
- `GET /api/sessions/<id>/messages` - Get session messages
- `DELETE /api/sessions/<id>` - Delete session
- `POST /api/sessions/<id>/fork` - Create conversation branch
- `GET /api/sessions/<id>/export` - Export (JSON/Markdown)

### Memory
- `GET /api/memories?type=...&limit=...` - Retrieve memories
- `POST /api/memories` - Create memory
- `DELETE /api/memories/<id>` - Delete memory
- `POST /api/memories/<id>/pin` - Pin memory
- `GET /api/memories/relevant?q=...` - Search memories

### Intents
- `GET /api/intents` - List intents
- `POST /api/intents` - Create intent
- `PUT /api/intents/<id>` - Update intent
- `DELETE /api/intents/<id>` - Delete intent

### Routing
- `GET /api/routing` - Get routing rules
- `POST /api/routing` - Create routing rule
- `DELETE /api/routing/<intent>` - Delete routing rule

### Providers
- `GET /api/providers` - List providers
- `POST /api/providers` - Add provider
- `DELETE /api/providers/<id>` - Remove provider
- `GET /api/providers/health` - Get health summary

### Mode Management
- `GET /api/mode` - Get current mode
- `POST /api/mode` - Set mode (work/personal)
- `GET /api/mode/settings/<mode>` - Get mode settings
- `POST /api/mode/settings/<mode>` - Update mode settings
- `GET /api/mode/work/subtab/<subtab>` - Get subtab config
- `POST /api/mode/work/subtab/<subtab>` - Update subtab config

### Microsoft 365
- `GET /api/m365/auth/url` - Get OAuth authorization URL
- `GET /api/m365/auth/callback?code=...` - Handle OAuth callback
- `GET /api/m365/status` - Check M365 connection status
- `POST /api/m365/disconnect` - Disconnect M365 account

### Confirmations
- `GET /api/confirmations/pending` - Get pending approval requests
- `POST /api/confirmations/<id>/approve` - Approve action
- `POST /api/confirmations/<id>/reject` - Reject action

See full API documentation in backend code comments.

---

## 🧪 Testing

### Mock Provider
The built-in mock provider is perfect for testing:
- **Deterministic**: Reflects injected context verbatim
- **No API Calls**: Zero external dependencies
- **Fast**: Instant responses

Enable in Settings → Providers or create via API.

---

## 📊 Provider Health Monitoring

THEO tracks provider health in real-time:
- **Success Rate**: Percentage of successful requests
- **Average Latency**: Response time statistics
- **Total Requests**: Request count over time
- **Circuit Breaker**: Automatic fallback when provider fails
- **Cost Estimation**: Token usage and estimated costs

View health dashboard: Settings → Providers → Health Summary

---

## 🔒 Security Notes

### Authentication
- **Hashing**: SHA-256 with 16-byte random salt
- **Sessions**: 32-byte URL-safe random tokens
- **Expiration**: 7-day automatic logout
- **Password Reset**: CLI utility included (`backend/reset_password.py`)

### For Production
Consider upgrading:
- SHA-256 → bcrypt or argon2 for password hashing
- Add rate limiting on login endpoint
- Implement password complexity requirements
- Add two-factor authentication (2FA)
- Add session activity audit logging

### Designed For
Single-user or small team self-hosted deployment. Not recommended for large-scale multi-tenant environments without security enhancements.

---

## 🛣️ Roadmap

### Completed
- ✅ Multi-model routing with intent classification
- ✅ Session management with persistent context
- ✅ Structured memory system with relevance scoring
- ✅ Provider health monitoring and circuit breaker
- ✅ Authentication with password management
- ✅ Work/Personal modes with subtab configurations
- ✅ S3 database backup for AWS deployments
- ✅ Streaming responses via SSE
- ✅ **Action provider system with two-step confirmations**
- ✅ **Microsoft 365 integration (Calendar & Email)**
- ✅ **OAuth 2.0 authentication with automatic token refresh**
- ✅ **LLM-powered email composition with natural language**
- ✅ **Context-aware intent routing (calendar/email)**
- ✅ **Draft workflow: Create → Review → Approve → Send/Delete**

### In Progress
- 🔄 Cross-model conversation continuity (summarization strategy)
- 🔄 Enhanced memory relevance decay algorithms
- 🔄 Email attachments support
- 🔄 Recurring calendar events

### Planned
- 📋 Google Workspace integration (Gmail, Calendar, Drive)
- 📋 Slack integration for team communication
- 📋 GitHub integration for issue/PR management
- 📋 Voice input/output support
- 📋 Multi-user administration UI
- 📋 Role-based access control (RBAC)
- 📋 Advanced provider cost optimization
- 📋 Custom model fine-tuning integration
- 📋 Email threading and conversation view
- 📋 Calendar conflict detection and smart scheduling

---

## 🐛 Known Limitations

### Current Design Choices
- **Authentication**: SHA-256 hashing (simple, suitable for self-hosted single-user)
- **Sessions**: 7-day fixed expiration (no refresh mechanism)
- **Password**: 4-character minimum (consider complexity rules for production)
- **Rate Limiting**: None (acceptable for self-hosted)

### Not Yet Implemented
- Multi-user administration
- Email-based password reset
- Two-factor authentication (2FA)
- Account lockout mechanism
- Provider streaming timeout handling

---

## 📜 License

No license applied yet. This project is currently private / experimental.

---

## 👨‍💻 Author

**Danny Black**

THEO is being developed as both a tool and a learning platform, exploring the intersection of multi-model AI orchestration, context preservation, and user-centric design.

---

## 🤝 Contributing

This is currently a personal project. If you have suggestions or find issues, feel free to reach out or submit a GitHub issue.

---

## 🙏 Acknowledgments

Built with:
- [Flask](https://flask.palletsprojects.com/) - Backend framework
- [Svelte](https://svelte.dev/) - Frontend framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM
- [Anthropic Claude](https://www.anthropic.com/) - AI provider
- [OpenAI GPT](https://openai.com/) - AI provider

---

**Last Updated**: December 2024
