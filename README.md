# THEO – Personal Multi-Model AI Assistant

THEO is a self-hosted AI assistant that intelligently routes requests to the most appropriate AI model based on intent, while maintaining conversation continuity and context across models.

**Philosophy**: Not "one model to rule them all," but use different models for different tasks while preserving seamless user experience.

[![CI/CD](https://img.shields.io/badge/CI%2FCD-passing-brightgreen)]() [![Tests](https://img.shields.io/badge/tests-779%20passing-brightgreen)]() [![Backend](https://img.shields.io/badge/backend-100%25%20passing-brightgreen)]() [![codecov](https://codecov.io/github/dannxevans/theo/branch/release/graph/badge.svg?token=H1XKWWQ8NL)](https://codecov.io/github/dannxevans/theo) [![License](https://img.shields.io/badge/license-private-red)]()

---

## ✨ Key Features

- **Multi-Model Routing** - Intelligent routing based on user-defined intents
- **Database Audit** - Admin interface to inspect all sessions and conversation turns (*Issue #290*)
- **LLM Request Context Capture** - Debug LLM responses by viewing full request context (system prompts, conversation history)
- **API Key Authentication** - Secure API keys for Siri Shortcuts and automation (*Issue #239*)
- **Voice Features** - Text-to-Speech and Speech-to-Text powered by OpenAI
- **Microsoft 365 Integration** - Calendar and email management via Graph API
- **Work/Personal Modes** - Dual-mode system with mode-specific configurations
- **Context-Aware Planning** - Intelligent planning with weather, traffic, and calendar integration
- **Memory System** - Structured memory with relevance scoring and pinning
- **Action Confirmations** - Two-step approval workflow for external actions
- **Provider Health Monitoring** - Circuit breaker pattern with automatic fallback
- **Streaming Responses** - Real-time token streaming via Server-Sent Events

---

## 🚀 Quick Start 

### Prerequisites

- Python 3.9+
- Node.js 16+
- (Optional) AWS account for S3 backups

### Local Development

**1. Clone and Setup Backend:**
```bash
git clone https://github.com/dannxevans/theo.git
cd theo/backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Backend runs at `http://localhost:1066`

**2. Setup Frontend:**
```bash
cd ../frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5174`

**3. Login:**
- **Username**: `admin`
- **Password**: `admin`
- ⚠️ **Change the default password immediately** via Settings → Account!

### Docker Deployment

```bash
docker-compose up -d
```

- Backend: `http://localhost:1066`
- Frontend: `http://localhost:8080`

---

## 📚 Documentation

For comprehensive documentation, visit the **[THEO Wiki](https://github.com/dannxevans/theo/wiki)**

### Quick Links

- **[Architecture Overview](https://github.com/dannxevans/theo/wiki/Architecture)** - System design and components
- **[API Reference](https://github.com/dannxevans/theo/wiki/API-Reference)** - Complete API documentation
- **[Configuration Guide](https://github.com/dannxevans/theo/wiki/Configuration)** - System prompts, intents, routing
- **[Testing Guide](https://github.com/dannxevans/theo/wiki/Testing-Guide)** - Running and writing tests
- **[Test Results](https://github.com/dannxevans/theo/wiki/Test-Results)** - Current test status and detailed analysis
- **[Voice Features](DOCS/voice-features.md)** - Text-to-Speech and Speech-to-Text setup
- **[M365 Integration](docs/M365_INTEGRATION.md)** - Microsoft 365 setup
- **[AWS Deployment](docs/ECS_DATABASE_SETUP.md)** - ECS and S3 configuration
- **[Authentication](docs/AUTHENTICATION.md)** - Security and password management

### Local Documentation

```
docs/
├── AUTHENTICATION.md          # Auth system and security
├── DATABASE_PERSISTENCE.md    # S3 backup/restore
├── ECS_DATABASE_SETUP.md     # AWS ECS deployment
├── M365_INTEGRATION.md       # Microsoft 365 setup
├── SERVICE_BOOKING.md        # Service provider integration
├── TESTING.md                # Test infrastructure and coverage
└── archive/                  # Refactoring history

DOCS/
├── voice-features.md         # Voice TTS/STT user guide
└── voice-implementation-summary.md  # Voice features technical docs
```

---

## 🏗️ Architecture

### Stack

- **Backend**: Python 3.9+ / Flask / SQLAlchemy
- **Frontend**: Svelte / Vite
- **Database**: SQLite (with S3 backup for production)
- **Deployment**: Docker / AWS ECS

### Project Structure

```
theo/
├── backend/
│   ├── app.py                 # Main Flask application
│   ├── routes/                # 15 modular route blueprints
│   ├── core/                  # Core business logic
│   │   ├── actions/           # Action handlers (5 modules)
│   │   └── memory/            # Memory operations (12 modules)
│   ├── providers/             # AI provider integrations
│   ├── voice/                 # TTS/STT providers (OpenAI)
│   ├── actions/               # Action providers (M365, etc.)
│   └── tests/                 # 779 backend tests (100% passing)
└── frontend/
    ├── src/
    │   ├── components/        # Svelte components
    │   │   ├── settings/      # 11 modular settings components
    │   │   └── VoiceControls.svelte  # Voice UI controls
    │   └── lib/api.js         # REST client
    └── tests/                 # 264 frontend tests (58% passing)
```

---

## 🔧 Configuration

### Adding AI Providers

Settings → Providers → Add Provider

```
Type: openai | anthropic | mock
Model: gpt-4 | claude-sonnet-4.5
API Key: your-api-key-here
```

### Defining Intents

Settings → Intents → Create Intent

```
Name: coding
Keywords: code, debug, function, python, javascript
Priority: 50
```

### Setting Up Routing

Settings → Routing → Add Rule

```
Intent: coding
Provider: anthropic-sonnet
```

### Environment Variables

```bash
ENV=prod                                    # prod | dev
DATABASE_URL=sqlite:///data/theo.db         # Database path
THEO_S3_BACKUP_BUCKET=your-bucket           # S3 backup bucket
THEO_S3_BACKUP_KEY=theo/theo.db            # S3 object key
```

---

## 🧪 Testing

### Backend Tests

```bash
cd backend
pip install -e .                            # Install package for testing
pytest tests/memory tests/core              # Core business logic tests
pytest tests/routes                         # API route tests
pytest --cov=. --cov-report=html           # With coverage
```

**Current Status**:
- **All Backend Tests: 779/779 passing (100%)**
- Code Coverage: 51%

### Frontend Tests

```bash
cd frontend
npm test                                    # Run all tests
npm run test:coverage                       # With coverage
```

**Current Status**: Frontend tests available

**Overall**: 779 backend tests passing (100%)

See [Testing Guide](https://github.com/dannxevans/theo/wiki/Testing-Guide) and [Test Results](https://github.com/dannxevans/theo/wiki/Test-Results) for detailed documentation.

---

## 📊 Project Stats

- **Backend**: 5,300+ lines across 58 modular files
- **Frontend**: Refactored from 2,777-line monolith to 12 components
- **Tests**: 779 backend tests, all passing (100%)
- **Test Pass Rate**: 100% backend (779/779 passing)
- **Code Coverage**: 51% backend
- **Routes**: 16 blueprint modules with 69+ endpoints
- **Documentation**: 10 comprehensive docs + GitHub Wiki

---

## 🛣️ Roadmap

### ✅ Completed
- Multi-model routing with intent classification
- **Database Audit** admin interface with filtering and pagination (*Issue #290*)
- **Full LLM Request Context Capture** for debugging unexpected responses
- **API Key Authentication** for Siri Shortcuts and automation (*Issue #239*)
- **Context-Aware Planning** with weather, traffic, and calendar integration
- Voice Features (OpenAI TTS/STT with auto-read mode)
- Microsoft 365 integration (Calendar & Email)
- OAuth 2.0 with automatic token refresh
- Work/Personal modes with subtab configurations
- Provider health monitoring and circuit breaker
- Comprehensive testing infrastructure (779 backend tests, 100% passing)
- Full codebase refactoring and modularization
- UK Government OFFICIAL classification compliance
- Explicit planning intent detection (reduced false positives)

### 🔄 In Progress
- Expanding frontend test coverage to 80%+
- Cross-model conversation continuity
- Enhanced memory relevance algorithms

### 📋 Planned
- **Prompt Caching** - Anthropic prompt caching for 60% cost reduction
- Google Workspace integration
- Slack integration
- Multi-user administration UI
- Email attachments and threading
- Calendar conflict detection
- Advanced voice controls

---

## 🔒 Security

**Default Authentication:**
- Username: `admin`
- Password: `admin`
- ⚠️ **Change immediately in production!**

**Authentication Methods:**
- **Session Tokens**: For web UI login
- **API Keys**: For Siri Shortcuts and automation (format: `theo_<64_hex>`)

**For Production Deployments:**
- Passwords now use bcrypt (secure by default)
- Implement rate limiting for API keys
- Add 2FA support
- Enable password complexity requirements
- Review [Authentication Wiki](https://github.com/dannxevans/theo/wiki/Authentication)

**Designed for**: Self-hosted single-user or small team deployments

---

## 🐛 Troubleshooting

**Backend won't start?**
- Check Python version: `python3 --version` (requires 3.9+)
- Verify dependencies: `pip install -r requirements.txt`
- Check port 1066 availability

**Frontend won't start?**
- Check Node version: `node --version` (requires 16+)
- Clear node_modules: `rm -rf node_modules && npm install`
- Check port 5174 availability

**Can't login?**
- Reset password: `cd backend && python reset_password.py`
- Check database exists: `ls backend/theo.db`

For more help, see the [Wiki Troubleshooting Guide](https://github.com/dannxevans/theo/wiki/Troubleshooting)

---

## 🤝 Contributing

This is currently a personal project. Suggestions and issues are welcome via [GitHub Issues](https://github.com/dannxevans/theo/issues).

---

## 📜 License

No license applied yet. This project is currently private/experimental.

---

## 👨‍💻 Author

**Danny Black** - Building THEO as a learning platform for multi-model AI orchestration

---

## 🙏 Acknowledgments

Built with:
- [Flask](https://flask.palletsprojects.com/) - Backend framework
- [Svelte](https://svelte.dev/) - Frontend framework
- [SQLAlchemy](https://www.sqlalchemy.org/) - Database ORM
- [Anthropic Claude](https://www.anthropic.com/) - AI provider
- [OpenAI GPT](https://openai.com/) - AI provider

---

**Last Updated**: January 5, 2026
