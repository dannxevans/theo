# import eventlet
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
# Wrap app with ProxyFix to correctly handle X-Forwarded headers from ALB (Application Load Balancer)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
app.config["PREFERRED_URL_SCHEME"] = "https"
app.config["SESSION_COOKIE_SECURE"] = True

ALLOWED_ORIGINS = [
    # Local DEV
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://192.168.10.25:5173",
    "https://dev.theoai.uk",

    # Primary CloudFront domains
    "https://theoai.uk",
    "https://www.theoai.uk",
    "https://app.theoai.uk",

    # Secondary CloudFront domain
    "https://duckyfuzz.uk",
    "https://app.duckyfuzz.uk",
    "https://ai.duckyfuzz.uk",

    # (Optional but useful for debugging)
    "http://theo-alb-306035510.eu-west-2.elb.amazonaws.com"
]

CORS(
    app,
    resources={
        r"/api/*": {"origins": ALLOWED_ORIGINS},
    },
    supports_credentials=True,
)

@app.route("/health")
def health():
    return {"status": "ok", "service": "THEO-Backend"} , 200

# Initialize database backup/restore (before creating MemoryStore)
from db_backup import init_database_backup
backup_manager = init_database_backup()

memory = MemoryStore(Config.DATABASE_URL)
context_manager = ContextManager(memory)
provider_registry = ProviderRegistry(memory)
set_context_manager(context_manager)

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
memory.seed_default_intents("local")

# Initialize authentication
from auth import init_default_user
init_default_user(memory)

@app.route("/api/health")
def api_health():
    return {"status": "ok", "service": "THEO"}

@app.route("/api/chat", methods=["POST"])
def chat():
    payload = request.json
    session_id = payload.get("session_id", "default")
    text = payload.get("text", "")

    context = context_manager.build_context(session_id, text)
    result = route_request(context)

    # Pass the full result object so metadata can be extracted
    context_manager.update(session_id, text, result, provider_registry)
    return jsonify(result)

@app.route("/api/stream/<session_id>")
def stream_chat_sse(session_id):
    text = request.args.get("text", "")
    forced_provider = request.args.get("forced_provider")

    def event_stream():
        try:
            # Get user from auth token (check both header and query param)
            auth_header = request.headers.get("Authorization")
            token = None
            user_id = None

            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            elif request.args.get("token"):
                token = request.args.get("token")

            if token:
                session = memory.get_auth_session(token)
                if session and session["expires_at"] >= datetime.utcnow():
                    user_id = session["user_id"]
                    logging.info(f"[AUTH] Authenticated user_id: {user_id}")
                else:
                    logging.warning(f"[AUTH] Invalid or expired session token")
            else:
                logging.warning(f"[AUTH] No token provided in request")

            context = context_manager.build_context(session_id, text)

            router_context = dict(context)
            router_context["text"] = text
            router_context["session_id"] = session_id
            router_context["memory"] = memory
            if forced_provider:
                router_context["forced_provider"] = forced_provider

            # Apply mode-specific settings if user is authenticated
            if user_id:
                mode_config = memory.get_user_mode(user_id)
                current_mode = mode_config.get("active_mode", "personal")
                logging.info(f"[MODE] User {user_id} current_mode: {current_mode}")
                mode_settings = memory.get_mode_settings(user_id, current_mode)

                if mode_settings:
                    # Apply system prompt override if configured
                    if mode_settings.get("system_prompt_override"):
                        router_context["system_prompt_override"] = mode_settings["system_prompt_override"]

                    # Apply preferred provider if configured
                    if mode_settings.get("preferred_provider_id") and not forced_provider:
                        router_context["forced_provider"] = str(mode_settings["preferred_provider_id"])

                    # Store mode for metadata
                    router_context["active_mode"] = current_mode

                # Inject base mode awareness context
                mode_context_prefix = None
                if current_mode == "work":
                    mode_context_prefix = "IMPORTANT CONTEXT UPDATE: You are currently operating in WORK mode. This is a professional work context. If the user asks what mode you are in, you MUST respond that you are in WORK mode, regardless of any previous conversation history."
                elif current_mode == "personal":
                    mode_context_prefix = "IMPORTANT CONTEXT UPDATE: You are currently operating in PERSONAL mode. This is a casual, personal context. If the user asks what mode you are in, you MUST respond that you are in PERSONAL mode, regardless of any previous conversation history."

                # Apply work mode subtab context if in work mode
                if current_mode == "work":
                    work_subtab = request.args.get("work_subtab", "conversation")
                    logging.info(f"[MODE] Work mode - subtab: {work_subtab}")
                    subtab_config = memory.get_work_subtab_config(user_id, work_subtab)

                    context_prefix = None
                    if subtab_config:
                        logging.info(f"[MODE] Found subtab config for {work_subtab}")
                        import json as json_module
                        config = json_module.loads(subtab_config.get("config_json", "{}"))

                        # Build context prefix based on subtab
                        if work_subtab == "code":
                            language = config.get("language", "servicenow_javascript")
                            framework = config.get("framework", "")
                            additional = config.get("additional_context", "")

                            language_names = {
                                "servicenow_javascript": "ServiceNow JavaScript",
                                "javascript": "JavaScript",
                                "typescript": "TypeScript",
                                "python": "Python",
                                "java": "Java",
                                "csharp": "C#",
                            }
                            lang_name = language_names.get(language, language)

                            context_prefix = f"You are an expert {lang_name} developer."
                            if framework:
                                context_prefix += f" You specialize in {framework}."
                            if additional:
                                context_prefix += f" {additional}"

                        elif work_subtab == "email":
                            tone = config.get("tone", "professional")
                            context_prefix = f"You are helping rewrite emails with a {tone} tone. Focus on clarity, professionalism, and appropriate formatting for business communication."
                    else:
                        logging.info(f"[MODE] No subtab config found for {work_subtab}")

                    # Combine mode context with subtab context (MOVED OUTSIDE if subtab_config block)
                    if context_prefix and mode_context_prefix:
                        combined_context = f"{mode_context_prefix} {context_prefix}"
                        router_context["subtab_context_prefix"] = combined_context
                        logging.info(f"[MODE] Set combined context for work mode")
                    elif context_prefix:
                        router_context["subtab_context_prefix"] = context_prefix
                        logging.info(f"[MODE] Set subtab context only for work mode")
                    elif mode_context_prefix:
                        router_context["subtab_context_prefix"] = mode_context_prefix
                        logging.info(f"[MODE] Set mode context only for work mode: {mode_context_prefix[:100]}")
                else:
                    # Not in work mode, just apply mode context if available
                    if mode_context_prefix:
                        router_context["subtab_context_prefix"] = mode_context_prefix
                        logging.info(f"[MODE] Set subtab_context_prefix for {current_mode} mode: {mode_context_prefix[:100]}")
            else:
                logging.warning(f"[MODE] No user_id - skipping mode context injection")

            # Route request (non-streaming, we chunk manually)
            result = route_request(router_context)

            full_text = result.get("text", "")
            chunk_size = 32

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                yield f"data: {json.dumps({'token': chunk})}\n\n"

            # Save the turn to database BEFORE sending end event
            # This ensures metadata is persisted before frontend reloads messages
            context_manager.update(session_id, text, result, provider_registry)

            # Send metadata at end of stream
            end_payload = {
                "provider": result.get("provider"),
                "model": result.get("model"),
                "task_type": result.get("task_type"),
                "fallback_reason": result.get("fallback_reason"),
                "routing": result.get("routing"),
            }

            yield "event: end\n"
            yield f"data: {json.dumps(end_payload)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        headers={
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
        },
    )

