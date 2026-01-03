"""
Authentication module for THEO.

This module provides:
- Password hashing and verification
- Session token generation and management
- User initialization
- Authentication decorators for Flask routes
- API key generation and validation
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

# Import API key management functions
from .api_keys import (
    generate_api_key,
    hash_api_key,
    verify_api_key,
    validate_api_key_format,
    is_api_key_expired,
    is_api_key_revoked,
    is_api_key_valid
)

# Import M365 OAuth
from .m365_oauth import M365OAuth

__all__ = [
    'hash_password',
    'verify_password',
    'generate_session_token',
    'init_default_user',
    'require_auth',
    'generate_api_key',
    'hash_api_key',
    'verify_api_key',
    'validate_api_key_format',
    'is_api_key_expired',
    'is_api_key_revoked',
    'is_api_key_valid',
    'M365OAuth'
]
