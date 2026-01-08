"""
User Management routes.

Provides admin endpoints for user CRUD operations and self-service profile access.
"""

from flask import Blueprint, jsonify, request
from auth import require_auth, hash_password
from auth.decorators import require_admin
from auth.password_utils import generate_random_password, validate_password_strength

user_mgmt_bp = Blueprint('user_management', __name__, url_prefix='/api')


def _get_memory():
    """Helper to get memory store instance."""
    from core.memory import MemoryStore
    from config import Config
    return MemoryStore(Config.DATABASE_URL)


@user_mgmt_bp.route("/users", methods=["GET"])
@require_auth(lambda: _get_memory())
@require_admin(lambda: _get_memory())
def list_users():
    """
    List all users (admin only).

    Query params:
        include_disabled: bool (default: false)

    Returns:
        {
            "users": [
                {
                    "id": 1,
                    "username": "admin",
                    "is_admin": true,
                    "is_enabled": true,
                    "created_at": "2025-01-01T00:00:00",
                    "updated_at": "2025-01-01T00:00:00",
                    "stats": {
                        "session_count": 2,
                        "api_key_count": 1,
                        "last_activity": "2025-01-08T10:00:00",
                        "memory_count": 45
                    }
                }
            ]
        }
    """
    memory = _get_memory()
    include_disabled = request.args.get('include_disabled', 'false').lower() == 'true'

    users = memory.list_all_users(include_disabled)

    users_data = []
    for user in users:
        stats = memory.get_user_activity_stats(user['id'])
        users_data.append({
            'id': user['id'],
            'username': user['username'],
            'name': user.get('name'),
            'email': user.get('email'),
            'is_admin': user['is_admin'],
            'is_enabled': user['is_enabled'],
            'created_at': user['created_at'].isoformat() if user.get('created_at') else None,
            'updated_at': user['updated_at'].isoformat() if user.get('updated_at') else None,
            'stats': {
                'session_count': stats['session_count'],
                'api_key_count': stats['api_key_count'],
                'last_activity': stats['last_activity'].isoformat() if stats.get('last_activity') else None,
                'memory_count': stats['memory_count']
            }
        })

    return jsonify({'users': users_data})


@user_mgmt_bp.route("/users", methods=["POST"])
@require_auth(lambda: _get_memory())
@require_admin(lambda: _get_memory())
def create_user():
    """
    Create new user (admin only).

    Generates random secure password and returns it (shown once).

    Request body:
        {
            "username": "newuser",
            "name": "John Doe",  (optional)
            "email": "john@example.com",  (optional)
            "is_admin": false  (optional, default: false)
        }

    Returns:
        {
            "user": {
                "id": 5,
                "username": "newuser",
                "name": "John Doe",
                "email": "john@example.com",
                "is_admin": false,
                "is_enabled": true,
                "created_at": "2025-01-08T10:00:00"
            },
            "password": "GeneratedP@ssw0rd!"  // ONLY returned once
        }

    Errors:
        400: Missing username
        409: Username already exists
    """
    memory = _get_memory()
    data = request.json

    if not data or 'username' not in data:
        return jsonify({'error': 'Username is required'}), 400

    username = data['username']
    name = data.get('name')
    email = data.get('email')
    is_admin = data.get('is_admin', False)

    # Check if username already exists
    existing = memory.get_user_by_username(username)
    if existing:
        return jsonify({'error': f"Username '{username}' already exists"}), 409

    # Generate random password
    password = generate_random_password()
    password_hash = hash_password(password)

    # Create user
    try:
        user_id = memory.create_user(username, password_hash, is_admin, name, email)
        user = memory.get_user_by_id(user_id)
    except Exception as e:
        return jsonify({'error': f'Failed to create user: {str(e)}'}), 500

    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user.get('name'),
            'email': user.get('email'),
            'is_admin': user['is_admin'],
            'is_enabled': user['is_enabled'],
            'created_at': user['created_at'].isoformat() if user.get('created_at') else None
        },
        'password': password  # ONLY shown once!
    }), 201


@user_mgmt_bp.route("/users/<int:user_id>", methods=["GET"])
@require_auth(lambda: _get_memory())
def get_user(user_id):
    """
    Get user details (admin or self).

    Authorization:
        - Admin can view any user
        - Non-admin can only view themselves

    Returns:
        {
            "user": {
                "id": 5,
                "username": "user",
                "is_admin": false,
                "is_enabled": true,
                "created_at": "...",
                "updated_at": "...",
                "stats": {...}
            }
        }

    Errors:
        403: Non-admin trying to view other user
        404: User not found
    """
    memory = _get_memory()

    # Authorization check
    if not request.current_user['is_admin'] and request.current_user['id'] != user_id:
        return jsonify({'error': 'You can only view your own profile'}), 403

    user = memory.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    stats = memory.get_user_activity_stats(user_id)

    return jsonify({
        'user': {
            'id': user['id'],
            'username': user['username'],
            'name': user.get('name'),
            'email': user.get('email'),
            'is_admin': user['is_admin'],
            'is_enabled': user['is_enabled'],
            'created_at': user['created_at'].isoformat() if user.get('created_at') else None,
            'updated_at': user['updated_at'].isoformat() if user.get('updated_at') else None,
            'stats': {
                'session_count': stats['session_count'],
                'api_key_count': stats['api_key_count'],
                'last_activity': stats['last_activity'].isoformat() if stats.get('last_activity') else None,
                'memory_count': stats['memory_count']
            }
        }
    })