@app.route("/api/memory/remember", methods=["POST"])
def remember():
    """Legacy memory endpoint (kept for backwards compatibility)"""
    data = request.json
    memory.remember(
        user_id="local",
        key=data["key"],
        value=data["value"]
    )
    return jsonify({"status": "ok"})

@app.route("/api/memory/forget", methods=["POST"])
def forget():
    """Legacy memory endpoint (kept for backwards compatibility)"""
    data = request.json
    memory.forget("local", data["key"])
    return jsonify({"status": "ok"})

# =============================
# Step 2: Structured Memory APIs
# =============================

@app.route("/api/memories", methods=["GET"])
def list_memories():
    """
    Get all structured memories for the user.
    Optional query params:
    - type: filter by memory type (fact, preference, goal, context)
    - limit: max results
    """
    memory_type = request.args.get("type")
    limit = request.args.get("limit", type=int)

    memories = memory.get_memories("local", memory_type=memory_type, limit=limit)
    return jsonify(memories)

@app.route("/api/memories", methods=["POST"])
def create_memory():
    """
    Store a new structured memory.
    Body: {type, key, value, pinned}
    """
    data = request.json
    memory.store_memory(
        user_id="local",
        memory_type=data.get("type", "fact"),
        key=data["key"],
        value=data["value"],
        pinned=data.get("pinned", False),
    )
    return jsonify({"status": "ok"})

@app.route("/api/memories/<int:memory_id>", methods=["DELETE"])
def delete_memory_endpoint(memory_id):
    """Delete a memory by ID"""
    memory.delete_memory("local", memory_id)
    return jsonify({"status": "ok"})

@app.route("/api/memories/<int:memory_id>/pin", methods=["POST"])
def pin_memory_endpoint(memory_id):
    """Pin or unpin a memory"""
    data = request.json
    pinned = data.get("pinned", True)
    memory.pin_memory("local", memory_id, pinned)
    return jsonify({"status": "ok", "pinned": pinned})

@app.route("/api/memories/relevant", methods=["GET"])
def get_relevant_memories():
    """
    Get memories relevant to a query.
    Query param: q (query text)
    """
    query = request.args.get("q", "")
    if not query:
        return jsonify([])

    relevant = memory.get_relevant_memories("local", query, max_results=7)
    return jsonify(relevant)

# =============================
# Step 3: Provider Intelligence APIs
# =============================

@app.route("/api/providers/health", methods=["GET"])
def get_provider_health():
    """Get health summary for all providers"""
    summary = memory.get_provider_health_summary()
    return jsonify(summary)

@app.route("/api/providers/<provider_id>/metadata", methods=["GET"])
def get_provider_metadata_endpoint(provider_id):
    """Get metadata for a specific provider"""
    metadata = memory.get_provider_metadata(provider_id)
    if not metadata:
        return jsonify({"error": "Provider not found"}), 404
    return jsonify(metadata)

@app.route("/api/providers/<provider_id>/metadata", methods=["POST"])
def update_provider_metadata_endpoint(provider_id):
    """Update cost metadata for a provider"""
    data = request.json
    memory.init_provider_metadata(
        provider_id,
        cost_per_1k_input=data.get("cost_per_1k_input", 0),
        cost_per_1k_output=data.get("cost_per_1k_output", 0),
    )
    return jsonify({"status": "ok"})

# =============================
# Routing Preferences APIs
# =============================

# =============================
# Intent Management APIs
# =============================

@app.route("/api/intents", methods=["GET"])
def list_intents():
    """Get all user-defined intents."""
    intents = memory.list_intents("local")
    return jsonify(intents)

@app.route("/api/intents/<intent_id>", methods=["GET"])
def get_intent(intent_id):
    """Get a single intent by ID."""
    intent = memory.get_intent("local", intent_id)
    if not intent:
        return jsonify({"error": "Intent not found"}), 404
    return jsonify(intent)

