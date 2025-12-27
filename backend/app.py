# import eventlet
# eventlet.monkey_patch()
import logging
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from core.router import route_request, set_provider_registry, set_context_manager
from core.context import ContextManager
from core.memory import MemoryStore
from config import Config
from core.provider_registry import ProviderRegistry
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

            # Pass the full result object so metadata can be extracted
            context_manager.update(session_id, text, result, provider_registry)

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
            "forced_provider": None  # Let router pick best provider
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