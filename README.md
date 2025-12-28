# THEO – Personal Multi-Model AI Assistant

THEO is a self-hosted AI assistant that intelligently routes requests to the most appropriate AI model based on intent, while maintaining conversation continuity and context across models.

**Philosophy**: Not "one model to rule them all," but use different models for different tasks while preserving seamless user experience.

[![Tests](https://img.shields.io/badge/tests-617%20total-blue)]() [![Coverage](https://img.shields.io/badge/coverage-40.54%25-yellow)]() [![License](https://img.shields.io/badge/license-private-red)]()

---

## ✨ Key Features

- **Multi-Model Routing** - Intelligent routing based on user-defined intents
- **Microsoft 365 Integration** - Calendar and email management via Graph API
- **Work/Personal Modes** - Dual-mode system with mode-specific configurations
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
- **[M365 Integration](docs/M365_INTEGRATION.md)** - Microsoft 365 setup
- **[AWS Deployment](docs/ECS_DATABASE_SETUP.md)** - ECS and S3 configuration
- **[Testing Guide](docs/TESTING.md)** - Running and writing tests
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
│   ├── routes/                # 14 modular route blueprints
│   ├── core/                  # Core business logic
│   │   ├── actions/           # Action handlers (5 modules)
│   │   └── memory/            # Memory operations (12 modules)
│   ├── providers/             # AI provider integrations
│   ├── actions/               # Action providers (M365, etc.)
│   └── tests/                 # 353 backend tests
└── frontend/
    ├── src/
    │   ├── components/        # Svelte components
    │   │   └── settings/      # 10 modular settings components
    │   └── lib/api.js         # REST client
    └── tests/                 # 264 frontend tests
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
pytest                                      # Run all tests
pytest --cov=. --cov-report=html           # With coverage
```

**Current Status**: 353 tests, 169 passing, 40.54% coverage

### Frontend Tests

```bash
cd frontend
npm test                                    # Run all tests
npm run test:coverage                       # With coverage
```

**Current Status**: 264 tests, 149 passing

See [TESTING.md](docs/TESTING.md) for detailed test documentation.

---

## 📊 Project Stats

- **Backend**: 5,121 lines across 54 modular files
- **Frontend**: Refactored from 2,777-line monolith to 10 components
- **Tests**: 617 total tests (backend + frontend)
- **Coverage**: 40.54% backend, expanding frontend coverage
- **Routes**: 14 blueprint modules with 63+ endpoints
- **Documentation**: 8 comprehensive docs + GitHub Wiki

---

## 🛣️ Roadmap

### ✅ Completed
- Multi-model routing with intent classification
- Microsoft 365 integration (Calendar & Email)
- OAuth 2.0 with automatic token refresh
- Work/Personal modes with subtab configurations
- Provider health monitoring and circuit breaker
- Comprehensive testing infrastructure (617 tests)
- Full codebase refactoring and modularization

### 🔄 In Progress
- Expanding test coverage to 70%+
- Cross-model conversation continuity
- Enhanced memory relevance algorithms

### 📋 Planned
- Google Workspace integration
- Slack integration
- Voice input/output
- Multi-user administration UI
- Email attachments and threading
- Calendar conflict detection

---

## 🔒 Security

**Default Authentication:**
- Username: `admin`
- Password: `admin`
- ⚠️ **Change immediately in production!**

**For Production Deployments:**
- Upgrade SHA-256 to bcrypt/argon2
- Implement rate limiting
- Add 2FA support
- Enable password complexity requirements
- Review [AUTHENTICATION.md](docs/AUTHENTICATION.md)

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

**Last Updated**: December 28, 2025