@app.route("/api/intents", methods=["POST"])
def create_intent():
    """Create a new intent."""
    data = request.json
    intent_id = data.get("id")
    name = data.get("name")
    description = data.get("description", "")
    keywords = data.get("keywords", "")
    priority = data.get("priority", 0)
    enabled = data.get("enabled", True)

    if not intent_id or not name:
        return jsonify({"error": "id and name are required"}), 400

    try:
        memory.create_intent(
            user_id="local",
            intent_id=intent_id,
            name=name,
            description=description,
            keywords=keywords,
            priority=priority,
            enabled=enabled,
        )
        return jsonify({"status": "ok", "intent_id": intent_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/intents/<intent_id>", methods=["PUT"])
def update_intent(intent_id):
    """Update an existing intent."""
    data = request.json
    updates = {}

    # Only include fields that are present in the request
    if "name" in data:
        updates["name"] = data["name"]
    if "description" in data:
        updates["description"] = data["description"]
    if "keywords" in data:
        updates["keywords"] = data["keywords"]
    if "priority" in data:
        updates["priority"] = data["priority"]
    if "enabled" in data:
        updates["enabled"] = data["enabled"]

    try:
        memory.update_intent("local", intent_id, **updates)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/intents/<intent_id>", methods=["DELETE"])
def delete_intent(intent_id):
    """Delete an intent."""
    try:
        memory.delete_intent("local", intent_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =============================
# Routing Preferences APIs
# =============================

@app.route("/api/routing", methods=["GET"])
def get_routing_preferences():
    prefs = memory.get_routing_preferences("local")
    return jsonify(prefs)

@app.route("/api/routing", methods=["POST"])
def set_routing_preference():
    data = request.json
    memory.set_routing_preference(
        user_id="local",
        intent=data["intent"],
        provider_id=data["provider_id"],
    )
    return jsonify({"status": "ok"})

@app.route("/api/routing/<intent>", methods=["DELETE"])
def delete_routing_preference(intent):
    memory.delete_routing_preference("local", intent)
    return jsonify({"status": "ok"})

@app.route("/api/session/<session_id>", methods=["GET"])
def get_session(session_id):
    summary = memory.get_session_summary(session_id)
    return {
        "session_id": session_id,
        "summary": summary
    }


@app.route("/api/sessions", methods=["GET"])
def list_sessions():
    sessions = memory.list_sessions()

    response = []
    for s in sessions:
        response.append({
            "id": s["id"],
            "title": s.get("title"),
            "summary": s.get("summary"),
        })

    return jsonify(response)

# New route: fetch messages for a session
@app.route("/api/sessions/<session_id>/messages", methods=["GET"])
def get_session_messages(session_id):
    # Load all conversation turns for this session
    turns = memory.get_recent_turns(session_id, limit=1000)

    # Normalise shape for frontend
    return jsonify([
        {
            "role": t["role"],
            "content": t["content"],
            "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
            "provider": t.get("provider_id"),
            "model": t.get("model"),
            "task_type": t.get("intent"),
            "metadata": t.get("metadata"),
        }
        for t in turns
    ])

@app.route("/api/sessions/<session_id>", methods=["DELETE"])
def delete_session(session_id):
    memory.delete_session(session_id)
    return jsonify({"status": "ok"})

@app.route("/api/sessions/<session_id>/export", methods=["GET"])
def export_session(session_id):
    """
    Export a conversation in JSON or Markdown format.
    Query param: format=json|markdown (default: json)
    """
    export_format = request.args.get("format", "json").lower()

    # Get session metadata
    session_data = memory.list_sessions()
    session = next((s for s in session_data if s["id"] == session_id), None)

    # Get all messages
    turns = memory.get_recent_turns(session_id, limit=10000)

    if export_format == "markdown":
        # Generate markdown format
        lines = []
        if session:
            lines.append(f"# {session.get('title', 'Conversation')}")
            lines.append(f"\n**Session ID:** {session_id}")
            lines.append(f"**Created:** {session.get('created_at', 'Unknown')}")
            if session.get('summary'):
                lines.append(f"\n**Summary:** {session['summary']}")
            lines.append("\n---\n")

        for turn in turns:
            role = turn["role"].upper()
            content = turn["content"]
            timestamp = turn.get("created_at", "")

            if role == "USER":
                lines.append(f"## 👤 User")
            else:
                lines.append(f"## 🤖 Assistant")

            if timestamp:
                lines.append(f"*{timestamp}*\n")

            lines.append(content)
            lines.append("\n---\n")

        markdown_text = "\n".join(lines)

        return Response(
            markdown_text,
            mimetype="text/markdown",
            headers={
                "Content-Disposition": f"attachment; filename=conversation_{session_id}.md"
            }
        )
    else:
        # JSON format
        export_data = {
            "session_id": session_id,
            "title": session.get("title") if session else None,
            "summary": session.get("summary") if session else None,
            "created_at": session.get("created_at").isoformat() if session and session.get("created_at") else None,
            "messages": [
                {
                    "role": t["role"],
                    "content": t["content"],
                    "created_at": t["created_at"].isoformat() if t.get("created_at") else None,
                }
                for t in turns
            ]
        }

        return Response(
            json.dumps(export_data, indent=2),
            mimetype="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=conversation_{session_id}.json"
            }
        )

@app.route("/api/sessions/<session_id>/fork", methods=["POST"])
def fork_session(session_id):
    """
    Create a new session as a fork/branch of the current one.
    Copies all messages up to an optional turn_index (or all if not specified).
    Request body (optional): { "turn_index": 5, "title": "Forked conversation" }
    """
    data = request.json or {}
    turn_index = data.get("turn_index")
    new_title = data.get("title")

    # Generate new session ID
    import uuid
    new_session_id = str(uuid.uuid4())

    # Get original messages
    original_turns = memory.get_recent_turns(session_id, limit=10000)

    # If turn_index specified, only copy up to that point
    if turn_index is not None:
        turns_to_copy = original_turns[:turn_index + 1]
    else:
        turns_to_copy = original_turns

    # Create new session and copy turns
    for turn in turns_to_copy:
        memory.save_turn(
            new_session_id,
            turn["role"],
            turn["content"]
        )

    # Set title for new session
    if new_title:
        memory.save_session_title(new_session_id, new_title)
    elif len(turns_to_copy) > 0:
        # Copy title from original session
        session_data = memory.list_sessions()
        original = next((s for s in session_data if s["id"] == session_id), None)
        if original and original.get("title"):
            memory.save_session_title(new_session_id, f"{original['title']} (fork)")

    return jsonify({
        "session_id": new_session_id,
        "status": "ok",
        "messages_copied": len(turns_to_copy)
    })

@app.route("/api/sessions/<session_id>/generate-title", methods=["POST"])
def generate_session_title(session_id):
    """
    Generate an AI-powered title for a session based on its first few messages.
    Returns: { "title": "Generated title" }
    """
    # Get first few turns to understand the conversation topic
    turns = memory.get_recent_turns(session_id, limit=6)

    if not turns or len(turns) == 0:
        return jsonify({"title": "New chat"}), 200

    # Build a concise summary of the conversation start
    conversation_text = ""
    for turn in turns[:4]:  # Use first 2 exchanges (4 turns max)
        role = "User" if turn["role"] == "user" else "Assistant"
        content = turn["content"][:200]  # Limit content length
        conversation_text += f"{role}: {content}\n"

    # Use a provider to generate the title
    try:
        # Build minimal context for title generation
        title_prompt = f"""Based on this conversation, generate a short, descriptive title (maximum 6 words).
Only respond with the title, nothing else.

Conversation:
{conversation_text}

Title:"""

        router_context = {
            "text": title_prompt,
            "session_id": session_id,
            "memory": memory,
            "forced_provider": None,  # Let router pick best provider
            "force_intent": "general"  # Force general intent to avoid action routing
        }

        result = route_request(router_context)
        generated_title = result.get("text", "New chat").strip()

        # Clean up the title
        # Remove quotes if present
        generated_title = generated_title.strip('"').strip("'").strip()
        # Limit length
        if len(generated_title) > 60:
            generated_title = generated_title[:57] + "..."

        # Save the title
        memory.save_session_title(session_id, generated_title)

        return jsonify({"title": generated_title})

    except Exception as e:
        logging.error(f"Failed to generate title: {e}")
        # Fallback to first user message as title
        first_user = next((t for t in turns if t["role"] == "user"), None)
        if first_user:
            fallback_title = first_user["content"][:60]
            if len(first_user["content"]) > 60:
                fallback_title += "..."
            memory.save_session_title(session_id, fallback_title)
            return jsonify({"title": fallback_title})

        return jsonify({"title": "New chat"})

# Provider Management APIs

@app.route("/api/providers", methods=["GET"])
def list_providers():
    providers = provider_registry.list()

    # Never expose API keys
    safe = []
    for p in providers:
        safe.append({
            "id": p["id"],
            "name": p["name"],
            "type": p["type"],
            "base_url": p.get("base_url"),
            "model": p.get("model"),
            "enabled": p.get("enabled", True),
        })

    return jsonify(safe)

@app.route("/api/providers", methods=["POST"])
def upsert_provider():
    data = request.json

    provider_registry.upsert({
        "id": data["id"],
        "name": data["name"],
        "type": data["type"],
        "base_url": data.get("base_url"),
        "model": data.get("model"),
        "api_key": data.get("api_key"),
        "enabled": data.get("enabled", True),
    })

    # Initialize metadata for new providers
    memory.init_provider_metadata(data["id"])

    return jsonify({"status": "ok"})

@app.route("/api/providers/<provider_id>", methods=["DELETE"])
def delete_provider(provider_id):
    provider_registry.delete(provider_id)

    # Clean up metadata and request logs for deleted provider
    memory.delete_provider_metadata(provider_id)

    return jsonify({"status": "ok"})

# =============================
# Debug Settings API
# =============================

@app.route("/api/settings/debug", methods=["GET"])
def get_debug_setting():
    # Read from preferences, not routing
    prefs = memory.get_all("local")
    value = prefs.get("debug_enabled")

    if value is None:
        enabled = False
    else:
        enabled = str(value).lower() == "true"

    return jsonify({"enabled": enabled})


@app.route("/api/settings/debug", methods=["POST"])
def set_debug_setting():
    data = request.json
    enabled = bool(data.get("enabled", False))

    # Persist as preference
    memory.remember(
        user_id="local",
        key="debug_enabled",
        value=str(enabled).lower()
    )

    return jsonify({"status": "ok", "enabled": enabled})

# =============================
# System Prompt Configuration API
# =============================

@app.route("/api/settings/system-prompt", methods=["GET"])
def get_system_prompt_settings():
    config = memory.get_system_prompt_config("local")
    return jsonify(config)


@app.route("/api/settings/system-prompt", methods=["POST"])
def update_system_prompt_settings():
    data = request.json

    # Only allow updating specific fields
    allowed_fields = ["persona_name", "tone", "style_rules", "custom_instructions"]
    updates = {k: v for k, v in data.items() if k in allowed_fields}

    if not updates:
        return jsonify({"error": "No valid fields to update"}), 400

    memory.update_system_prompt_config("local", **updates)
    return jsonify({"status": "ok"})

# =============================
# Authentication API
# =============================

from auth import hash_password, verify_password, generate_session_token

@app.route("/api/auth/login", methods=["POST"])
def login():
    """
    Login endpoint.
    Expects: { "username": "...", "password": "..." }
    Returns: { "token": "..." } on success
    """
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    # Get user
    user = memory.get_user_by_username(username)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    # Check if user is enabled
    if not user["is_enabled"]:
        return jsonify({"error": "Account disabled"}), 401

    # Verify password
    if not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    # Create session token
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)  # 7 day session

    memory.create_auth_session(token, user["id"], expires_at)

    return jsonify({
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"]
        }
    })

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """
    Logout endpoint.
    Expects: Authorization: Bearer <token>
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "No token provided"}), 400

    token = auth_header.split(" ")[1]
    memory.delete_auth_session(token)

    return jsonify({"status": "ok"})

@app.route("/api/auth/verify", methods=["GET"])
def verify_session():
    """
    Verify if current session is valid.
    Expects: Authorization: Bearer <token>
    Returns: { "valid": true, "user": {...} } or { "valid": false }
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"valid": False})

    token = auth_header.split(" ")[1]

    # Get session
    session = memory.get_auth_session(token)
    if not session:
        return jsonify({"valid": False})

    # Check expiration
    if session["expires_at"] < datetime.utcnow():
        memory.delete_auth_session(token)
        return jsonify({"valid": False})

    # Get user
    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"valid": False})

    return jsonify({
        "valid": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "is_admin": user["is_admin"]
        }
    })

