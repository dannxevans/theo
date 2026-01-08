"""
Authorization decorators for THEO API routes.

Provides role-based access control decorators to protect admin-only endpoints.
"""

from functools import wraps
from flask import request, jsonify


def require_admin(memory):
    """
    Decorator that requires authenticated user to be an administrator.

    IMPORTANT: This decorator MUST be used AFTER @require_auth decorator,
    as it relies on request.current_user being set by the auth middleware.

    Usage:
        from backend.auth.password import require_auth
        from backend.auth.decorators import require_admin

        @app.route('/api/users')
        @require_auth(memory)
        @require_admin(memory)
        def list_users():
            user = request.current_user  # Guaranteed to exist and be admin
            ...

    Args:
        memory: Memory store instance (for consistency with require_auth signature)

    Returns:
        Decorator function that:
        - Returns 401 if user not authenticated (missing current_user)
        - Returns 403 if user is not admin
        - Calls wrapped function if user is admin

    Example responses:
        401: {"error": "Authentication required"}
        403: {"error": "Admin access required"}
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check if user is authenticated (require_auth should have set this)
            if not hasattr(request, 'current_user') or request.current_user is None:
                return jsonify({"error": "Authentication required"}), 401

            # Check if user is admin (current_user is a dict)
            is_admin = request.current_user.get('is_admin', False) if isinstance(request.current_user, dict) else getattr(request.current_user, 'is_admin', False)

            if not is_admin:
                return jsonify({"error": "Admin access required"}), 403

            # User is authenticated and admin - proceed
            return f(*args, **kwargs)

        return decorated_function
    return decorator
