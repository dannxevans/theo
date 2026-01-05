"""
Database Audit routes.

Provides API endpoints for the database audit feature:
- List all sessions with filtering and pagination
- View conversation turns for a specific session
- Get audit statistics

All endpoints require admin authentication.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import sqlite3
import json
from auth.password import require_auth

audit_bp = Blueprint('audit', __name__, url_prefix='/api/audit')


def get_db_path(memory):
    """
    Extract database file path from MemoryStore's SQLAlchemy engine URL.

    Args:
        memory: MemoryStore instance

    Returns:
        str: Path to SQLite database file
    """
    db_url = str(memory.engine.url)
    # Extract path from sqlite:///path/to/db.db
    if db_url.startswith('sqlite:///'):
        return db_url.replace('sqlite:///', '')
    else:
        # Fallback for relative paths
        return db_url.split('sqlite:///')[-1]


def is_admin(memory, user):
    """
    Check if user has admin privileges.

    Args:
        memory: MemoryStore instance
        user: User dict from database

    Returns:
        True if user is admin, False otherwise
    """
    return user and user.get('is_admin', False)


@audit_bp.route("/sessions", methods=["GET"])
@require_auth(lambda: __import__('app').memory)
def get_audit_sessions():
    """
    Get all sessions with optional filtering and pagination.

    Query params:
        - limit: Number of sessions to return (default 50, max 500)
        - offset: Number of sessions to skip (default 0)
        - mode: Filter by mode ("work" or "personal")
        - start_date: Filter sessions created after this date (ISO format)
        - end_date: Filter sessions created before this date (ISO format)
        - user_id: Filter by user ID

    Returns:
        JSON with sessions list, total count, and pagination info

    Requires: Admin authentication
    """
    from app import memory

    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    # Get pagination parameters
    try:
        limit = min(int(request.args.get("limit", 50)), 500)
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "Invalid pagination parameters"}), 400

    # Get filter parameters
    mode = request.args.get("mode")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    user_id_filter = request.args.get("user_id")

    # Validate mode
    if mode and mode not in ["work", "personal"]:
        return jsonify({"error": "Invalid mode - must be 'work' or 'personal'"}), 400

    # Validate dates
    try:
        if start_date:
            datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        if end_date:
            datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    except ValueError:
        return jsonify({"error": "Invalid date format - use ISO format"}), 400

    # Build query
    db_path = get_db_path(memory)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Build WHERE clause
    where_clauses = []
    params = []

    if mode:
        where_clauses.append("s.mode = ?")
        params.append(mode)

    if start_date:
        where_clauses.append("s.created_at >= ?")
        params.append(start_date)

    if end_date:
        where_clauses.append("s.created_at <= ?")
        params.append(end_date)

    if user_id_filter:
        where_clauses.append("s.user_id = ?")
        params.append(int(user_id_filter))

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM sessions s WHERE {where_sql}"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get sessions with turn counts
    query = f"""
        SELECT
            s.id,
            s.title,
            s.mode,
            s.classification,
            s.user_id,
            s.created_at,
            s.updated_at,
            COUNT(t.id) as turn_count
        FROM sessions s
        LEFT JOIN turns t ON s.id = t.session_id
        WHERE {where_sql}
        GROUP BY s.id
        ORDER BY s.created_at DESC
        LIMIT ? OFFSET ?
    """

    cursor.execute(query, params + [limit, offset])
    rows = cursor.fetchall()

    sessions = []
    for row in rows:
        sessions.append({
            "id": row["id"],
            "title": row["title"],
            "mode": row["mode"],
            "classification": row["classification"],
            "user_id": row["user_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "turn_count": row["turn_count"]
        })

    conn.close()

    return jsonify({
        "sessions": sessions,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }), 200


@audit_bp.route("/sessions/<session_id>/turns", methods=["GET"])
@require_auth(lambda: __import__('app').memory)
def get_session_turns(session_id):
    """
    Get all turns for a specific session with optional filtering.

    Path params:
        - session_id: The session ID to get turns for

    Query params:
        - limit: Number of turns to return (default 100, max 1000)
        - offset: Number of turns to skip (default 0)
        - role: Filter by role ("user" or "assistant")
        - provider_id: Filter by provider ID
        - model: Filter by model name

    Returns:
        JSON with turns list, total count, and pagination info

    Requires: Admin authentication
    """
    from app import memory

    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    # Check if session exists and get its details
    db_path = get_db_path(memory)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, mode, created_at
        FROM sessions
        WHERE id = ?
    """, (session_id,))
    session_row = cursor.fetchone()

    if not session_row:
        conn.close()
        return jsonify({"error": "Session not found"}), 404

    session_info = {
        "id": session_row["id"],
        "title": session_row["title"],
        "mode": session_row["mode"]
    }

    # Get pagination parameters
    try:
        limit = min(int(request.args.get("limit", 100)), 1000)
        offset = int(request.args.get("offset", 0))
    except ValueError:
        return jsonify({"error": "Invalid pagination parameters"}), 400

    # Get filter parameters
    role = request.args.get("role")
    provider_id = request.args.get("provider_id")
    model = request.args.get("model")

    # Validate role
    if role and role not in ["user", "assistant"]:
        conn.close()
        return jsonify({"error": "Invalid role - must be 'user' or 'assistant'"}), 400

    # Build WHERE clause
    where_clauses = ["session_id = ?"]
    params = [session_id]

    if role:
        where_clauses.append("role = ?")
        params.append(role)

    if provider_id:
        where_clauses.append("provider_id = ?")
        params.append(provider_id)

    if model:
        where_clauses.append("model = ?")
        params.append(model)

    where_sql = " AND ".join(where_clauses)

    # Get total count
    count_query = f"SELECT COUNT(*) as total FROM turns WHERE {where_sql}"
    cursor.execute(count_query, params)
    total = cursor.fetchone()[0]

    # Get turns
    query = f"""
        SELECT
            id,
            session_id,
            role,
            content,
            created_at,
            provider_id,
            model,
            intent,
            metadata,
            planning_metadata,
            routine_name,
            routine_actions,
            full_request_context
        FROM turns
        WHERE {where_sql}
        ORDER BY created_at ASC
        LIMIT ? OFFSET ?
    """

    cursor.execute(query, params + [limit, offset])
    rows = cursor.fetchall()

    turns = []
    for row in rows:
        # Parse JSON fields
        metadata = None
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except json.JSONDecodeError:
                metadata = None

        planning_metadata = None
        if row["planning_metadata"]:
            try:
                planning_metadata = json.loads(row["planning_metadata"])
            except json.JSONDecodeError:
                planning_metadata = None

        routine_actions = None
        if row["routine_actions"]:
            try:
                routine_actions = json.loads(row["routine_actions"])
            except json.JSONDecodeError:
                routine_actions = None

        full_request_context = None
        if row["full_request_context"]:
            try:
                full_request_context = json.loads(row["full_request_context"])
            except json.JSONDecodeError:
                full_request_context = None

        turns.append({
            "id": row["id"],
            "session_id": row["session_id"],
            "role": row["role"],
            "content": row["content"],
            "created_at": row["created_at"],
            "provider_id": row["provider_id"],
            "model": row["model"],
            "intent": row["intent"],
            "metadata": metadata,
            "planning_metadata": planning_metadata,
            "routine_name": row["routine_name"],
            "routine_actions": routine_actions,
            "full_request_context": full_request_context
        })

    conn.close()

    return jsonify({
        "session": session_info,
        "turns": turns,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total
    }), 200


