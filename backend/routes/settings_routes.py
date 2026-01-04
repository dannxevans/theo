"""
Settings routes.

Provides application settings endpoints for debug mode and system prompt configuration.
"""

from flask import Blueprint, jsonify, request
from core.user_utils import DEFAULT_USER_ID

settings_bp = Blueprint('settings', __name__, url_prefix='/api/settings')



def get_user_id_from_request():
    """Extract user_id from auth token or use default."""
    return DEFAULT_USER_ID


@settings_bp.route("/debug", methods=["GET"])
def get_debug_setting():
    """
    Get debug mode setting.
    Returns: { "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # Read from preferences, not routing
    prefs = memory.get_all(get_user_id_from_request())
    value = prefs.get("debug_enabled")

    if value is None:
        enabled = False
    else:
        enabled = str(value).lower() == "true"

    return jsonify({"enabled": enabled})


@settings_bp.route("/debug", methods=["POST"])
def set_debug_setting():
    """
    Set debug mode setting.
    Request body: { "enabled": bool }
    Returns: { "status": "ok", "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    enabled = bool(data.get("enabled", False))

    # Persist as preference
    memory.remember(
        user_id=get_user_id_from_request(),
        key="debug_enabled",
        value=str(enabled).lower()
    )

    return jsonify({"status": "ok", "enabled": enabled})


@settings_bp.route("/message-debug", methods=["GET"])
def get_message_debug_setting():
    """
    Get message debug mode setting.
    Returns: { "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use get_user_id_from_request() for unauthenticated
    user_id = get_user_id_from_request()
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    # Read from preferences
    prefs = memory.get_all(user_id)
    value = prefs.get("message_debug_enabled")

    if value is None:
        enabled = False
    else:
        enabled = str(value).lower() == "true"

    return jsonify({"enabled": enabled})


@settings_bp.route("/message-debug", methods=["POST"])
def set_message_debug_setting():
    """
    Set message debug mode setting.
    Request body: { "enabled": bool }
    Returns: { "status": "ok", "enabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use get_user_id_from_request() for unauthenticated
    user_id = get_user_id_from_request()
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    data = request.json
    enabled = bool(data.get("enabled", False))

    # Persist as preference
    import logging
    logging.info(f"[MESSAGE_DEBUG_POST] Saving preference for user_id={user_id}, enabled={enabled}")
    memory.remember(
        user_id=user_id,
        key="message_debug_enabled",
        value=str(enabled).lower()
    )

    # Verify it was saved
    prefs_check = memory.get_all(user_id)
    logging.info(f"[MESSAGE_DEBUG_POST] After save, prefs for user_id={user_id}: {prefs_check}")

    return jsonify({"status": "ok", "enabled": enabled})


@settings_bp.route("/system-prompt", methods=["GET"])
def get_system_prompt_settings():
    """
    Get system prompt configuration.
    Returns: System prompt config object
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    config = memory.get_system_prompt_config(get_user_id_from_request())
    
    return jsonify(config)


@settings_bp.route("/system-prompt", methods=["POST"])
def update_system_prompt_settings():
    """
    Update system prompt configuration.
    Request body: { "persona_name": "...", "tone": "...", "style_rules": "...", "custom_instructions": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json

    # Only allow updating specific fields
    allowed_fields = ["persona_name", "tone", "style_rules", "custom_instructions"]
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    memory.update_system_prompt_config(get_user_id_from_request(), **updates)
    return jsonify({"status": "ok"})


@settings_bp.route("/preference/<key>", methods=["GET"])
def get_user_preference(key):
    """
    Get a user preference value.
    Returns: { "value": "..." }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)

    # For now, using get_user_id_from_request() as user_id (will be replaced with actual auth later)
    value = memory.get_user_preference(get_user_id_from_request(), key)

    return jsonify({"value": value})


@settings_bp.route("/preference/<key>", methods=["POST"])
def set_user_preference(key):
    """
    Set a user preference value.
    Request body: { "value": "..." }
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config

    memory = MemoryStore(Config.DATABASE_URL)
    data = request.json
    value = data.get("value")

    if value is None:
        return jsonify({"error": "Value is required"}), 400

    # For now, using get_user_id_from_request() as user_id
    memory.set_user_preference(get_user_id_from_request(), key, str(value))

    return jsonify({"status": "ok"})


@settings_bp.route("/proactive", methods=["GET"])
def get_proactive_settings():
    """
    Get proactive notification settings.
    Returns: Proactive settings object
    """
    from core.memory import MemoryStore
    from config import Config
    from sqlalchemy import text

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = get_user_id_from_request()  # For now, using get_user_id_from_request() as user_id

    try:
        with memory.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT calendar_enabled, email_enabled,
                       calendar_lead_time_minutes, calendar_check_frequency_minutes,
                       email_check_frequency_minutes, email_digest_frequency_minutes,
                       max_messages_per_hour,
                       quiet_hours_enabled, quiet_hours_start, quiet_hours_end,
                       frontend_poll_interval_minutes
                FROM proactive_settings
                WHERE user_id = :user_id
            """), {"user_id": user_id})

            row = result.fetchone()

            if row:
                return jsonify({
                    "calendar_enabled": bool(row[0]),
                    "email_enabled": bool(row[1]),
                    "calendar_lead_time_minutes": row[2],
                    "calendar_check_frequency_minutes": row[3],
                    "email_check_frequency_minutes": row[4],
                    "email_digest_frequency_minutes": row[5],
                    "max_messages_per_hour": row[6],
                    "quiet_hours_enabled": bool(row[7]),
                    "quiet_hours_start": row[8],
                    "quiet_hours_end": row[9],
                    "frontend_poll_interval_minutes": row[10]
                })
            else:
                # Return defaults if no settings found
                return jsonify({
                    "calendar_enabled": True,
                    "email_enabled": True,
                    "calendar_lead_time_minutes": 15,
                    "calendar_check_frequency_minutes": 15,
                    "email_check_frequency_minutes": 15,
                    "email_digest_frequency_minutes": 60,
                    "max_messages_per_hour": 10,
                    "quiet_hours_enabled": False,
                    "quiet_hours_start": None,
                    "quiet_hours_end": None,
                    "frontend_poll_interval_minutes": 5
                })

    except Exception as e:
        import logging
        logging.error(f"[SETTINGS] Error fetching proactive settings: {e}")
        return jsonify({"error": "Failed to fetch proactive settings"}), 500


@settings_bp.route("/proactive", methods=["POST"])
def update_proactive_settings():
    """
    Update proactive notification settings.
    Request body: Proactive settings object
    Returns: { "status": "ok" }
    """
    from core.memory import MemoryStore
    from config import Config
    from sqlalchemy import text

    memory = MemoryStore(Config.DATABASE_URL)
    user_id = get_user_id_from_request()  # For now, using get_user_id_from_request() as user_id
    data = request.json

    try:
        # Build UPDATE statement dynamically based on provided fields
        allowed_fields = {
            "calendar_enabled": "calendar_enabled",
            "email_enabled": "email_enabled",
            "calendar_lead_time_minutes": "calendar_lead_time_minutes",
            "calendar_check_frequency_minutes": "calendar_check_frequency_minutes",
            "email_check_frequency_minutes": "email_check_frequency_minutes",
            "email_digest_frequency_minutes": "email_digest_frequency_minutes",
            "max_messages_per_hour": "max_messages_per_hour",
            "quiet_hours_enabled": "quiet_hours_enabled",
            "quiet_hours_start": "quiet_hours_start",
            "quiet_hours_end": "quiet_hours_end",
            "frontend_poll_interval_minutes": "frontend_poll_interval_minutes"
        }

        updates = {}
        for key, db_field in allowed_fields.items():
            if key in data:
                updates[db_field] = data[key]

        if not updates:
            return jsonify({"error": "No valid fields to update"}), 400

        with memory.engine.connect() as conn:
            # Build SQL
            set_clause = ", ".join([f"{field} = :{field}" for field in updates.keys()])
            set_clause += ", updated_at = CURRENT_TIMESTAMP"

            # Add user_id to params
            params = {**updates, "user_id": user_id}

            sql = text(f"""
                UPDATE proactive_settings
                SET {set_clause}
                WHERE user_id = :user_id
            """)

            result = conn.execute(sql, params)
            conn.commit()

            # If no rows updated, insert default settings
            if result.rowcount == 0:
                # Insert with provided values
                fields = ["user_id"] + list(updates.keys())
                placeholders = ", ".join([f":{field}" for field in fields])
                field_names = ", ".join(fields)

                insert_sql = text(f"""
                    INSERT INTO proactive_settings ({field_names})
                    VALUES ({placeholders})
                """)

                conn.execute(insert_sql, params)
                conn.commit()

        # Reschedule jobs if scheduler is running
        try:
            from core.scheduler import get_scheduler
            scheduler = get_scheduler()
            if scheduler and scheduler.is_running():
                scheduler.reschedule_jobs()
                import logging
                logging.info("[SETTINGS] Proactive jobs rescheduled after settings update")
        except Exception as e:
            import logging
            logging.warning(f"[SETTINGS] Could not reschedule jobs: {e}")

        return jsonify({"status": "ok"})

    except Exception as e:
        import logging
        logging.error(f"[SETTINGS] Error updating proactive settings: {e}")
        return jsonify({"error": "Failed to update proactive settings"}), 500


@settings_bp.route("/visual-streaming", methods=["GET"])
def get_visual_streaming_setting():
    """
    Get visual streaming setting (whether to disable the typewriter effect).
    Returns: { "disabled": bool }
    """
    import logging
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    logging.info("[VISUAL_STREAMING] GET request received")
    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use get_user_id_from_request() for unauthenticated
    user_id = get_user_id_from_request()
    logging.info(f"[VISUAL_STREAMING] Initial user_id from request: {user_id}")

    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]
            logging.info(f"[VISUAL_STREAMING] Authenticated user_id: {user_id}")

    # Read from preferences
    prefs = memory.get_all(user_id)
    value = prefs.get("visual_streaming_disabled")
    logging.info(f"[VISUAL_STREAMING] Retrieved value for user {user_id}: {value}")

    if value is None:
        disabled = False  # Default: visual streaming enabled (not disabled)
    else:
        disabled = str(value).lower() == "true"

    logging.info(f"[VISUAL_STREAMING] Returning disabled={disabled}")
    return jsonify({"disabled": disabled})


@settings_bp.route("/visual-streaming", methods=["POST"])
def set_visual_streaming_setting():
    """
    Set visual streaming setting (whether to disable the typewriter effect).
    Request body: { "disabled": bool }
    Returns: { "status": "ok", "disabled": bool }
    """
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime

    memory = MemoryStore(Config.DATABASE_URL)

    # Get authenticated user or use get_user_id_from_request() for unauthenticated
    user_id = get_user_id_from_request()
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        session = memory.get_auth_session(token)
        if session and session["expires_at"] >= datetime.utcnow():
            user_id = session["user_id"]

    data = request.json
    disabled = bool(data.get("disabled", False))

    # Persist as preference
    import logging
    logging.info(f"[VISUAL_STREAMING] Saving preference for user_id={user_id}, disabled={disabled}")
    memory.remember(
        user_id=user_id,
        key="visual_streaming_disabled",
        value=str(disabled).lower()
    )

    return jsonify({"status": "ok", "disabled": disabled})


@settings_bp.route("/database/restore-from-s3", methods=["POST"])
def restore_database_from_s3():
    """
    Restore database from S3 backup (Unraid only).
    Downloads the latest database backup from S3 and replaces the current database.
    Returns: { "status": "ok", "message": "..." }
    """
    import logging
    import os
    import shutil
    from datetime import datetime
    from pathlib import Path
    from db_backup import DatabaseBackupManager
    from config import Config

    logging.info("[DB_RESTORE] S3 restore requested")

    # Get S3 configuration
    s3_bucket = os.getenv("THEO_S3_BACKUP_BUCKET")
    s3_key = os.getenv("THEO_S3_BACKUP_KEY", "theo/theo.db")

    if not s3_bucket:
        logging.error("[DB_RESTORE] S3 bucket not configured")
        return jsonify({"error": "S3 backup not configured. Set THEO_S3_BACKUP_BUCKET environment variable."}), 400

    # Get database path
    db_url = Config.DATABASE_URL
    if not db_url.startswith("sqlite:///"):
        logging.error("[DB_RESTORE] Not using SQLite database")
        return jsonify({"error": "Database restore only supported for SQLite databases"}), 400

    db_path = Path(db_url.replace("sqlite:///", ""))
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(exist_ok=True)

    try:
        # Backup current database before restore
        if db_path.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"theo_pre_s3_restore_{timestamp}.db"
            logging.info(f"[DB_RESTORE] Backing up current database to {backup_path}")
            shutil.copy2(db_path, backup_path)

        # Initialize backup manager and restore from S3
        manager = DatabaseBackupManager(str(db_path), s3_bucket, s3_key)
        success = manager.restore_from_s3()

        if not success:
            logging.error("[DB_RESTORE] Failed to restore from S3")
            return jsonify({"error": "Failed to download database from S3. Check logs for details."}), 500

        logging.info("[DB_RESTORE] Database restored successfully from S3")
        return jsonify({
            "status": "ok",
            "message": f"Database restored from s3://{s3_bucket}/{s3_key}"
        })

    except Exception as e:
        logging.error(f"[DB_RESTORE] Error during restore: {e}")
        import traceback
        logging.error(f"[DB_RESTORE] Traceback: {traceback.format_exc()}")
        return jsonify({"error": f"Failed to restore database: {str(e)}"}), 500