@app.route("/api/auth/change-password", methods=["POST"])
def change_password():
    """
    Change password endpoint.
    Expects: Authorization: Bearer <token>
    Body: { "current_password": "...", "new_password": "..." }
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Verify session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get passwords from request
    data = request.json
    current_password = data.get("current_password")
    new_password = data.get("new_password")

    if not current_password or not new_password:
        return jsonify({"error": "Current and new password required"}), 400

    # Verify current password
    if not verify_password(current_password, user["password_hash"]):
        return jsonify({"error": "Current password incorrect"}), 401

    # Validate new password
    if len(new_password) < 4:
        return jsonify({"error": "New password must be at least 4 characters"}), 400

    # Update password
    new_hash = hash_password(new_password)
    memory.update_user_password(user["id"], new_hash)

    return jsonify({"status": "ok"})


# =============================
# Mode Management Endpoints
# =============================

@app.route("/api/mode", methods=["GET"])
def get_mode():
    """Get user's current mode."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get mode
    mode_config = memory.get_user_mode(user["id"])
    return jsonify(mode_config)


@app.route("/api/mode", methods=["POST"])
def set_mode():
    """Set user's current mode."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get requested mode
    data = request.json
    mode = data.get("mode")

    if mode not in ["work", "personal"]:
        return jsonify({"error": "Mode must be 'work' or 'personal'"}), 400

    # Set mode
    memory.set_user_mode(user["id"], mode)
    return jsonify({"status": "ok", "mode": mode})


@app.route("/api/mode/settings", methods=["GET"])
def get_mode_settings_endpoint():
    """Get all mode settings for the user."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get all mode settings
    settings = memory.get_all_mode_settings(user["id"])
    return jsonify(settings)


