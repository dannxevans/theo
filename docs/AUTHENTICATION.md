# THEO Authentication System

## Overview

THEO now includes a simple, secure authentication system designed for single-user deployments. The system protects the application behind a login screen while maintaining ease of use for personal AI assistant scenarios.

## Features

- **Login/Logout**: Secure session-based authentication
- **Password Management**: Change password functionality in Settings
- **Default Admin Account**: Pre-configured `admin` user for first-time setup
- **Password Reset**: Command-line utility for recovering lost passwords
- **7-Day Sessions**: Authentication tokens valid for 7 days
- **Secure Password Hashing**: SHA-256 with random salt

## Default Credentials

On first startup, THEO creates a default admin account:

**Username**: `admin`
**Password**: `admin`

⚠️ **Important**: Change the default password immediately after first login via Settings → Account!

## How It Works

### Database Schema

Two new tables support authentication:

**`users` table**:
- `id` (primary key)
- `username` (unique)
- `password_hash` (salted SHA-256)
- `is_admin` (boolean)
- `is_enabled` (boolean)
- Timestamps

**`auth_sessions` table**:
- `id` (session token, primary key)
- `user_id` (foreign key to users)
- `created_at`
- `expires_at`

### Authentication Flow

1. **Login** (`POST /api/auth/login`):
   - User submits username/password
   - Server verifies credentials
   - Server generates secure session token
   - Token stored in browser localStorage
   - Token valid for 7 days

2. **Session Verification** (`GET /api/auth/verify`):
   - Client sends token in `Authorization: Bearer <token>` header
   - Server validates token and expiration
   - Returns user info if valid

3. **Logout** (`POST /api/auth/logout`):
   - Client sends token
   - Server deletes session from database
   - Client clears localStorage

### Password Security

Passwords are hashed using SHA-256 with a random 16-byte salt:

```
salt:hash = random_16_bytes:sha256(password + salt)
```

Example: `a1b2c3d4e5f6...xyz:9f8e7d6c5b4a...`

## API Endpoints

### POST /api/auth/login
Login endpoint.

**Request**:
```json
{
  "username": "admin",
  "password": "admin"
}
```

**Response** (200 OK):
```json
{
  "token": "abc123xyz...",
  "user": {
    "id": 1,
    "username": "admin",
    "is_admin": true
  }
}
```

**Errors**:
- 400: Missing username/password
- 401: Invalid credentials or account disabled

---

### POST /api/auth/logout
Logout endpoint.

**Headers**:
```
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "status": "ok"
}
```

---

### GET /api/auth/verify
Verify session validity.

**Headers**:
```
Authorization: Bearer <token>
```

**Response** (200 OK):
```json
{
  "valid": true,
  "user": {
    "id": 1,
    "username": "admin",
    "is_admin": true
  }
}
```

**Response** (invalid session):
```json
{
  "valid": false
}
```

---

### POST /api/auth/change-password
Change user password.

**Headers**:
```
Authorization: Bearer <token>
```

**Request**:
```json
{
  "current_password": "admin",
  "new_password": "my-secure-password"
}
```

**Response** (200 OK):
```json
{
  "status": "ok"
}
```

**Errors**:
- 400: Missing fields or password too short (min 4 chars)
- 401: Current password incorrect or invalid session

## Password Reset Utility

If you forget your password and can't log in, use the command-line password reset utility:

### Usage

```bash
cd backend
source venv/bin/activate  # If using virtual environment
python reset_password.py <username> <new_password>
```

### Example

```bash
# Reset admin password to "mynewpassword"
python reset_password.py admin mynewpassword
```

### How It Works

The script:
1. Connects directly to the SQLite database
2. Looks up the user by username
3. Hashes the new password with a fresh salt
4. Updates the user's password_hash in the database
5. Confirms the reset was successful

### Requirements

- Password must be at least 4 characters
- You must have access to the backend directory
- The database file must be accessible

### Output

```
✅ Password reset successfully for user 'admin'
   You can now log in with the new password.
```

## Frontend Components

### Login Component

Located at: `frontend/src/components/Login.svelte`

Features:
- Clean, gradient background with centered login box
- Username/password inputs
- Error message display
- Responsive mobile design
- Auto-stores auth token in localStorage

### Account Settings Tab

Located in: `frontend/src/components/Settings.svelte` (Account tab)

Features:
- **Change Password Section**:
  - Current password field
  - New password field
  - Confirm password field
  - Validation (min 4 chars, passwords must match)
  - Success/error messages

