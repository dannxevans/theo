# THEO API Reference

Complete REST API documentation for THEO. All endpoints require authentication unless otherwise noted.

**Base URL**: `http://localhost:1066`

---

## 🔐 Authentication

### POST `/api/auth/login`

Authenticate user and receive session token.

**Request:**
```json
{
  "username": "admin",
  "password": "admin"
}
```

**Response (200 OK):**
```json
{
  "token": "abc123...",
  "user": {
    "id": 1,
    "username": "admin",
    "is_admin": true
  }
}
```

**Errors:**
- `401` - Invalid credentials
- `400` - Missing username or password

---

### POST `/api/auth/logout`

Invalidate current session token.

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "message": "Logged out successfully"
}
```

---

### GET `/api/auth/verify`

Verify current session token is valid.

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "user": {
    "id": 1,
    "username": "admin"
  }
}
```

**Errors:**
- `401` - Invalid or expired token

---

### POST `/api/auth/change-password`

Change user password.

**Headers:**
```
Authorization: Bearer {token}
```

**Request:**
```json
{
  "current_password": "oldpass",
  "new_password": "newpass"
}
```

**Response (200 OK):**
```json
{
  "message": "Password changed successfully"
}
```

**Errors:**
- `401` - Current password incorrect
- `400` - New password too short (min 4 chars)

---

## 💬 Chat & Streaming

### GET `/api/stream/{session_id}`

Stream chat response via Server-Sent Events (SSE).

**Headers:**
```
Authorization: Bearer {token}
```

**Query Parameters:**
- `text` (required): User message
- `work_subtab` (optional): Work mode subtab (conversation/code/email)
- `force_provider` (optional): Force specific provider ID

**Response (text/event-stream):**
```
data: {"token": "Hello"}
data: {"token": " world"}
data: {"done": true, "provider": "openai-1", "model": "gpt-4", "intent": "general"}
```

**Confirmation Response:**
```
data: {"confirmation_required": true, "confirmation_id": 123, "action": {...}}
```

---

### GET `/api/message/{session_id}/{turn_id}`

Retrieve specific message from session.

**Response (200 OK):**
```json
{
  "id": 456,
  "session_id": 123,
  "role": "assistant",
  "content": "Hello! How can I help?",
  "provider": "openai-1",
  "model": "gpt-4",
  "created_at": "2025-12-28T10:30:00Z"
}
```

---

## 📝 Sessions

### GET `/api/sessions`

List all chat sessions for current user.

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200 OK):**
```json
{
  "sessions": [
    {
      "id": 123,
      "title": "Coding Help",
      "mode": "work",
      "created_at": "2025-12-28T10:00:00Z",
      "updated_at": "2025-12-28T10:30:00Z",
      "message_count": 12
    }
  ]
}
```

---

### GET `/api/sessions/{id}/messages`

Get all messages for a session.

**Headers:**
```
Authorization: Bearer {token}
```

**Query Parameters:**
- `limit` (optional): Max messages to return (default: 50)
- `offset` (optional): Offset for pagination (default: 0)

**Response (200 OK):**
```json
{
  "messages": [
    {
      "id": 1,
      "role": "user",
      "content": "Hello",
      "created_at": "2025-12-28T10:00:00Z"
    },
    {
      "id": 2,
      "role": "assistant",
      "content": "Hi! How can I help?",
      "provider": "openai-1",
      "model": "gpt-4",
      "created_at": "2025-12-28T10:00:05Z"
    }
  ]
}
```

---

### POST `/api/sessions`

Create new chat session.

**Request:**
```json
{
  "title": "My Session",
  "mode": "personal"
}
```

**Response (201 Created):**
```json
{
  "id": 124,
  "title": "My Session",
  "mode": "personal"
}
```

---

### DELETE `/api/sessions/{id}`

Delete a session and all its messages.

**Response (200 OK):**
```json
{
  "message": "Session deleted"
}
```

---