@app.route("/api/mode/settings/<mode>", methods=["GET"])
def get_mode_setting(mode):
    """Get settings for a specific mode."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    if mode not in ["work", "personal"]:
        return jsonify({"error": "Mode must be 'work' or 'personal'"}), 400

    # Get mode settings
    settings = memory.get_mode_settings(user["id"], mode)
    return jsonify(settings if settings else {})


@app.route("/api/mode/settings/<mode>", methods=["POST"])
def update_mode_settings(mode):
    """Update settings for a specific mode."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    if mode not in ["work", "personal"]:
        return jsonify({"error": "Mode must be 'work' or 'personal'"}), 400

    # Get settings from request
    data = request.json
    system_prompt_override = data.get("system_prompt_override")
    preferred_provider_id = data.get("preferred_provider_id")
    tone = data.get("tone")

    # Update settings
    memory.create_or_update_mode_settings(
        user["id"],
        mode,
        system_prompt_override=system_prompt_override,
        preferred_provider_id=preferred_provider_id,
        tone=tone
    )

    return jsonify({"status": "ok"})


# =============================
# Work Mode Sub-Tab Endpoints
# =============================

@app.route("/api/mode/work/subtab/<subtab>", methods=["GET"])
def get_work_subtab(subtab):
    """Get configuration for a specific work subtab."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    if subtab not in ["conversation", "email", "code"]:
        return jsonify({"error": "Subtab must be 'conversation', 'email', or 'code'"}), 400

    # Get subtab config
    config = memory.get_work_subtab_config(user["id"], subtab)
    return jsonify(config if config else {})


@app.route("/api/mode/work/subtab/<subtab>", methods=["POST"])
def update_work_subtab(subtab):
    """Update configuration for a specific work subtab."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    if subtab not in ["conversation", "email", "code"]:
        return jsonify({"error": "Subtab must be 'conversation', 'email', or 'code'"}), 400

    # Get config from request
    data = request.json
    import json as json_module
    config_json = json_module.dumps(data)

    # Update subtab config
    memory.update_work_subtab_config(user["id"], subtab, config_json)
    return jsonify({"status": "ok"})


@app.route("/api/mode/work/subtabs", methods=["GET"])
def get_all_work_subtabs():
    """Get all work subtab configurations."""
    # Get token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]

    # Validate session
    session = memory.get_auth_session(token)
    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get all subtab configs
    configs = memory.get_all_work_subtab_configs(user["id"])
    return jsonify(configs)


# =============================
# M365 Authentication API
# =============================