### App Integration

The main `App.svelte` component:
- Checks authentication on mount using `verifySession()`
- Shows Login component if not authenticated
- Shows main app (Chat/Settings) if authenticated
- Adds Logout button to header
- Clears session on logout

## Security Considerations

### Current Implementation (Single-User Focus)

✅ **Good for**:
- Personal deployments
- Single-user scenarios
- Internal/private networks
- Self-hosted environments

⚠️ **Limitations**:
- SHA-256 is fast (consider bcrypt/argon2 for multi-user)
- No rate limiting on login attempts
- No password complexity requirements (min 4 chars only)
- Session tokens never refreshed (7-day fixed expiration)
- No CSRF protection
- No account lockout mechanism

### Recommendations for Production

If deploying publicly or for multiple users, consider:

1. **Stronger Password Hashing**: Use bcrypt or argon2
2. **Rate Limiting**: Limit login attempts (e.g., 5 per minute)
3. **Password Requirements**: Enforce complexity (uppercase, numbers, symbols)
4. **Session Refresh**: Implement rolling session expiration
5. **HTTPS Only**: Always use HTTPS in production
6. **CSRF Tokens**: Add CSRF protection for state-changing operations
7. **Account Lockout**: Temporarily lock accounts after failed login attempts
8. **Audit Logging**: Log authentication events
9. **2FA**: Consider two-factor authentication

## Usage Guide

### First-Time Setup

1. Start THEO application
2. Login screen appears
3. Enter default credentials:
   - Username: `admin`
   - Password: `admin`
4. Navigate to Settings → Account tab
5. Change password to something secure
6. (Optional) Disable admin account after creating your own credentials

### Changing Your Password

1. Navigate to **Settings** → **Account**
2. Enter your current password
3. Enter new password (min 4 characters)
4. Confirm new password
5. Click "Change Password"

### Resetting a Forgotten Password

If you forget your password:

1. SSH into your server (or access the backend directory locally)
2. Navigate to the backend directory
3. Run the password reset script:
   ```bash
   cd backend
   source venv/bin/activate  # If using venv
   python reset_password.py admin YourNewPassword
   ```
4. Log in with the new password

## Deployment Notes

### Environment Variables

No additional environment variables required. Authentication uses the same SQLite database as the rest of THEO.

### Database Migration

The authentication tables are created automatically on first startup. No manual migration needed.

### AWS ECS Deployment

Authentication works seamlessly with the S3 database backup system:
- User accounts persist across deployments
- Session tokens remain valid after container restarts (as long as database is restored)

### Backing Up User Data

User accounts are stored in the same `theo.db` SQLite database, so they're automatically included in:
- S3 backups (if configured)
- Local database backups
- EFS persistence (if using EFS instead of S3)

## Troubleshooting

### "Invalid credentials" even with correct password

- Check that the user account exists and is enabled
- Verify the database wasn't reset (losing user accounts)
- Check backend logs for authentication errors

### Session expires unexpectedly

- Sessions last 7 days
- Check system time on server (session expiration is UTC-based)
- Verify the `auth_sessions` table has the correct `expires_at` value

### Can't login after deployment

- Ensure database persistence is working (S3 backups or EFS)
- Check if database was reset to defaults
- Verify `users` table contains your account

### Forgot password

Use the password reset utility:

```bash
cd backend
source venv/bin/activate
python reset_password.py admin YourNewPassword
```

This directly updates the password in the database without needing to log in.

## Code References

### Backend

- **Authentication module**: `backend/auth.py`
- **Password reset utility**: `backend/reset_password.py`
- **User database methods**: `backend/core/memory.py` (authentication API)
- **API endpoints**: `backend/app.py` (authentication endpoints)

### Frontend

- **Login component**: `frontend/src/components/Login.svelte`
- **Account settings**: `frontend/src/components/Settings.svelte` (Account tab)
- **API functions**: `frontend/src/lib/api.js` (lines 573-668)
- **App integration**: `frontend/src/App.svelte` (authentication check and routing)

## Future Enhancements

Potential improvements for future versions:

- [ ] Multi-user support with user management UI
- [ ] Stronger password hashing (bcrypt/argon2)
- [ ] Email-based password reset
- [ ] Two-factor authentication (2FA)
- [ ] Role-based access control (RBAC)
- [ ] Session activity log
- [ ] Remember me checkbox (30-day sessions)
- [ ] Password complexity requirements
- [ ] Account lockout after failed attempts
- [ ] Rate limiting on authentication endpoints
