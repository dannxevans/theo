"""
Authentication module for THEO.

This module provides:
- Password hashing and verification
- Session token generation and management
- User initialization
- Authentication decorators for Flask routes
- M365 OAuth integration
"""

# Import password and session management functions
from .password import (
    hash_password,
    verify_password,
    generate_session_token,
    init_default_user,
    require_auth
)

# Import M365 OAuth
from .m365_oauth import M365OAuth

__all__ = [
    'hash_password',
    'verify_password',
    'generate_session_token',
    'init_default_user',
    'require_auth',
    'M365OAuth'
]