@app.route("/api/m365/auth/start", methods=["POST"])
def start_m365_auth():
    """Initiate M365 OAuth device flow."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Import M365OAuth
    from auth.m365_oauth import M365OAuth

    # Check if configured
    if not M365OAuth.is_configured():
        return jsonify({
            "error": "M365 not configured",
            "instructions": M365OAuth.get_configuration_instructions()
        }), 500

    try:
        # Initiate device flow
        device_info = M365OAuth.initiate_device_flow()

        # Store device_code in session for later polling
        # (In a production system, you might want to use Redis or similar)
        # For now, we'll expect the frontend to pass it back

        return jsonify({
            "user_code": device_info["user_code"],
            "verification_url": device_info["verification_url"],
            "message": device_info["message"],
            "expires_in": device_info["expires_in"],
            "interval": device_info["interval"],
            "device_code": device_info["device_code"]  # Frontend will need this for polling
        })

    except Exception as e:
        logging.error(f"[API] M365 auth start failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/m365/auth/poll", methods=["POST"])
def poll_m365_auth():
    """Poll for M365 OAuth token completion."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    data = request.json
    device_code = data.get("device_code")

    if not device_code:
        return jsonify({"error": "device_code required"}), 400

    from auth.m365_oauth import M365OAuth

    try:
        # Poll for token (single attempt)
        import requests
        payload = {
            "client_id": M365OAuth.CLIENT_ID,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": device_code
        }

        response = requests.post(M365OAuth.TOKEN_URL, data=payload, timeout=10)

        if response.status_code == 200:
            # Success! Store credentials
            token_data = response.json()

            memory.store_m365_credentials(
                user_id=user["id"],
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_at=datetime.utcnow() + timedelta(seconds=token_data["expires_in"]),
                scope=token_data.get("scope")
            )

            # Create M365 service provider entry
            import json as json_module
            provider_id = memory.store_service_provider(
                user_id=user["id"],
                name="Microsoft 365",
                category="calendar",
                provider_type="m365",
                capabilities=json_module.dumps([
                    "read_calendar",
                    "create_calendar_event",
                    "update_calendar_event",
                    "delete_calendar_event",
                    "read_email",
                    "send_email",
                    "draft_email"
                ]),
                auth_method="oauth2",
                trust_level="confirm"
            )

            logging.info(f"[API] M365 connected successfully for user {user['id']}")

            return jsonify({
                "status": "success",
                "message": "M365 connected successfully",
                "provider_id": provider_id
            })

        # Check error
        error_data = response.json()
        error = error_data.get("error")

        if error == "authorization_pending":
            # Still waiting
            return jsonify({"status": "pending"}), 202
        elif error == "authorization_declined":
            return jsonify({"status": "declined", "error": "User declined authorization"}), 400
        elif error == "expired_token":
            return jsonify({"status": "expired", "error": "Device code expired"}), 400
        else:
            logging.error(f"[API] M365 auth error: {error}")
            return jsonify({"status": "error", "error": error}), 400

    except Exception as e:
        logging.error(f"[API] M365 auth poll failed: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/m365/status", methods=["GET"])
def get_m365_status():
    """Get M365 connection status."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Check for M365 credentials
    creds = memory.get_m365_credentials(user["id"])

    if not creds:
        return jsonify({"connected": False})

    return jsonify({
        "connected": True,
        "is_valid": creds.get("is_valid"),
        "expires_at": creds.get("expires_at").isoformat() if creds.get("expires_at") else None,
        "user_principal_name": creds.get("user_principal_name"),
        "token_expires_soon": (
            creds.get("expires_at") < datetime.utcnow() + timedelta(minutes=10)
            if creds.get("expires_at") else True
        )
    })


@app.route("/api/m365/disconnect", methods=["POST"])
def disconnect_m365():
    """Disconnect M365 account."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Delete M365 credentials (not just invalidate)
    memory.delete_m365_credentials(user["id"])

    # Remove M365 service providers
    providers = memory.get_service_providers(user["id"])
    for provider in providers:
        if provider.get("provider_type") == "m365":
            memory.delete_service_provider(provider["id"], user["id"])

    logging.info(f"[API] M365 disconnected for user {user['id']}")

    return jsonify({"status": "disconnected"})


# =============================
# Service Providers API
# =============================

@app.route("/api/service-providers", methods=["GET"])
def get_service_providers():
    """Get all service providers for the authenticated user."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get optional category filter
    category = request.args.get("category")

    # Get service providers
    providers = memory.get_service_providers(user["id"], category=category)

    return jsonify({"providers": providers})


@app.route("/api/service-providers", methods=["POST"])
def create_service_provider():
    """Create a new service provider."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get request data
    data = request.get_json()

    # Required fields
    name = data.get("name")
    category = data.get("category")
    provider_type = data.get("provider_type")

    if not name or not category or not provider_type:
        return jsonify({"error": "Missing required fields: name, category, provider_type"}), 400

    # Create service provider
    try:
        provider_id = memory.store_service_provider(
            user_id=user["id"],
            name=name,
            category=category,
            provider_type=provider_type,
            capabilities=data.get("capabilities"),
            api_base_url=data.get("api_base_url"),
            auth_method=data.get("auth_method"),
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            token_expires_at=data.get("token_expires_at"),
            trust_level=data.get("trust_level", "manual"),
            booking_method=data.get("booking_method"),
            preferred_for_category=data.get("preferred_for_category", False),
            additional_metadata=data.get("additional_metadata")
        )

        logging.info(f"[API] Service provider created: {provider_id} for user {user['id']}")

        return jsonify({
            "success": True,
            "provider_id": provider_id,
            "message": f"Service provider '{name}' created successfully"
        }), 201

    except Exception as e:
        logging.error(f"[API] Failed to create service provider: {e}")
        return jsonify({"error": f"Failed to create service provider: {str(e)}"}), 500


