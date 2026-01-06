"""
Folder routes.

Provides folder management endpoints for organizing sessions including:
- Listing folders
- Creating custom folders
- Renaming and deleting folders
- Moving sessions between folders
- Archiving sessions
- Folder state management (collapsed/expanded)
"""

from flask import Blueprint, jsonify, request
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from auth.password import require_auth
import logging

folder_bp = Blueprint('folders', __name__, url_prefix='/api')

logger = logging.getLogger(__name__)


@folder_bp.route("/folders", methods=["GET"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def get_folders():
    """
    Get all folders for the current user.
    Archive folder is always first in the list.

    Returns:
        List of folder objects with id, name, user_id, is_system, sort_order, collapsed
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token (set by require_auth decorator)
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    folders = memory.get_folders(user_id)
    return jsonify(folders)


@folder_bp.route("/folders", methods=["POST"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def create_folder():
    """
    Create a new custom folder.

    Request body:
        {
            "name": "Folder name (max 100 chars)"
        }

    Returns:
        Created folder object or error
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    data = request.get_json()
    name = data.get('name')

    # Validate name
    if not name:
        return jsonify({"error": "Folder name is required"}), 400

    if len(name) > 100:
        return jsonify({"error": "Folder name must be 100 characters or less"}), 400

    # Create folder
    folder = memory.create_folder(user_id, name)

    if folder:
        return jsonify(folder), 201
    else:
        return jsonify({"error": "Failed to create folder. Name may already exist."}), 400


@folder_bp.route("/folders/<int:folder_id>", methods=["PUT"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def update_folder(folder_id):
    """
    Update folder properties (rename or toggle collapsed state).

    Request body (one of):
        { "name": "New name" }
        { "collapsed": true }

    Returns:
        Success status
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    data = request.get_json()

    # Handle rename
    if 'name' in data:
        new_name = data['name']

        if not new_name or len(new_name) > 100:
            return jsonify({"error": "Invalid folder name"}), 400

        success = memory.rename_folder(folder_id, user_id, new_name)

        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to rename folder. It may be a system folder or not found."}), 400

    # Handle collapsed state
    elif 'collapsed' in data:
        collapsed = data['collapsed']

        if not isinstance(collapsed, bool):
            return jsonify({"error": "Collapsed must be a boolean"}), 400

        success = memory.update_folder_collapsed(folder_id, user_id, collapsed)

        if success:
            return jsonify({"success": True})
        else:
            return jsonify({"error": "Failed to update folder state"}), 400

    else:
        return jsonify({"error": "No valid update property provided"}), 400


@folder_bp.route("/folders/<int:folder_id>", methods=["DELETE"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def delete_folder(folder_id):
    """
    Delete a custom folder.
    System folders (Archive) cannot be deleted.
    Sessions in the folder will be moved to unfiled.

    Returns:
        Success status
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    success = memory.delete_folder(folder_id, user_id)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to delete folder. It may be a system folder or not found."}), 400


@folder_bp.route("/sessions/<session_id>/move", methods=["POST"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def move_session(session_id):
    """
    Move a session to a folder or to unfiled.

    Request body:
        {
            "folder_id": 123  // or null for unfiled
        }

    Returns:
        Success status
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    data = request.get_json()
    folder_id = data.get('folder_id')  # Can be None for unfiled

    success = memory.move_session_to_folder(session_id, folder_id, user_id)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to move session. Session or folder not found."}), 400


@folder_bp.route("/sessions/<session_id>/archive", methods=["POST"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def archive_session(session_id):
    """
    Move a session to the Archive folder.

    Returns:
        Success status
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    success = memory.archive_session(session_id, user_id)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to archive session"}), 400


@folder_bp.route("/folders/reorder", methods=["POST"])
@require_auth(lambda: __import__('core.memory').memory.MemoryStore(__import__('config').Config.DATABASE_URL))
def reorder_folders():
    """
    Update the sort order of custom folders.
    Archive folder always remains at the top.

    Request body:
        {
            "folder_order": [1, 3, 2]  // Array of folder IDs in desired order
        }

    Returns:
        Success status
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Get user_id from auth token
    user_id = normalize_user_id(getattr(request, 'user_id', DEFAULT_USER_ID))

    data = request.get_json()
    folder_order = data.get('folder_order', [])

    if not isinstance(folder_order, list):
        return jsonify({"error": "folder_order must be an array"}), 400

    success = memory.reorder_folders(user_id, folder_order)

    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to reorder folders"}), 400
