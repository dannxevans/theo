# Microsoft 365 Integration Guide

This guide covers the setup, configuration, and usage of THEO's Microsoft 365 integration for calendar and email operations.

---

## Overview

THEO integrates with Microsoft 365 via the Microsoft Graph API v1.0, providing:
- **Calendar Management**: Read, create, update, and delete calendar events
- **Email Operations**: Read emails, compose with LLM assistance, send, and reply
- **OAuth 2.0 Authentication**: Secure token-based authentication with automatic refresh
- **Two-Step Approval**: Confirm actions before execution

---

## Prerequisites

### 1. Azure AD App Registration

You need to register an application in Azure Active Directory:

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **New registration**
4. Configure the application:
   - **Name**: THEO M365 Integration
   - **Supported account types**: "Accounts in this organizational directory only"
   - **Redirect URI**:
     - Type: Web
     - URI: `http://localhost:1066/api/m365/auth/callback` (for development)
     - URI: `https://your-domain.com/api/m365/auth/callback` (for production)

5. Click **Register**

### 2. API Permissions

After registration, configure API permissions:

1. Go to **API permissions** in your app
2. Click **Add a permission** → **Microsoft Graph** → **Delegated permissions**
3. Add the following permissions:
   - `Calendars.ReadWrite` - Read and write calendar events
   - `Mail.ReadWrite` - Read and write mail
   - `Mail.Send` - Send mail as the user
   - `User.Read` - Read user profile (basic)
   - `offline_access` - Maintain access to data