@app.route("/api/service-providers/<int:provider_id>", methods=["GET"])
def get_service_provider(provider_id):
    """Get a single service provider by ID."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get service provider
    provider = memory.get_service_provider(provider_id)

    if not provider:
        return jsonify({"error": "Service provider not found"}), 404

    # Verify ownership
    if provider["user_id"] != user["id"]:
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({"provider": provider})


@app.route("/api/service-providers/<int:provider_id>", methods=["PUT"])
def update_service_provider(provider_id):
    """Update a service provider."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get existing provider
    provider = memory.get_service_provider(provider_id)

    if not provider:
        return jsonify({"error": "Service provider not found"}), 404

    # Verify ownership
    if provider["user_id"] != user["id"]:
        return jsonify({"error": "Unauthorized"}), 403

    # Get update data
    data = request.get_json()

    # Update service provider
    try:
        memory.update_service_provider(
            provider_id=provider_id,
            name=data.get("name"),
            category=data.get("category"),
            provider_type=data.get("provider_type"),
            capabilities=data.get("capabilities"),
            api_base_url=data.get("api_base_url"),
            auth_method=data.get("auth_method"),
            access_token=data.get("access_token"),
            refresh_token=data.get("refresh_token"),
            token_expires_at=data.get("token_expires_at"),
            trust_level=data.get("trust_level"),
            booking_method=data.get("booking_method"),
            preferred_for_category=data.get("preferred_for_category"),
            additional_metadata=data.get("additional_metadata"),
            is_enabled=data.get("is_enabled")
        )

        logging.info(f"[API] Service provider {provider_id} updated by user {user['id']}")

        return jsonify({
            "success": True,
            "message": "Service provider updated successfully"
        })

    except Exception as e:
        logging.error(f"[API] Failed to update service provider: {e}")
        return jsonify({"error": f"Failed to update service provider: {str(e)}"}), 500


@app.route("/api/service-providers/<int:provider_id>", methods=["DELETE"])
def delete_service_provider(provider_id):
    """Delete a service provider."""
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get provider to verify ownership
    provider = memory.get_service_provider(provider_id)

    if not provider:
        return jsonify({"error": "Service provider not found"}), 404

    # Verify ownership
    if provider["user_id"] != user["id"]:
        return jsonify({"error": "Unauthorized"}), 403

    # Delete service provider
    try:
        memory.delete_service_provider(provider_id, user["id"])

        logging.info(f"[API] Service provider {provider_id} deleted by user {user['id']}")

        return jsonify({
            "success": True,
            "message": "Service provider deleted successfully"
        })

    except Exception as e:
        logging.error(f"[API] Failed to delete service provider: {e}")
        return jsonify({"error": f"Failed to delete service provider: {str(e)}"}), 500


@app.route("/api/health/overview", methods=["GET"])
def get_health_overview():
    """
    Get comprehensive health overview of all system components.

    Returns AI providers, M365 integration, and service providers health status.
    """
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get AI providers with metadata
    providers = memory.list_providers()
    ai_providers = []

    for provider in providers:
        metadata = memory.get_provider_metadata(provider["id"])

        # Handle case where metadata doesn't exist yet
        if not metadata:
            metadata = {
                "total_requests": 0,
                "failed_requests": 0,
                "health_status": "unknown",
                "circuit_breaker_open": False,
                "avg_latency_ms": 0,
                "last_success_at": None,
                "last_failure_at": None
            }

        # Calculate success rate
        total = metadata.get("total_requests", 0)
        failed = metadata.get("failed_requests", 0)
        success_rate = ((total - failed) / total * 100) if total > 0 else 0

        ai_providers.append({
            "id": provider["id"],
            "name": provider["name"],
            "type": provider["type"],
            "model": provider.get("model"),
            "enabled": provider["enabled"],
            "health_status": metadata.get("health_status", "unknown"),
            "circuit_breaker_open": metadata.get("circuit_breaker_open", False),
            "total_requests": total,
            "failed_requests": failed,
            "success_rate": round(success_rate, 2),
            "avg_latency_ms": metadata.get("avg_latency_ms", 0),
            "last_success_at": metadata.get("last_success_at").isoformat() if metadata.get("last_success_at") else None,
            "last_failure_at": metadata.get("last_failure_at").isoformat() if metadata.get("last_failure_at") else None
        })

    # Get M365 integration status
    m365_integration = {"connected": False}
    creds = memory.get_m365_credentials(user["id"])

    if creds:
        expires_at = creds.get("expires_at")
        now = datetime.utcnow()

        # Calculate hours until expiry
        hours_until_expiry = None
        if expires_at:
            delta = expires_at - now
            hours_until_expiry = round(delta.total_seconds() / 3600, 1)

        # Parse scopes
        scopes = []
        if creds.get("scope"):
            scopes = creds["scope"].split(" ")

        m365_integration = {
            "connected": True,
            "account": creds.get("user_principal_name"),
            "token_valid": creds.get("is_valid", False),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "hours_until_expiry": hours_until_expiry,
            "last_refreshed_at": creds.get("last_refreshed_at").isoformat() if creds.get("last_refreshed_at") else None,
            "last_error": creds.get("last_error"),
            "scopes": scopes
        }

    # Get service providers
    service_providers_list = memory.get_service_providers(user["id"])
    service_providers = []

    for sp in service_providers_list:
        # Parse booking URL from metadata
        booking_url = None
        try:
            if sp.get("additional_metadata"):
                metadata = json.loads(sp["additional_metadata"])
                booking_url = metadata.get("booking_url")
        except:
            pass

        service_providers.append({
            "id": sp["id"],
            "name": sp["name"],
            "category": sp["category"],
            "provider_type": sp["provider_type"],
            "is_enabled": sp.get("is_enabled", True),
            "health_status": sp.get("health_status", "unknown"),
            "last_synced_at": sp.get("last_synced_at").isoformat() if sp.get("last_synced_at") else None,
            "booking_url": booking_url
        })

    return jsonify({
        "ai_providers": ai_providers,
        "m365_integration": m365_integration,
        "service_providers": service_providers
    })