### POST `/api/sessions/{id}/fork`

Fork a session at specific message.

**Request:**
```json
{
  "turn_id": 5,
  "title": "Forked Conversation"
}
```

**Response (201 Created):**
```json
{
  "new_session_id": 125,
  "title": "Forked Conversation",
  "messages_copied": 5
}
```

---

### GET `/api/sessions/{id}/export`

Export session as JSON or Markdown.

**Query Parameters:**
- `format`: `json` or `markdown` (default: json)

**Response (200 OK):**
```json
{
  "session": {...},
  "messages": [...]
}
```

Or for markdown:
```markdown
# Coding Help

**User**: How do I write a function?
**Assistant**: Here's an example...
```

---

## 🧠 Memory

### GET `/api/memories`

Retrieve memories for current user.

**Query Parameters:**
- `type` (optional): Filter by type (fact/preference/goal/context)
- `limit` (optional): Max memories (default: 100)
- `pinned_only` (optional): Only return pinned memories

**Response (200 OK):**
```json
{
  "memories": [
    {
      "id": 1,
      "type": "fact",
      "key": "name",
      "value": "John Doe",
      "score": 1.0,
      "is_pinned": false,
      "created_at": "2025-12-28T10:00:00Z"
    }
  ]
}
```

---

### POST `/api/memories`

Create new memory.

**Request:**
```json
{
  "type": "preference",
  "key": "language",
  "value": "Python",
  "is_pinned": true
}
```

**Response (201 Created):**
```json
{
  "id": 2,
  "type": "preference",
  "key": "language",
  "value": "Python",
  "is_pinned": true
}
```

---

### DELETE `/api/memories/{id}`

Delete a memory.

**Response (200 OK):**
```json
{
  "message": "Memory deleted"
}
```

---

### POST `/api/memories/{id}/pin`

Toggle memory pin status.

**Response (200 OK):**
```json
{
  "id": 1,
  "is_pinned": true
}
```

---

### GET `/api/memories/relevant`

Search for relevant memories.

**Query Parameters:**
- `q` (required): Search query
- `limit` (optional): Max results (default: 10)

**Response (200 OK):**
```json
{
  "memories": [
    {
      "id": 1,
      "key": "language",
      "value": "Python",
      "relevance_score": 0.85
    }
  ]
}
```

---

## 🎯 Intents

### GET `/api/intents`

List all intents.

**Response (200 OK):**
```json
{
  "intents": [
    {
      "id": 1,
      "name": "coding",
      "keywords": ["code", "debug", "function"],
      "priority": 50,
      "description": "Coding help",
      "is_enabled": true
    }
  ]
}
```

---

### POST `/api/intents`

Create new intent.

**Request:**
```json
{
  "name": "research",
  "keywords": ["research", "find", "search"],
  "priority": 40,
  "description": "Research tasks",
  "is_enabled": true
}
```

**Response (201 Created):**
```json
{
  "id": 2,
  "name": "research",
  ...
}
```

---

### PUT `/api/intents/{id}`

Update existing intent.

**Request:**
```json
{
  "keywords": ["research", "find", "search", "lookup"],
  "priority": 45
}
```

**Response (200 OK):**
```json
{
  "id": 2,
  "name": "research",
  "keywords": ["research", "find", "search", "lookup"],
  "priority": 45
}
```

---

### DELETE `/api/intents/{id}`

Delete an intent.

**Response (200 OK):**
```json
{
  "message": "Intent deleted"
}
```

---

### POST `/api/intents/{id}/toggle`

Enable or disable an intent.

**Response (200 OK):**
```json
{
  "id": 1,
  "is_enabled": false
}
```

---

## 🔀 Routing

### GET `/api/routing`

Get all routing preferences (intent → provider mappings).

**Response (200 OK):**
```json
{
  "rules": [
    {
      "intent": "coding",
      "provider_id": 1,
      "provider_name": "anthropic-sonnet"
    }
  ]
}
```

---

