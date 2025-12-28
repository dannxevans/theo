# THEO Configuration Guide

Complete guide to configuring THEO for your needs.

---

## 🎯 System Prompt Configuration

The system prompt defines THEO's personality and behavior.

### Accessing System Prompt Settings

1. Login to THEO
2. Click Settings (gear icon)
3. Navigate to "General" tab

### Configuration Options

**Persona Name** (default: "THEO")
- The name THEO uses when referring to itself
- Example: "THEO", "Assistant", "Helper"

**Tone** (default: "professional, conversational, direct")
- Defines communication style
- Examples:
  - "friendly and casual"
  - "formal and technical"
  - "concise and to-the-point"

**Style Rules** (default: "No em dashes, concise first, full solutions")
- Behavioral guidelines for responses
- Examples:
  - "Use bullet points for lists"
  - "Always provide code examples"
  - "Explain your reasoning"

**Custom Instructions**
- Additional context or requirements
- Examples:
  - "I'm a Python developer working with Flask"
  - "Always use TypeScript examples for JavaScript"
  - "Prefer functional programming patterns"

### API Configuration

```bash
POST /api/settings/system-prompt
Content-Type: application/json
Authorization: Bearer {token}

{
  "persona_name": "THEO",
  "tone": "professional",
  "style_rules": "Be concise, use examples",
  "custom_instructions": "I work with Python and Flask"
}
```

---

## 🤖 AI Provider Configuration

### Adding Providers

**Via UI:**
1. Settings → Providers → "Add Provider"
2. Fill in provider details
3. Click "Save"

**Via API:**
```bash
POST /api/providers
Content-Type: application/json
Authorization: Bearer {token}

{
  "provider_id": "anthropic-sonnet",
  "type": "anthropic",
  "model": "claude-sonnet-4.5",
  "api_key": "sk-ant-...",
  "is_enabled": true
}
```

### Supported Provider Types

**OpenAI**
```json
{
  "type": "openai",
  "model": "gpt-4",
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1"
}
```

**Anthropic**
```json
{
  "type": "anthropic",
  "model": "claude-sonnet-4.5",
  "api_key": "sk-ant-...",
  "base_url": "https://api.anthropic.com"
}
```

**Mock Provider (Testing)**
```json
{
  "type": "mock",
  "model": "mock-model"
}
```

### Provider Health Monitoring

THEO automatically tracks:
- Success rate
- Average latency
- Total requests
- Cost estimation
- Circuit breaker state

View in: Settings → Providers → Health Summary

---

## 🎯 Intent Configuration

Intents categorize user requests to enable intelligent routing.

### Creating Intents

**Via UI:**
1. Settings → Intents → "New Intent"
2. Configure:
   - **Name**: Unique identifier (e.g., "coding")
   - **Keywords**: Trigger words (comma-separated)
   - **Priority**: Higher = wins in ties (1-100)
   - **Description**: Human-readable explanation
   - **Enabled**: Toggle on/off
3. Click "Save"

**Via API:**
```bash
POST /api/intents
Content-Type: application/json
Authorization: Bearer {token}

{
  "name": "coding",
  "keywords": ["code", "debug", "function", "python", "javascript"],
  "priority": 50,
  "description": "Programming and coding tasks",
  "is_enabled": true
}
```

### Intent Examples

**Coding Intent:**
```json
{
  "name": "coding",
  "keywords": ["code", "debug", "function", "class", "api"],
  "priority": 50
}
```

**Research Intent:**
```json
{
  "name": "research",
  "keywords": ["research", "find", "search", "lookup", "information"],
  "priority": 40
}
```

**General Intent (Fallback):**
```json
{
  "name": "general",
  "keywords": [],
  "priority": 1,
  "description": "Default fallback intent"
}
```

### Keyword Matching

- Case-insensitive matching
- Whole word matching
- Priority-based tie-breaking
- Context-aware for actions (calendar/email)

---

## 🔀 Routing Configuration

Routing rules map intents to specific providers.

### Creating Routing Rules

**Via UI:**
1. Settings → Routing → "Add Rule"
2. Select:
   - **Intent**: From your defined intents
   - **Provider**: Target AI provider
3. Click "Save"

**Via API:**
```bash
POST /api/routing
Content-Type: application/json
Authorization: Bearer {token}

{
  "intent": "coding",
  "provider_id": 1
}
```

### Routing Logic

THEO selects providers in this order:

1. **Forced Provider** (user override in chat UI)
2. **Routing Rules** (intent → provider mapping)
3. **Intent Default** (provider configured in intent)
4. **Health-Based Fallback** (circuit breaker)

### Example Configuration

```
Intent "coding" → Provider "anthropic-sonnet"
Intent "research" → Provider "openai-gpt4"
Intent "general" → Provider "mock" (testing)
```

---

## 🧠 Memory Configuration

### Adding Memories

**Via UI:**
1. Settings → Memory → "Add Memory"
2. Configure:
   - **Type**: fact, preference, goal, context
   - **Key**: Memory identifier
   - **Value**: Memory content
   - **Pinned**: Always include in context
3. Click "Save"

**Via API:**
```bash
POST /api/memories
Content-Type: application/json
Authorization: Bearer {token}

{
  "type": "preference",
  "key": "programming_language",
  "value": "Python",
  "is_pinned": true
}
```

### Memory Types

**Facts**
- Objective information
- Example: "My name is John Doe"

**Preferences**
- User preferences
- Example: "I prefer Python over JavaScript"

**Goals**
- User objectives
- Example: "Learning machine learning"

**Context**
- Situational information
- Example: "Working on e-commerce project"

### Memory Relevance

- Memories have relevance scores (0.0 - 1.0)
- Scores decay over time
- Pinned memories always included
- Recent memories weighted higher

---

## 🎭 Mode Configuration

THEO supports Work and Personal modes with separate configurations.

### Setting Current Mode

**Via UI:**
- Toggle in header: "Work" / "Personal"

**Via API:**
```bash
POST /api/mode
Content-Type: application/json
Authorization: Bearer {token}

{
  "mode": "work"
}
```

### Mode-Specific Settings

**Via UI:**
1. Settings → Work Mode (or Personal Mode)
2. Configure:
   - System Prompt Override
   - Preferred Provider
3. Click "Save"

**Via API:**
```bash
POST /api/mode/settings/work
Content-Type: application/json
Authorization: Bearer {token}

{
  "system_prompt_override": "You are a professional assistant...",
  "preferred_provider_id": 1
}
```

### Work Mode Subtabs

**Conversation** (default)
- General professional discussion

**Code Development**
- Configure:
  - Programming Language (Python, JavaScript, etc.)
  - Framework (Flask, React, etc.)
  - Additional Context

**Email Rewrites**
- Configure:
  - Tone (Formal, Friendly, etc.)
  - Signature

---

## 📅 Microsoft 365 Configuration

### Prerequisites

1. Azure AD App Registration
2. Configured redirect URI: `http://localhost:1066/api/m365/auth/callback`
3. API Permissions:
   - `Calendars.ReadWrite`
   - `Mail.ReadWrite`
   - `Mail.Send`
   - `offline_access`

### Connecting M365 Account

**Via UI:**
1. Settings → Integrations → "Connect Microsoft 365"
2. Click "Authorize"
3. Login to Microsoft account
4. Grant permissions
5. Redirected back to THEO

**Via API:**
1. Get authorization URL:
```bash
GET /api/m365/auth/url
Authorization: Bearer {token}
```

2. Direct user to returned URL
3. Handle callback at `/api/m365/auth/callback?code=...`

### M365 Configuration in Azure

**App Registration Settings:**
```
Name: THEO
Redirect URI: http://localhost:1066/api/m365/auth/callback
Client Secret: (generate and save)
API Permissions: Calendars.ReadWrite, Mail.ReadWrite, Mail.Send
```

**Environment Variables:**
```bash
M365_CLIENT_ID=your-client-id
M365_CLIENT_SECRET=your-client-secret
M365_REDIRECT_URI=http://localhost:1066/api/m365/auth/callback
```

---

## 🔒 Authentication Configuration

### Default Credentials

```
Username: admin
Password: admin
```

⚠️ **Change immediately after first login!**

### Changing Password

**Via UI:**
1. Settings → Account → "Change Password"
2. Enter current password
3. Enter new password (min 4 characters)
4. Click "Save"

**Via API:**
```bash
POST /api/auth/change-password
Content-Type: application/json
Authorization: Bearer {token}

{
  "current_password": "admin",
  "new_password": "new_secure_password"
}
```

### Resetting Password (CLI)

If locked out:

```bash
cd backend
python reset_password.py
```

Follow prompts to reset admin password.

### Session Configuration