@user_mgmt_bp.route("/users/<int:user_id>", methods=["PUT"])
@require_auth(lambda: _get_memory())
@require_admin(lambda: _get_memory())
def update_user(user_id):
    """
    Update user (admin only).

    Request body (all fields optional):
        {
            "username": "newname",
            "name": "John Doe",
            "email": "john@example.com",
            "is_admin": true,
            "is_enabled": false
        }

    Safeguards:
        - Cannot deactivate yourself
        - Cannot demote yourself if you're the last admin
        - Cannot demote last admin

    Returns:
        {
            "user": {...}
        }

    Errors:
        400: Invalid update / safeguard violation
        404: User not found
        409: Username conflict
    """
    memory = _get_memory()
    data = request.json

    if not data:
        return jsonify({'error': 'No update data provided'}), 400

    # Safeguard: Cannot deactivate yourself
    if 'is_enabled' in data and not data['is_enabled']:
        if user_id == request.current_user['id']:
            return jsonify({'error': 'You cannot deactivate your own account'}), 400

    # Safeguard: Cannot demote last admin
    if 'is_admin' in data and not data['is_admin']:
        user = memory.get_user_by_id(user_id)
        if user and user['is_admin']:
            # This user is currently admin and being demoted
            admin_count = memory.count_admins()
            if admin_count <= 1:
                return jsonify({'error': 'Cannot demote the last admin user'}), 400

    try:
        updated_user = memory.update_user(user_id, data)
    except ValueError as e:
        error_msg = str(e)
        if 'not found' in error_msg.lower():
            return jsonify({'error': error_msg}), 404
        elif 'already exists' in error_msg.lower():
            return jsonify({'error': error_msg}), 409
        else:
            return jsonify({'error': error_msg}), 400

    stats = memory.get_user_activity_stats(user_id)

    return jsonify({
        'user': {
            'id': updated_user['id'],
            'username': updated_user['username'],
            'name': updated_user.get('name'),
            'email': updated_user.get('email'),
            'is_admin': updated_user['is_admin'],
            'is_enabled': updated_user['is_enabled'],
            'created_at': updated_user['created_at'].isoformat() if updated_user.get('created_at') else None,
            'updated_at': updated_user['updated_at'].isoformat() if updated_user.get('updated_at') else None,
            'stats': {
                'session_count': stats['session_count'],
                'api_key_count': stats['api_key_count'],
                'last_activity': stats['last_activity'].isoformat() if stats.get('last_activity') else None,
                'memory_count': stats['memory_count']
            }
        }
    })


@user_mgmt_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@require_auth(lambda: _get_memory())
@require_admin(lambda: _get_memory())
def reset_password(user_id):
    """
    Admin reset user password.

    Generates new random password and returns it (shown once).
    Invalidates all user sessions for security.

    Returns:
        {
            "message": "Password reset successfully",
            "password": "NewGeneratedP@ss123!"  // ONLY shown once
        }

    Errors:
        404: User not found
    """
    memory = _get_memory()

    user = memory.get_user_by_id(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Generate new password
    new_password = generate_random_password()
    new_password_hash = hash_password(new_password)

    # Reset password and invalidate sessions
    try:
        memory.reset_user_password(user_id, new_password_hash)
    except Exception as e:
        return jsonify({'error': f'Failed to reset password: {str(e)}'}), 500

    return jsonify({
        'message': 'Password reset successfully',
        'password': new_password  # ONLY shown once!
    })


@user_mgmt_bp.route("/users/me", methods=["GET"])
@require_auth(lambda: _get_memory())
def get_current_user():
    """
    Get current user profile (self-service).

    Returns:
        {
            "user": {
                "id": 3,
                "username": "john",
                "is_admin": false,
                "is_enabled": true,
                "created_at": "...",
                "stats": {...}
            }
        }
    """
    memory = _get_memory()
    user_id = request.current_user['id']

    stats = memory.get_user_activity_stats(user_id)

    return jsonify({
        'user': {
            'id': request.current_user['id'],
            'username': request.current_user['username'],
            'is_admin': request.current_user['is_admin'],
            'is_enabled': request.current_user['is_enabled'],
            'created_at': request.current_user['created_at'].isoformat() if request.current_user.get('created_at') else None,
            'stats': {
                'session_count': stats['session_count'],
                'api_key_count': stats['api_key_count'],
                'last_activity': stats['last_activity'].isoformat() if stats.get('last_activity') else None,
                'memory_count': stats['memory_count']
            }
        }
    })
