"""
Debug Console routes.

Provides API endpoints for the debug console feature:
- Real-time log streaming via SSE
- Historical log retrieval with filtering
- Log management (clear, export)
- Debug mode toggle

All endpoints require admin authentication.
"""

from flask import Blueprint, jsonify, request, Response, stream_with_context
from datetime import datetime
import sqlite3
import json
import time
from auth.password import require_auth

debug_bp = Blueprint('debug', __name__, url_prefix='/api/debug')


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


@debug_bp.route("/logs/stream")
def stream_logs():
    """
    Stream debug logs in real-time using Server-Sent Events (SSE).

    Query params:
        - token: Authentication token
        - levels: Comma-separated log levels to filter (e.g., "error,warning")
        - source: Filter by source ("backend" or "frontend")
        - component: Filter by component tag (e.g., "AUTH", "ROUTER")

    Returns:
        SSE stream of log entries as JSON

    Requires: Admin authentication
    """
    from app import memory

    # Get auth token from query param (for EventSource compatibility)
    token = request.args.get("token")
    if not token:
        return jsonify({"error": "Unauthorized - token required"}), 401

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid or expired session"}), 401

    # Get user and check admin status
    user = memory.get_user_by_id(session["user_id"])
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    # Get filter parameters
    levels_param = request.args.get("levels", "")
    levels = set(levels_param.split(",")) if levels_param else set()
    source = request.args.get("source", "")
    component = request.args.get("component", "")

    def event_stream():
        """Generate SSE events for new log entries."""
        try:
            # Track the last seen log ID to avoid duplicates
            last_id = 0

            # Get initial last ID from database
            db_path = get_db_path(memory)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(id) as max_id FROM debug_logs")
            row = cursor.fetchone()
            if row and row['max_id']:
                last_id = row['max_id']
            conn.close()

            # Stream new logs
            while True:
                conn = sqlite3.connect(db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # Build query with filters
                query = "SELECT * FROM debug_logs WHERE id > ?"
                params = [last_id]

                if levels:
                    placeholders = ','.join(['?' for _ in levels])
                    query += f" AND level IN ({placeholders})"
                    params.extend(levels)

                if source:
                    query += " AND source = ?"
                    params.append(source)

                if component:
                    query += " AND component = ?"
                    params.append(component)

                query += " ORDER BY id ASC LIMIT 100"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                # Send new log entries
                for row in rows:
                    log_entry = {
                        'id': row['id'],
                        'timestamp': row['timestamp'],
                        'level': row['level'],
                        'source': row['source'],
                        'component': row['component'],
                        'message': row['message'],
                        'session_id': row['session_id'],
                        'user_id': row['user_id']
                    }
                    yield f"data: {json.dumps(log_entry)}\n\n"
                    last_id = row['id']

                conn.close()

                # Sleep briefly before checking for new logs
                time.sleep(0.5)

        except GeneratorExit:
            # Client disconnected
            pass
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(event_stream()), content_type='text/event-stream')


