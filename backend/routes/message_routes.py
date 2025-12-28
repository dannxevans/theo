"""
Message routes.

Provides chat and streaming endpoints for message processing.
"""

from flask import Blueprint, jsonify, request, Response, stream_with_context
from datetime import datetime
import json
import logging

message_bp = Blueprint('message', __name__, url_prefix='/api')


@message_bp.route("/chat", methods=["POST"])
def chat():
    """
    Process a chat message (non-streaming).
    Request body: { "session_id": "...", "text": "..." }
    Returns: { "text": "...", "provider": "...", "model": "...", ... }
    """
    from app import context_manager, provider_registry
    from core.router import route_request

    payload = request.json
    session_id = payload.get("session_id", "default")
    text = payload.get("text", "")

    context = context_manager.build_context(session_id, text)
    result = route_request(context)

    # Pass the full result object so metadata can be extracted
    context_manager.update(session_id, text, result, provider_registry)
    return jsonify(result)


@message_bp.route("/stream/<session_id>")
def stream_chat_sse(session_id):
    """
    Process a chat message with Server-Sent Events streaming.
    Query params: text, forced_provider, token, work_subtab
    Streams response in chunks with metadata at end.
    """
    from app import memory, context_manager, provider_registry
    from core.router import route_request

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
            if user_id:
                router_context["user_id"] = user_id
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