@audit_bp.route("/stats", methods=["GET"])
@require_auth(lambda: __import__('app').memory)
def get_audit_stats():
    """
    Get overall database audit statistics.

    Returns:
        JSON with statistics about sessions, turns, providers, and models

    Requires: Admin authentication
    """
    from app import memory

    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    db_path = get_db_path(memory)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get total sessions
    cursor.execute("SELECT COUNT(*) as total FROM sessions")
    total_sessions = cursor.fetchone()[0]

    # Get total turns
    cursor.execute("SELECT COUNT(*) as total FROM turns")
    total_turns = cursor.fetchone()[0]

    # Get sessions by mode
    cursor.execute("""
        SELECT mode, COUNT(*) as count
        FROM sessions
        GROUP BY mode
    """)
    sessions_by_mode = {row["mode"]: row["count"] for row in cursor.fetchall()}

    # Get turns by role
    cursor.execute("""
        SELECT role, COUNT(*) as count
        FROM turns
        GROUP BY role
    """)
    turns_by_role = {row["role"]: row["count"] for row in cursor.fetchall()}

    # Get turns by provider
    cursor.execute("""
        SELECT provider_id, COUNT(*) as count
        FROM turns
        WHERE provider_id IS NOT NULL
        GROUP BY provider_id
        ORDER BY count DESC
    """)
    turns_by_provider = {row["provider_id"]: row["count"] for row in cursor.fetchall()}

    # Get turns by model
    cursor.execute("""
        SELECT model, COUNT(*) as count
        FROM turns
        WHERE model IS NOT NULL
        GROUP BY model
        ORDER BY count DESC
    """)
    turns_by_model = {row["model"]: row["count"] for row in cursor.fetchall()}

    # Get turns by intent
    cursor.execute("""
        SELECT intent, COUNT(*) as count
        FROM turns
        WHERE intent IS NOT NULL
        GROUP BY intent
        ORDER BY count DESC
    """)
    turns_by_intent = {row["intent"]: row["count"] for row in cursor.fetchall()}

    conn.close()

    return jsonify({
        "total_sessions": total_sessions,
        "total_turns": total_turns,
        "sessions_by_mode": sessions_by_mode,
        "turns_by_role": turns_by_role,
        "turns_by_provider": turns_by_provider,
        "turns_by_model": turns_by_model,
        "turns_by_intent": turns_by_intent
    }), 200
