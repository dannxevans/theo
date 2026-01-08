# import eventlet
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
# eventlet.monkey_patch()
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.router import route_request, set_provider_registry, set_context_manager, set_action_router, set_action_registry
from core.context import ContextManager
from core.memory import MemoryStore
from config import Config
from core.provider_registry import ProviderRegistry
from core.action_router import ActionRouter
from actions.action_registry import ActionProviderRegistry
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Response, stream_with_context
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

app = Flask(__name__)
# Wrap app with ProxyFix to correctly handle X-Forwarded headers from reverse proxy (Nginx/Traefik)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SESSION_COOKIE_SECURE"] = True

ALLOWED_ORIGINS = [
    # Local DEV
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.10.25:5173",
    "https://dev.theoai.uk",

    # Primary domains
    "https://theoai.uk",
    "https://www.theoai.uk",
    "https://app.theoai.uk",

    # Secondary domain
    "https://duckyfuzz.uk",
    "https://app.duckyfuzz.uk",
    "https://ai.duckyfuzz.uk"
]

CORS(
    app,
    resources={
        r"/api/*": {"origins": ALLOWED_ORIGINS},
    },
    supports_credentials=True,
)


# Initialize database migrations (before creating MemoryStore)
# Note: S3 backup functionality removed - now using Unraid native backups
from db_backup import init_database_backup
init_database_backup()  # Runs migrations only, no longer returns backup manager

memory = MemoryStore(Config.DATABASE_URL)
context_manager = ContextManager(memory)
provider_registry = ProviderRegistry(memory)
set_context_manager(context_manager)

# Add DatabaseLogHandler for debug console
# This must be outside if __name__ == "__main__" to work with Gunicorn
from core.logging_handler import DatabaseLogHandler
db_handler = DatabaseLogHandler(memory)
db_handler.setLevel(logging.DEBUG)
app.logger.addHandler(db_handler)

# Also capture logs from root logger (for non-Flask logs)
logging.getLogger().addHandler(db_handler)

# Inject provider registry into router
set_provider_registry(provider_registry)

# Initialize action system
action_registry = ActionProviderRegistry(memory)
action_router = ActionRouter(action_registry, memory)
set_action_router(action_router)
set_action_registry(action_registry)

# Initialize confirmation manager
from core.confirmation_manager import ConfirmationManager
confirmation_manager = ConfirmationManager(memory, action_router)

# Connect confirmation manager to action router
action_router.confirmation_manager = confirmation_manager

# Seed default intents if none exist
# Check if intents exist for user 1 (admin), otherwise seed for user 1
try:
    existing_intents = memory.list_intents("1")
    if not existing_intents:
        memory.seed_default_intents("1")
except Exception as e:
    logging.warning(f"Could not check/seed intents: {e}")

# Initialize authentication
from auth import init_default_user
init_default_user(memory)

# Initialize proactive scheduler
try:
    from core.scheduler import init_scheduler
    proactive_scheduler = init_scheduler(memory)
    logging.info("[APP] Proactive scheduler initialized and started")
except Exception as e:
    logging.warning(f"[APP] Failed to initialize proactive scheduler: {e}")

# Register route blueprints
from routes.health_routes import health_bp
from routes.auth_routes import auth_bp
from routes.api_key_routes import api_key_bp
from routes.user_management_routes import user_mgmt_bp
from routes.session_routes import session_bp
from routes.folder_routes import folder_bp
from routes.message_routes import message_bp
from routes.memory_routes import memory_bp
from routes.provider_routes import provider_bp
from routes.intent_routes import intent_bp
from routes.routing_routes import routing_bp
from routes.mode_routes import mode_bp
from routes.m365_routes import m365_bp
from routes.whoop_routes import whoop_bp
from routes.service_provider_routes import service_provider_bp
from routes.settings_routes import settings_bp
from routes.calendar_routes import calendar_bp
from routes.confirmation_routes import confirmation_bp
from routes.voice_routes import voice_bp
from routes.feature_provider_routes import feature_provider_bp
from routes.planning_routes import planning_bp
from routes.routine_routes import routine_bp
from routes.debug_routes import debug_bp
from routes.audit_routes import audit_bp

app.register_blueprint(health_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(api_key_bp)
app.register_blueprint(user_mgmt_bp)
app.register_blueprint(session_bp)
app.register_blueprint(folder_bp)
app.register_blueprint(message_bp)
app.register_blueprint(memory_bp)
app.register_blueprint(provider_bp)
app.register_blueprint(intent_bp)
app.register_blueprint(routing_bp)
app.register_blueprint(mode_bp)
app.register_blueprint(m365_bp)
app.register_blueprint(whoop_bp)
app.register_blueprint(service_provider_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(calendar_bp)
app.register_blueprint(confirmation_bp)
app.register_blueprint(voice_bp, url_prefix="/api/voice")
app.register_blueprint(feature_provider_bp)
app.register_blueprint(planning_bp)
app.register_blueprint(routine_bp)
app.register_blueprint(debug_bp)
app.register_blueprint(audit_bp)

# Set g.user_id for all requests based on auth token
@app.before_request
def set_user_id():
    from flask import g
    # Extract token from Authorization header
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        # Look up session to get user_id
        session = memory.get_auth_session(token)
        if session:
            g.user_id = session.get('user_id')
        else:
            g.user_id = None
    else:
        g.user_id = None

def debug_log(message):
    try:
        prefs = memory.get_all(DEFAULT_USER_ID)
        enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"
        if enabled:
            logging.info(f"[DEBUG] {message}")
    except Exception as e:
        logging.warning(f"[DEBUG-LOGGING-ERROR] {e}")

        

if __name__ == "__main__":
    import os
    # SECURITY: Only enable debug mode via environment variable
    # Never run with debug=True in production
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")

    if debug_mode:
        print("[SECURITY WARNING] Flask debug mode is ENABLED - only use in development!")

    print("THEO backend starting on port 1066")
    app.run(host="0.0.0.0", port=1066, debug=True)