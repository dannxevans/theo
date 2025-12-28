# Welcome to the THEO Wiki

THEO is a self-hosted AI assistant that intelligently routes requests to the most appropriate AI model based on intent, while maintaining conversation continuity and context across models.

## 📖 Quick Navigation

### Getting Started
- [[Quick Start Guide]] - Install and run THEO in 5 minutes
- [[Configuration]] - Configure providers, intents, and routing
- [[First Steps]] - Your first conversation with THEO

### Core Features
- [[Architecture]] - System design and components
- [[Multi-Model Routing]] - How THEO routes requests
- [[Memory System]] - Structured memory and context management
- [[Work and Personal Modes]] - Dual-mode configuration

### Integrations
- [[Microsoft 365 Integration]] - Calendar and email management
- [[AI Providers]] - Adding and configuring AI providers
- [[Action Providers]] - External service integrations

### Development
- [[API Reference]] - Complete REST API documentation
- [[Testing Guide]] - Running and writing tests
- [[Contributing]] - How to contribute to THEO
- [[Troubleshooting]] - Common issues and solutions

### Deployment
- [[Local Development]] - Running THEO locally
- [[Docker Deployment]] - Containerized deployment
- [[AWS ECS Deployment]] - Production deployment on AWS
- [[Database Backups]] - S3 backup and restore

### Security
- [[Authentication]] - Login, sessions, and password management
- [[Security Best Practices]] - Hardening THEO for production
- [[Privacy]] - Data storage and privacy considerations

---

## 🚀 What is THEO?

THEO (The Helper Engine Orchestrator) is designed around the philosophy that no single AI model excels at everything. Instead, THEO allows you to:

1. **Define Intents** - Categorize different types of requests (coding, research, general chat, etc.)
2. **Route Intelligently** - Automatically send requests to the best model for each intent
3. **Maintain Context** - Preserve conversation history and user context across model switches
4. **Execute Actions** - Integrate with external services like Microsoft 365, Google Workspace, etc.
5. **Monitor Health** - Track provider performance and automatically fallback when issues occur

---

## ✨ Key Features

### Multi-Model Orchestration
- Intelligent routing based on user-defined intents
- Automatic fallback when providers fail
- Circuit breaker pattern for provider health
- Seamless model switching mid-conversation

### Microsoft 365 Integration
- **Calendar**: Read, create, update, delete events
- **Email**: Read, compose, reply, send with LLM assistance
- **OAuth 2.0**: Secure authentication with automatic token refresh

### Memory & Context
- Structured memory (facts, preferences, goals, context)
- Relevance scoring with time-based decay
- Pinned memories always included in prompts
- Session summaries for long conversations

### Work/Personal Modes
- Dual-mode system with separate configurations
- Work subtabs: Conversation, Code Development, Email Rewrites
- Mode-specific system prompts and provider preferences

### Action Confirmations
- Two-step approval workflow for external actions
- UI approval widgets for calendar and email operations
- Approval expiration and rejection handling

### Provider Health Monitoring
- Real-time success rate tracking
- Average latency measurements
- Cost estimation (token usage)
- Circuit breaker for automatic fallback

---

## 📊 Project Status

- **Version**: Beta (Active Development)
- **Backend**: Python 3.9+ / Flask / SQLAlchemy
- **Frontend**: Svelte / Vite
- **Database**: SQLite with S3 backup support
- **Tests**: 617 total tests (353 backend + 264 frontend)
- **Coverage**: 40.54% backend, expanding frontend

---

## 🗂️ Documentation Structure

This wiki is organized into the following sections:

### For Users
- Setup and configuration guides
- Feature documentation
- Integration tutorials
- Troubleshooting

### For Developers
- Architecture documentation
- API reference
- Testing guides
- Contributing guidelines

### For Operators
- Deployment guides
- Security hardening
- Backup and restore
- Monitoring and maintenance

---

## 🤝 Community

- **Issues**: [GitHub Issues](https://github.com/dannxevans/theo/issues)
- **Discussions**: [GitHub Discussions](https://github.com/dannxevans/theo/discussions)
- **Author**: Danny Black

---

## 📜 License

This project is currently private/experimental. No license has been applied yet.

---

**Last Updated**: December 28, 2025

Navigate using the sidebar or search for specific topics using the search bar above.