### POST `/api/routing`

Create routing rule.

**Request:**
```json
{
  "intent": "coding",
  "provider_id": 1
}
```

**Response (201 Created):**
```json
{
  "intent": "coding",
  "provider_id": 1
}
```

---

### DELETE `/api/routing/{intent}`

Delete routing rule for an intent.

**Response (200 OK):**
```json
{
  "message": "Routing rule deleted"
}
```

---

## 🤖 AI Providers

### GET `/api/providers`

List all AI providers.

**Response (200 OK):**
```json
{
  "providers": [
    {
      "id": 1,
      "provider_id": "anthropic-sonnet",
      "type": "anthropic",
      "model": "claude-sonnet-4.5",
      "is_enabled": true,
      "created_at": "2025-12-28T10:00:00Z"
    }
  ]
}
```

---

### POST `/api/providers`

Add new AI provider.

**Request:**
```json
{
  "provider_id": "openai-gpt4",
  "type": "openai",
  "model": "gpt-4",
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "is_enabled": true
}
```

**Response (201 Created):**
```json
{
  "id": 2,
  "provider_id": "openai-gpt4",
  ...
}
```

---

### PUT `/api/providers/{id}`

Update provider configuration.

**Request:**
```json
{
  "model": "gpt-4-turbo",
  "is_enabled": false
}
```

**Response (200 OK):**
```json
{
  "id": 2,
  "model": "gpt-4-turbo",
  "is_enabled": false
}
```

---

### DELETE `/api/providers/{id}`

Remove provider.

**Response (200 OK):**
```json
{
  "message": "Provider deleted"
}
```

---

### GET `/api/providers/health`

Get health summary for all providers.

**Response (200 OK):**
```json
{
  "providers": [
    {
      "provider_id": "anthropic-sonnet",
      "status": "healthy",
      "success_rate": 0.98,
      "avg_latency_ms": 1234,
      "total_requests": 150,
      "circuit_breaker_state": "closed",
      "last_request": "2025-12-28T10:30:00Z"
    }
  ]
}
```

---

## 🎭 Modes

### GET `/api/mode`

Get current user mode.

**Response (200 OK):**
```json
{
  "mode": "work"
}
```

---

### POST `/api/mode`

Set user mode.

**Request:**
```json
{
  "mode": "personal"
}
```

**Response (200 OK):**
```json
{
  "mode": "personal"
}
```

---

### GET `/api/mode/settings/{mode}`

Get mode-specific settings.

**Path Parameters:**
- `mode`: `work` or `personal`

**Response (200 OK):**
```json
{
  "mode": "work",
  "system_prompt_override": "You are a professional assistant...",
  "preferred_provider_id": 1
}
```

---

### POST `/api/mode/settings/{mode}`

Update mode settings.

**Request:**
```json
{
  "system_prompt_override": "New prompt",
  "preferred_provider_id": 2
}
```

**Response (200 OK):**
```json
{
  "message": "Mode settings updated"
}
```

---

### GET `/api/mode/work/subtab/{subtab}`

Get work subtab configuration.

**Path Parameters:**
- `subtab`: `conversation`, `code`, or `email`

**Response (200 OK):**
```json
{
  "subtab": "code",
  "config": {
    "language": "python",
    "framework": "flask",
    "additional_context": "Using SQLAlchemy"
  }
}
```

---

### POST `/api/mode/work/subtab/{subtab}`

Update work subtab configuration.

**Request:**
```json
{
  "language": "javascript",
  "framework": "svelte"
}
```

**Response (200 OK):**
```json
{
  "message": "Subtab configuration updated"
}
```

---

## 📅 Microsoft 365

### GET `/api/m365/auth/url`

Get M365 OAuth authorization URL.

**Response (200 OK):**
```json
{
  "auth_url": "https://login.microsoftonline.com/..."
}
```

---

### GET `/api/m365/auth/callback`

Handle OAuth callback (redirect endpoint).