@debug_bp.route("/logs")
@require_auth(lambda: __import__('app').memory)
def get_logs():
    """
    Retrieve historical debug logs with filtering and pagination.

    Query params:
        - limit: Max number of logs to return (default: 100, max: 1000)
        - offset: Number of logs to skip (default: 0)
        - level: Filter by log level
        - source: Filter by source
        - component: Filter by component
        - since: ISO timestamp - only logs after this time
        - search: Search term for message content

    Returns:
        JSON: {"logs": [...], "total": int, "has_more": bool}

    Requires: Admin authentication
    """
    from app import memory

    # Check admin status
    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    # Get query parameters
    limit = min(int(request.args.get("limit", 100)), 1000)
    offset = int(request.args.get("offset", 0))
    level = request.args.get("level", "")
    source = request.args.get("source", "")
    component = request.args.get("component", "")
    since = request.args.get("since", "")
    search = request.args.get("search", "")

    try:
        db_path = get_db_path(memory)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if debug_logs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_logs'")
        if not cursor.fetchone():
            # Table doesn't exist yet - return empty results
            conn.close()
            return jsonify({
                "logs": [],
                "total": 0,
                "has_more": False
            })

        # Build query with filters
        query = "SELECT * FROM debug_logs WHERE 1=1"
        params = []

        if level:
            query += " AND level = ?"
            params.append(level)

        if source:
            query += " AND source = ?"
            params.append(source)

        if component:
            query += " AND component = ?"
            params.append(component)

        if since:
            query += " AND timestamp >= ?"
            params.append(since)

        if search:
            query += " AND message LIKE ?"
            params.append(f"%{search}%")

        # Get total count
        count_query = f"SELECT COUNT(*) as total FROM ({query})"
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']

        # Get paginated results
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()

        logs = []
        for row in rows:
            logs.append({
                'id': row['id'],
                'timestamp': row['timestamp'],
                'level': row['level'],
                'source': row['source'],
                'component': row['component'],
                'message': row['message'],
                'session_id': row['session_id'],
                'user_id': row['user_id']
            })

        conn.close()

        return jsonify({
            "logs": logs,
            "total": total,
            "has_more": (offset + len(logs)) < total
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@debug_bp.route("/logs", methods=["DELETE"])
@require_auth(lambda: __import__('app').memory)
def clear_logs():
    """
    Clear debug logs from database.

    Query params:
        - before: ISO timestamp - delete logs before this time
        - level: Delete only logs of this level

    Returns:
        JSON: {"deleted": int}

    Requires: Admin authentication
    """
    from app import memory

    # Check admin status
    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    before = request.args.get("before", "")
    level = request.args.get("level", "")

    try:
        db_path = get_db_path(memory)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if debug_logs table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_logs'")
        if not cursor.fetchone():
            # Table doesn't exist yet - nothing to delete
            conn.close()
            return jsonify({"deleted": 0})

        # Build delete query
        query = "DELETE FROM debug_logs WHERE 1=1"
        params = []

        if before:
            query += " AND timestamp < ?"
            params.append(before)

        if level:
            query += " AND level = ?"
            params.append(level)

        cursor.execute(query, params)
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        return jsonify({"deleted": deleted})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@debug_bp.route("/log", methods=["POST"])
@require_auth(lambda: __import__('app').memory)
def log_frontend():
    """
    Receive log entries from frontend.

    Request body:
        {
            "level": "error|warn|info|debug",
            "message": "Log message",
            "component": "ComponentName",
            "session_id": "optional-session-id"
        }

    Returns:
        JSON: {"status": "ok"}

    Requires: Authentication (admin check optional - logs when debug enabled)
    """
    from app import memory
    from core.user_utils import DEFAULT_USER_ID

    # Check if debug logging is enabled
    prefs = memory.get_all(DEFAULT_USER_ID)
    enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"

    if not enabled:
        return jsonify({"status": "ok", "logged": False})

    data = request.json
    level = data.get("level", "INFO").upper()
    message = data.get("message", "")
    component = data.get("component", "")
    session_id = data.get("session_id", "")

    # Get user from auth
    user = request.current_user
    user_id = user.get('id') if user else None

    try:
        db_path = get_db_path(memory)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO debug_logs (timestamp, level, source, component, message, user_id, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            level,
            'frontend',
            component,
            message,
            user_id,
            session_id
        ))

        conn.commit()
        conn.close()

        return jsonify({"status": "ok", "logged": True})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@debug_bp.route("/status")
def get_debug_status():
    """
    Get current debug console status.

    Returns:
        JSON: {"enabled": bool, "log_count": int}

    No authentication required (returns basic status only)
    """
    from app import memory
    from core.user_utils import DEFAULT_USER_ID

    try:
        # Check if debug is enabled
        prefs = memory.get_all(DEFAULT_USER_ID)
        enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"

        # Get log count (gracefully handle missing table)
        log_count = 0
        try:
            db_path = get_db_path(memory)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if debug_logs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_logs'")
            if cursor.fetchone():
                cursor.execute("SELECT COUNT(*) as count FROM debug_logs")
                row = cursor.fetchone()
                log_count = row[0] if row else 0

            conn.close()
        except Exception as db_error:
            # If debug_logs table doesn't exist or other DB error, return 0
            # This prevents the entire endpoint from failing
            pass

        # Get logger filter settings
        filters = {
            "sqlalchemy": str(prefs.get("debug_filter_sqlalchemy", "false")).lower() == "true",
            "werkzeug": str(prefs.get("debug_filter_werkzeug", "false")).lower() == "true",
            "urllib3": str(prefs.get("debug_filter_urllib3", "false")).lower() == "true",
            "botocore": str(prefs.get("debug_filter_botocore", "false")).lower() == "true",
        }

        return jsonify({
            "enabled": enabled,
            "log_count": log_count,
            "filters": filters
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@debug_bp.route("/toggle", methods=["POST"])
@require_auth(lambda: __import__('app').memory)
def toggle_debug():
    """
    Enable or disable debug logging.

    Request body: {"enabled": bool}

    Returns:
        JSON: {"status": "ok", "enabled": bool}

    Requires: Admin authentication
    """
    from app import memory, db_handler
    from core.user_utils import DEFAULT_USER_ID

    # Check admin status
    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    data = request.json
    enabled = bool(data.get("enabled", False))

    # Update preference
    memory.remember(
        user_id=DEFAULT_USER_ID,
        key="debug_enabled",
        value=str(enabled).lower()
    )

    # Safety: When disabling debug, reset all verbose logger filters to OFF and clear logs
    if not enabled:
        verbose_filters = [
            "debug_filter_sqlalchemy",
            "debug_filter_werkzeug",
            "debug_filter_urllib3",
            "debug_filter_botocore"
        ]
        for filter_key in verbose_filters:
            memory.remember(
                user_id=DEFAULT_USER_ID,
                key=filter_key,
                value="false"
            )

        # Clear all debug logs
        try:
            db_path = get_db_path(memory)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if debug_logs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='debug_logs'")
            if cursor.fetchone():
                cursor.execute("DELETE FROM debug_logs")
                conn.commit()

            conn.close()
        except Exception as e:
            # Log error but don't fail the disable operation
            import sys
            print(f"[DEBUG-TOGGLE] Warning: Failed to clear logs: {e}", file=sys.stderr)

    # Invalidate cache so handler picks up change immediately
    db_handler.invalidate_cache()

    return jsonify({"status": "ok", "enabled": enabled})


@debug_bp.route("/filters", methods=["POST"])
@require_auth(lambda: __import__('app').memory)
def update_filters():
    """
    Update logger filter settings.

    Request body: {
        "sqlalchemy": bool,
        "werkzeug": bool,
        "urllib3": bool,
        "botocore": bool
    }

    Returns:
        JSON: {"status": "ok", "filters": {...}}

    Requires: Admin authentication
    """
    from app import memory, db_handler
    from core.user_utils import DEFAULT_USER_ID

    # Check admin status
    user = request.current_user
    if not is_admin(memory, user):
        return jsonify({"error": "Forbidden - admin access required"}), 403

    data = request.json
    filters = data.get("filters", {})

    # Update each filter preference
    filter_map = {
        "sqlalchemy": "debug_filter_sqlalchemy",
        "werkzeug": "debug_filter_werkzeug",
        "urllib3": "debug_filter_urllib3",
        "botocore": "debug_filter_botocore",
    }

    updated_filters = {}
    for key, pref_key in filter_map.items():
        if key in filters:
            value = bool(filters[key])
            memory.remember(
                user_id=DEFAULT_USER_ID,
                key=pref_key,
                value=str(value).lower()
            )
            updated_filters[key] = value

    # Invalidate cache so handler picks up changes immediately
    db_handler.invalidate_cache()

    return jsonify({"status": "ok", "filters": updated_filters})