- **Session Duration**: 7 days
- **Token Storage**: localStorage (frontend)
- **Token Format**: 32-byte URL-safe random string

---

## ⚙️ Environment Variables

### Backend Configuration

Create `backend/.env`:

```bash
# Environment
ENV=dev                # dev | prod

# Database
DATABASE_URL=sqlite:///theo.db

# S3 Backup (Production)
THEO_S3_BACKUP_BUCKET=your-bucket-name
THEO_S3_BACKUP_KEY=theo/theo.db
AWS_REGION=us-east-1

# Microsoft 365
M365_CLIENT_ID=your-client-id
M365_CLIENT_SECRET=your-client-secret
M365_REDIRECT_URI=http://localhost:1066/api/m365/auth/callback

# Debug
DEBUG=false
```

### Frontend Configuration

Create `frontend/.env`:

```bash
# API URL
VITE_API_URL=http://localhost:1066

# Environment
VITE_ENV=development
```

---

## 🐳 Docker Configuration

### docker-compose.yml

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "1066:1066"
    environment:
      - ENV=prod
      - DATABASE_URL=sqlite:///data/theo.db
    volumes:
      - ./data:/data

  frontend:
    build: ./frontend
    ports:
      - "8080:80"
    depends_on:
      - backend
```

### Volumes

- `/data` - Database storage
- `/backend/.env` - Environment variables (mounted)

---

## 🔧 Advanced Configuration

### Debug Mode

Enable detailed logging:

**Via UI:**
Settings → Debug → Enable Debug Logs

**Via API:**
```bash
POST /api/settings/debug
Content-Type: application/json
Authorization: Bearer {token}

{
  "enabled": true
}
```

### Custom Base URLs

For providers with custom endpoints:

```json
{
  "type": "openai",
  "model": "gpt-4",
  "api_key": "sk-...",
  "base_url": "https://your-custom-endpoint.com/v1"
}
```

### Health Check Intervals

Configure in `backend/core/provider_registry.py`:

```python
HEALTH_CHECK_INTERVAL = 300  # 5 minutes
CIRCUIT_BREAKER_THRESHOLD = 5  # failures before open
CIRCUIT_BREAKER_TIMEOUT = 60  # seconds in open state
```

---

## 📊 Monitoring Configuration

### Provider Metrics

View in Settings → Providers → Health Summary:

- Success Rate
- Average Latency
- Total Requests
- Estimated Cost
- Circuit Breaker State

### Request Logs

Enable in database:

```sql
SELECT * FROM request_logs
ORDER BY created_at DESC
LIMIT 100;
```

---

## 🔒 Security Configuration

### Production Hardening

1. **Change Default Password**
   ```bash
   python backend/reset_password.py
   ```

2. **Upgrade Password Hashing**
   - Replace SHA-256 with bcrypt/argon2
   - Increase salt size

3. **Add Rate Limiting**
   - Install Flask-Limiter
   - Configure per-endpoint limits

4. **Enable HTTPS**
   - Use reverse proxy (nginx/Apache)
   - Configure SSL certificates

5. **Add CORS Restrictions**
   ```python
   CORS(app, origins=["https://your-domain.com"])
   ```

---

## 📝 Configuration Best Practices

### Intent Keywords

✅ **Do:**
- Use specific, relevant keywords
- Include variations and synonyms
- Test with real queries

❌ **Don't:**
- Use generic words in multiple intents
- Create too many overlapping intents
- Set all priorities to the same value

### Provider Configuration

✅ **Do:**
- Test providers before enabling
- Monitor health metrics regularly
- Set appropriate model selection

❌ **Don't:**
- Store API keys in version control
- Enable untested providers in production
- Ignore circuit breaker alerts

### Memory Management

✅ **Do:**
- Pin important, permanent memories
- Review and clean outdated memories
- Use descriptive keys

❌ **Don't:**
- Store sensitive information
- Create duplicate memories
- Pin everything (reduces effectiveness)

---

## 🆘 Troubleshooting

**Routing not working?**
- Check intent keywords match your queries
- Verify routing rules are saved
- Enable debug mode to see classification

**Provider failing?**
- Check API key is valid
- Verify base URL is correct
- Check provider health status

**M365 not connecting?**
- Verify Azure AD configuration
- Check redirect URI matches exactly
- Ensure API permissions granted

---

**Last Updated**: December 28, 2025

For API details, see [[API Reference]].
For architecture, see [[Architecture]].