**Query Parameters:**
- `code`: Authorization code from Microsoft

**Response:** Redirects to frontend with success/error

---

### GET `/api/m365/status`

Check M365 connection status.

**Response (200 OK):**
```json
{
  "connected": true,
  "expires_at": "2025-12-29T10:00:00Z",
  "scopes": ["Calendars.ReadWrite", "Mail.ReadWrite"]
}
```

---

### POST `/api/m365/disconnect`

Disconnect M365 account.

**Response (200 OK):**
```json
{
  "message": "M365 account disconnected"
}
```

---

## ✅ Confirmations

### GET `/api/confirmations/pending`

Get pending approval requests.

**Response (200 OK):**
```json
{
  "confirmations": [
    {
      "id": 1,
      "action_id": 10,
      "action_type": "calendar_create",
      "parameters": {
        "subject": "Team Meeting",
        "start": "2025-12-29T14:00:00Z"
      },
      "expires_at": "2025-12-28T11:00:00Z"
    }
  ]
}
```

---

### POST `/api/confirmations/{id}/approve`

Approve pending action.

**Response (200 OK):**
```json
{
  "message": "Action approved",
  "result": {
    "event_id": "abc123",
    "web_link": "https://..."
  }
}
```

---

### POST `/api/confirmations/{id}/reject`

Reject pending action.

**Request:**
```json
{
  "reason": "Not the right time"
}
```

**Response (200 OK):**
```json
{
  "message": "Action rejected"
}
```

---

## ⚙️ Settings

### GET `/api/settings/system-prompt`

Get system prompt configuration.

**Response (200 OK):**
```json
{
  "persona_name": "THEO",
  "tone": "professional",
  "style_rules": "Concise, no em dashes",
  "custom_instructions": "..."
}
```

---

### POST `/api/settings/system-prompt`

Update system prompt configuration.

**Request:**
```json
{
  "persona_name": "THEO",
  "tone": "conversational",
  "style_rules": "Be brief",
  "custom_instructions": "Use examples"
}
```

**Response (200 OK):**
```json
{
  "message": "System prompt updated"
}
```

---

### GET `/api/settings/debug`

Get debug mode status.

**Response (200 OK):**
```json
{
  "enabled": false
}
```

---

### POST `/api/settings/debug`

Toggle debug mode.

**Request:**
```json
{
  "enabled": true
}
```

**Response (200 OK):**
```json
{
  "enabled": true
}
```

---

## 🏥 Health

### GET `/health`

Basic health check (no auth required).

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2025-12-28T10:00:00Z"
}
```

---

### GET `/api/health`

API health check (no auth required).

**Response (200 OK):**
```json
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0"
}
```

---

### GET `/api/health/overview`

Comprehensive health overview.

**Response (200 OK):**
```json
{
  "ai_providers": {...},
  "m365_status": {...},
  "service_providers": {...},
  "database": "healthy",
  "uptime_seconds": 86400
}
```

---

## 📊 Error Responses

All error responses follow this format:

```json
{
  "error": "Error message",
  "details": "Optional additional details"
}
```

**Common HTTP Status Codes:**
- `200 OK` - Success
- `201 Created` - Resource created
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Authentication required or invalid
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource doesn't exist
- `409 Conflict` - Resource conflict (e.g., duplicate)
- `500 Internal Server Error` - Server error

---

## 🔗 Webhooks & Callbacks

Currently, THEO doesn't support webhooks, but M365 OAuth uses a callback endpoint:

**Callback URL**: `/api/m365/auth/callback`

Configure this in Azure AD App Registration.

---

## 📝 Rate Limiting

Currently, THEO does not implement rate limiting. For production deployments, consider adding rate limiting middleware.

---

## 🔒 Security

All authenticated endpoints require:

```
Authorization: Bearer {token}
```

Tokens expire after 7 days. After expiration, users must re-authenticate.

---

**Last Updated**: December 28, 2025

For implementation details, see [[Architecture]] documentation.