4. Click **Add permissions**
5. Click **Grant admin consent** (if you're an admin)

### 3. Client Secret

Create a client secret for your application:

1. Go to **Certificates & secrets**
2. Click **New client secret**
3. Add a description and select expiration (recommendation: 24 months)
4. Click **Add**
5. **Copy the secret value immediately** (you won't be able to see it again)

### 4. Environment Variables

Set the following environment variables in your backend:

```bash
# Azure AD App Configuration
M365_CLIENT_ID=your-client-id
M365_CLIENT_SECRET=your-client-secret
M365_TENANT_ID=your-tenant-id  # Or "common" for multi-tenant
M365_REDIRECT_URI=http://localhost:1066/api/m365/auth/callback
```

For production, update the redirect URI to your domain.

---

## Setup in THEO

### 1. Connect Microsoft 365 Account

1. Log into THEO
2. Go to **Settings** → **Providers**
3. Find the **Microsoft 365** section
4. Click **Connect to Microsoft 365**
5. You'll be redirected to Microsoft login
6. Sign in with your M365 account
7. Grant the requested permissions
8. You'll be redirected back to THEO

The OAuth tokens will be automatically stored and refreshed.

### 2. Verify Connection

Check the connection status:
- Go to **Settings** → **Providers**
- You should see "Connected to Microsoft 365" with token expiration time
- Or use the API: `GET /api/m365/status`

---

## Calendar Features

### Reading Calendar Events

**Natural Language Examples:**
```
"What's on my calendar today?"
"Show me my meetings this week"
"Do I have any events tomorrow?"
"What meetings do I have on Friday?"
"Any flights on my calendar?"  # Smart travel detection
```

**Context-Aware Booking:**
THEO uses context detection to prevent false positives. Generic verbs like "add", "create", "make" require calendar-related context:

✅ Good:
```
"Add a meeting with John to my calendar at 3pm"
"Create a lunch appointment for tomorrow"
"Make a reminder in my diary for next week"
```

❌ Won't trigger (requires context):
```
"Add this feature to the codebase"  # No calendar context
"Create a new function"              # No calendar context
```

### Creating Calendar Events

**Natural Language Examples:**
```
"Book a meeting with Sarah at 2pm tomorrow for 30 minutes"
"Schedule a call with the team on Friday at 10am"
"Add a lunch with Mike at the office on Monday at 12:30pm"
"Create an all-day event for the conference on Dec 15th"
```

**What THEO Captures:**
- Subject (meeting title)
- Start time (with smart parsing)
- End time (or duration)
- Location (if mentioned)
- Attendees (email addresses)
- Description/notes (if provided)

### Updating Calendar Events

```
"Move my 2pm meeting to 3pm"
"Change the location of tomorrow's standup to Conference Room B"
"Update the meeting subject to 'Q4 Planning Session'"
```

### Deleting Calendar Events

```
"Cancel my 3pm meeting today"
"Delete the team sync tomorrow"
"Remove the lunch appointment on Friday"
```

---

## Email Features

### Reading Emails

**Natural Language Examples:**
```
"Check my emails"
"Show me unread messages"
"What emails did I get today?"
"Search my inbox for messages from John"
"Find emails about the project proposal"
```

**Email Signature Stripping:**
THEO intelligently strips email signatures and footers using comprehensive pattern matching:
- Common sign-offs (Best regards, Kind regards, etc.)
- Mobile signatures (Sent from my iPhone)
- Legal disclaimers
- Company footers with contact info

### Composing Emails

**Natural Language to Email:**
```
"Send an email to john@example.com, I am confirming our meeting tomorrow at 2pm. Looking forward to discussing the project."
```

THEO will:
1. Generate an appropriate subject (e.g., "Meeting Confirmation")
2. Compose a professional email body
3. Sign it with your name (from memory)
4. Create a draft in your M365 account
5. Show you a preview with **Approve/Reject** buttons

**Draft Workflow:**
1. **Draft Created**: Email is saved to your M365 Drafts folder
2. **Review**: THEO displays the subject and body
3. **Approve**: Click approve → Email is sent, saved to Sent Items
4. **Reject**: Click reject → Draft is deleted

### Replying to Emails

```
"Reply to the last email from Sarah, tell her I'll review the document by EOD"
"Respond to john@example.com's message about the meeting"
```

THEO will:
- Find the original email
- Generate a contextual reply
- Include your signature
- Present for approval before sending

---

## Technical Details

### OAuth 2.0 Flow

1. **Authorization Request**: THEO redirects to Microsoft login
2. **User Consent**: User grants permissions
3. **Authorization Code**: Microsoft returns an auth code
4. **Token Exchange**: THEO exchanges code for access & refresh tokens
5. **Token Storage**: Tokens stored securely in database
6. **Automatic Refresh**: Access tokens refreshed before expiration

### Token Refresh

Tokens are automatically refreshed:
- Access tokens expire after ~60 minutes
- THEO checks expiration before each API call
- Refresh tokens valid for 90 days (default)
- No user interaction required for refresh

### API Capabilities

The M365 Provider supports these action types:

| Action Type | Description | Parameters |
|-------------|-------------|------------|
| `read_calendar` | Fetch events in date range | `start_date`, `end_date` |
| `create_calendar_event` | Create new event | `subject`, `start_time`, `end_time`, `location`, `attendees`, `description` |
| `update_calendar_event` | Modify existing event | `event_id`, updates |
| `delete_calendar_event` | Remove event | `event_id` |
| `read_email` | Read/search emails | `folder`, `query`, `max_results` |
| `send_email` | Send new email | `to`, `subject`, `body` |
| `reply_email` | Reply to email | `email_id`, `body` |
| `draft_email` | Create draft | `to`, `subject`, `body` |
| `send_draft_email` | Send draft | `draft_id` |
| `delete_draft_email` | Delete draft | `draft_id` |

---

## Confirmation System

All M365 actions require confirmation for safety:

### How It Works

1. **Action Proposed**: THEO identifies an action (e.g., send email)
2. **Confirmation Created**: Action stored with "pending" status
3. **User Notification**: Approval widget shown in UI
4. **User Decision**:
   - **Approve**: Action executed immediately
   - **Reject**: Action canceled, draft deleted (if applicable)
5. **Expiration**: Confirmations expire after 24 hours

### Confirmation Metadata

Each confirmation includes:
- **Action Type**: What will be executed
- **Parameters**: Action details (e.g., recipient, subject)
- **Message**: Human-readable description
- **Expires At**: When the confirmation becomes invalid

### API Endpoints

- `GET /api/confirmations/pending` - List pending confirmations
- `POST /api/confirmations/<id>/approve` - Approve action
- `POST /api/confirmations/<id>/reject` - Reject action

---

## Troubleshooting

### Connection Issues

**Problem**: "Failed to connect to Microsoft 365"

**Solutions**:
1. Check environment variables are set correctly
2. Verify redirect URI matches in Azure AD app
3. Ensure API permissions are granted
4. Check client secret hasn't expired

**Problem**: "Token expired"

**Solutions**:
1. THEO should auto-refresh - check logs for errors
2. Reconnect account via Settings → Providers
3. Check refresh token hasn't been revoked

### Permission Errors

**Problem**: "Access denied" or "Insufficient permissions"

**Solutions**:
1. Verify all required permissions are added in Azure AD
2. Ensure admin consent was granted
3. User must have appropriate M365 license

### Email Sending Issues

**Problem**: Email drafts created but not sent

**Solutions**:
1. Check confirmation was approved
2. Verify `saveToSentItems` is boolean (not string)
3. Check backend logs for errors
4. Ensure user has send permissions

**Problem**: Signatures not being stripped

**Solutions**:
1. Check email format (HTML vs plain text)
2. Signature patterns may need adjustment
3. Review `m365_provider.py` signature stripping patterns

### Calendar Booking Issues

**Problem**: Generic phrases triggering calendar booking

**Solutions**:
1. Ensure calendar context detection is enabled
2. Update `router.py` CALENDAR_CONTEXT words if needed
3. Use more specific phrases (e.g., "add to calendar" instead of "add")

---

## Advanced Configuration

### Custom Signature Patterns

To add custom signature patterns for stripping:

Edit `backend/actions/m365_provider.py`:

```python
signature_markers = [
    r'(?i)\n\s*(your custom pattern here)',
    # ... existing patterns
]
```

### Adjusting Token Refresh Timing

By default, tokens refresh 5 minutes before expiration. To adjust:

Edit `backend/actions/m365_provider.py`:

```python
def _ensure_token_valid(self):
    # Current: 5 minute buffer
    if datetime.utcnow() >= (self.expires_at - timedelta(minutes=5)):
        self._refresh_token()
```

### Calendar Context Words

To customize calendar detection context:

Edit `backend/core/router.py`:

```python
CALENDAR_CONTEXT = [
    "calendar", "diary", "schedule", "appointment", "meeting",
    # Add your custom context words
]
```

---

## Security Best Practices

### Production Deployment

1. **Use HTTPS**: Always use HTTPS for redirect URIs in production
2. **Rotate Secrets**: Regularly rotate client secrets
3. **Limit Permissions**: Only request necessary API permissions
4. **Monitor Access**: Review Azure AD sign-in logs
5. **Token Security**: Tokens encrypted in database (implement at application layer)

### User Privacy

- Tokens stored per-user in database
- No cross-user access to M365 data
- Users can disconnect at any time
- Action history logged for audit

---

## API Reference

### M365 Status

```bash
GET /api/m365/status

Response:
{
  "connected": true,
  "email": "user@example.com",
  "token_expires": "2025-12-27T15:30:00Z"
}
```

### Get OAuth URL

```bash
GET /api/m365/auth/url

Response:
{
  "auth_url": "https://login.microsoftonline.com/..."
}
```

### Disconnect Account

```bash
POST /api/m365/disconnect

Response:
{
  "success": true,
  "message": "Microsoft 365 account disconnected"
}
```

---

## Frequently Asked Questions

**Q: Can I use a personal Microsoft account?**
A: Yes, but you'll need to use "common" as the tenant ID in your Azure AD app configuration.

**Q: How long do tokens last?**
A: Access tokens expire after ~60 minutes. Refresh tokens last 90 days by default but are automatically refreshed.

**Q: Can I revoke access?**
A: Yes, either through THEO (Settings → Disconnect M365) or through your Microsoft account security settings.

**Q: Does THEO store my emails?**
A: No, THEO only stores OAuth tokens. Emails are read from M365 in real-time.

**Q: Can I use multiple M365 accounts?**
A: Currently, THEO supports one M365 account per user. Multi-account support is planned.

**Q: What happens if I reject a draft?**
A: The draft is immediately deleted from your M365 Drafts folder.

**Q: Are calendar events created immediately?**
A: No, all calendar operations require confirmation first for safety.

---

## Changelog

### December 27, 2024
- ✅ Fixed email compose routing (Issue #29)
- ✅ Fixed sent items not saving (Issue #24)
- ✅ Fixed calendar context detection (Issue #28)
- ✅ Enhanced signature stripping (Issues #30, #31)
- ✅ Added draft workflow with approval
- ✅ Implemented send_draft_email and delete_draft_email
- ✅ Fixed confirmation widget serialization

### December 26, 2024
- ✅ Added flight/travel detection (Issue #32)
- ✅ Enhanced email search capabilities
- ✅ Improved HTML to text conversion

### Earlier
- ✅ Initial M365 integration
- ✅ OAuth 2.0 implementation
- ✅ Calendar and email operations
- ✅ Automatic token refresh

---

## Support

For issues or questions:
1. Check the [Implementation Plan](IMPLEMENTATION_PLAN.md) for known issues
2. Review backend logs for error details
3. Verify Azure AD app configuration
4. Check Microsoft Graph API documentation: https://docs.microsoft.com/graph

---

**Last Updated**: December 27, 2024
**Author**: Danny Black
**Status**: Production Ready