@app.route("/api/health/test-m365", methods=["POST"])
def test_m365_health():
    """
    Perform live health check on M365 integration.
    """
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Check if M365 is connected
    creds = memory.get_m365_credentials(user["id"])

    if not creds:
        return jsonify({
            "healthy": False,
            "status": "not_connected",
            "error": "Microsoft 365 account not connected"
        })

    # Perform health check
    try:
        from actions.m365_provider import M365Provider
        import time

        start_time = time.time()

        provider = M365Provider(
            access_token=creds["access_token"],
            refresh_token=creds["refresh_token"],
            expires_at=creds["expires_at"],
            user_id=user["id"],
            memory_store=memory
        )

        health = provider.check_health()

        response_time_ms = int((time.time() - start_time) * 1000)
        health["response_time_ms"] = response_time_ms

        return jsonify(health)

    except Exception as e:
        logging.error(f"[API] M365 health check failed: {e}")
        return jsonify({
            "healthy": False,
            "status": "error",
            "last_check": datetime.utcnow().isoformat(),
            "error": str(e)
        })


@app.route("/api/calendar/query", methods=["POST"])
def query_calendar():
    """
    Query calendar using natural language.

    Example request:
    POST /api/calendar/query
    {
        "text": "What's on my calendar tomorrow?",
        "session_id": "session_123"
    }

    Returns calendar events or error message.
    """
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get request data
    payload = request.json
    text = payload.get("text", "")
    session_id = payload.get("session_id", "default")

    if not text:
        return jsonify({"error": "No query text provided"}), 400

    # Build context for router
    context = {
        "text": text,
        "session_id": session_id,
        "user_id": user["id"],
        "memory": memory,
    }

    # Route through main router (will detect calendar intent and route to ActionRouter)
    try:
        result = route_request(context)

        # Log to conversation history
        context_manager.update(session_id, text, result, provider_registry)

        return jsonify(result)

    except Exception as e:
        logging.error(f"[API] Calendar query failed: {e}")
        return jsonify({
            "error": "Calendar query failed",
            "details": str(e)
        }), 500


@app.route("/api/confirmations/pending", methods=["GET"])
def get_pending_confirmations():
    """
    Get all pending confirmations for the authenticated user.

    Returns list of confirmations awaiting user approval.
    """
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get pending confirmations
    try:
        confirmations = confirmation_manager.get_pending_confirmations(user["id"])

        # Format for frontend
        formatted_confirmations = []
        for conf in confirmations:
            formatted_confirmations.append({
                "confirmation_id": conf.get("id"),
                "action_id": conf.get("action_id"),
                "message": conf.get("confirmation_message"),
                "action_type": conf.get("action_type"),
                "category": conf.get("category"),
                "created_at": conf.get("created_at").isoformat() if conf.get("created_at") else None,
                "expires_at": conf.get("expires_at").isoformat() if conf.get("expires_at") else None,
            })

        return jsonify({
            "confirmations": formatted_confirmations,
            "count": len(formatted_confirmations)
        })

    except Exception as e:
        logging.error(f"[API] Get pending confirmations failed: {e}")
        return jsonify({
            "error": "Failed to get confirmations",
            "details": str(e)
        }), 500


@app.route("/api/confirmations/<int:confirmation_id>/approve", methods=["POST"])
def approve_confirmation(confirmation_id):
    """
    Approve a confirmation and execute the action.

    Path parameters:
        confirmation_id: ID of the confirmation to approve
    """
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Approve confirmation
    try:
        result = confirmation_manager.approve_confirmation(confirmation_id, user["id"])

        if result["status"] == "success":
            return jsonify({
                "status": "approved",
                "message": result["message"],
                "action_result": result.get("action_result")
            })
        else:
            return jsonify({
                "status": "error",
                "message": result["message"]
            }), 400

    except Exception as e:
        logging.error(f"[API] Approve confirmation failed: {e}")
        return jsonify({
            "error": "Failed to approve confirmation",
            "details": str(e)
        }), 500


@app.route("/api/confirmations/<int:confirmation_id>/reject", methods=["POST"])
def reject_confirmation(confirmation_id):
    """
    Reject a confirmation request.

    Path parameters:
        confirmation_id: ID of the confirmation to reject

    Body (optional):
        {
            "reason": "User's reason for rejection"
        }
    """
    # Get authenticated user
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    token = auth_header.split(" ")[1]
    session = memory.get_auth_session(token)

    if not session or session["expires_at"] < datetime.utcnow():
        return jsonify({"error": "Invalid session"}), 401

    user = memory.get_user_by_id(session["user_id"])
    if not user or not user["is_enabled"]:
        return jsonify({"error": "User not found"}), 401

    # Get reason if provided
    payload = request.json or {}
    reason = payload.get("reason")

    # Reject confirmation
    try:
        result = confirmation_manager.reject_confirmation(confirmation_id, user["id"], reason)

        if result["status"] == "success":
            return jsonify({
                "status": "rejected",
                "message": result["message"]
            })
        else:
            return jsonify({
                "status": "error",
                "message": result["message"]
            }), 400

    except Exception as e:
        logging.error(f"[API] Reject confirmation failed: {e}")
        return jsonify({
            "error": "Failed to reject confirmation",
            "details": str(e)
        }), 500


def debug_log(message):
    try:
        prefs = memory.get_all("local")
        enabled = str(prefs.get("debug_enabled", "false")).lower() == "true"
        if enabled:
            logging.info(f"[DEBUG] {message}")
    except Exception as e:
        logging.warning(f"[DEBUG-LOGGING-ERROR] {e}")

        

if __name__ == "__main__":
    print("THEO backend starting on port 1066")
    app.run(host="0.0.0.0", port=1066, debug=True)