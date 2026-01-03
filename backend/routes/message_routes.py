"""
Message routes.

Provides chat and streaming endpoints for message processing.
"""

from flask import Blueprint, jsonify, request, Response, stream_with_context
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from auth.password import require_auth
from datetime import datetime
import json
import logging

message_bp = Blueprint('message', __name__, url_prefix='/api')


@message_bp.route("/chat", methods=["POST"])
@require_auth(lambda: __import__('app').memory)
def chat():
    """
    Process a chat message (non-streaming).
    Requires authentication via session token or API key.
    Request body: { "session_id": "...", "text": "..." }
    Returns: { "text": "...", "provider": "...", "model": "...", ... }
    """
    from app import context_manager, provider_registry
    from core.router import route_request

    payload = request.json
    session_id = payload.get("session_id", "default")
    text = payload.get("text", "").strip()

    # Validate text is not empty
    if not text:
        return jsonify({"error": "Message text cannot be empty"}), 400

    # Get authenticated user from request context (set by require_auth decorator)
    user_id = request.user.get("id") if hasattr(request, 'user') else None

    context = context_manager.build_context(session_id, text, user_id=user_id)
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

    # CRITICAL DEBUG: Log immediately when endpoint is hit
    logging.warning(f"[STREAM-ENTRY] ===== STREAMING ENDPOINT HIT ===== session_id={session_id}")
    logging.warning(f"[STREAM-ENTRY] Request headers: {dict(request.headers)}")
    logging.warning(f"[STREAM-ENTRY] Request args: {dict(request.args)}")
    logging.warning(f"[STREAM-ENTRY] Request method: {request.method}")
    logging.warning(f"[STREAM-ENTRY] Request path: {request.path}")

    text = request.args.get("text", "").strip()
    forced_provider = request.args.get("forced_provider")

    # Debug logging for Siri shortcuts troubleshooting
    logging.warning(f"[STREAM] Received request - text param: '{request.args.get('text')}', stripped: '{text}', all params: {dict(request.args)}")

    # Validate text is not empty
    if not text:
        def error_stream():
            yield f"event: error\ndata: {json.dumps({'error': 'Message text cannot be empty'})}\n\n"
        return Response(
            stream_with_context(error_stream()),
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    def event_stream():
        try:
            # Get user from auth token (check both header and query param)
            from auth.password import _validate_session_auth, _validate_api_key_auth

            auth_header = request.headers.get("Authorization")
            token = None
            user_id = None
            user = None

            logging.warning(f"[STREAM-AUTH] Authorization header: {auth_header}")

            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            elif request.args.get("token"):
                token = request.args.get("token")

            logging.warning(f"[STREAM-AUTH] Extracted token: {token[:20] if token else 'None'}...")

            if token:
                # Check if it's an API key (starts with "theo_")
                if token.startswith("theo_"):
                    logging.warning(f"[STREAM-AUTH] Attempting API key authentication")
                    user = _validate_api_key_auth(memory, token)
                    if user:
                        user_id = user["id"]
                        logging.warning(f"[STREAM-AUTH] API key authenticated - user_id: {user_id}")
                    else:
                        logging.warning(f"[STREAM-AUTH] API key authentication FAILED")
                else:
                    # Session-based authentication
                    logging.warning(f"[STREAM-AUTH] Attempting session token authentication")
                    session = memory.get_auth_session(token)
                    if session and session["expires_at"] >= datetime.utcnow():
                        user_id = session["user_id"]
                        logging.warning(f"[STREAM-AUTH] Session authenticated - user_id: {user_id}")
                    else:
                        logging.warning(f"[STREAM-AUTH] Session authentication FAILED - invalid or expired")
            else:
                logging.warning(f"[STREAM-AUTH] No token provided in request")

            context = context_manager.build_context(session_id, text, user_id=user_id)

            router_context = dict(context)
            router_context["text"] = text
            router_context["session_id"] = session_id
            router_context["memory"] = memory
            if user_id:
                router_context["user_id"] = user_id
            if forced_provider:
                router_context["forced_provider"] = forced_provider

            # Initialize current_mode default (will be overridden if user is authenticated)
            current_mode = "personal"

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

                    # Add mode and subtab to router_context for intent classification
                    router_context["mode"] = current_mode
                    router_context["subtab"] = work_subtab

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
                            context_prefix = f"You are helping rewrite emails with a {tone} tone. IMPORTANT: Only output the rewritten message body content. Do NOT include greetings, salutations, sign-offs, signatures, subject lines, or any meta-commentary explaining the rewrite. The user will add their own email formatting and signature. Output ONLY the refined message body that can be directly inserted into an email."

                        # Check for subtab-specific preferred provider (only if not already forced)
                        subtab_preferred_provider = config.get("preferred_provider_id")
                        if subtab_preferred_provider and not forced_provider:
                            router_context["forced_provider"] = str(subtab_preferred_provider)
                            logging.info(f"[MODE] Using subtab preferred provider: {subtab_preferred_provider}")
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
                    router_context["mode"] = current_mode  # Add mode even for personal
                    if mode_context_prefix:
                        router_context["subtab_context_prefix"] = mode_context_prefix
                        logging.info(f"[MODE] Set subtab_context_prefix for {current_mode} mode: {mode_context_prefix[:100]}")
            else:
                logging.warning(f"[MODE] No user_id - skipping mode context injection")
                # current_mode already defaults to "personal" (set on line 86)

            # Apply PII redaction for work mode (OFFICIAL)
            pii_redaction_log = None
            filtered_text = text  # Use filtered_text to avoid scope issues
            if current_mode == "work" and user_id:
                mode_settings = memory.get_mode_settings(user_id, "work")
                if mode_settings and mode_settings.get("pii_filtering_enabled"):
                    from core.pii_filter import PIIFilter
                    pii_filter = PIIFilter(mode_settings)
                    filtered_text, pii_redaction_log = pii_filter.filter_text(text)

                    if pii_redaction_log:
                        logging.info(f"[PII] Redacted {len(pii_redaction_log)} PII items from user message")
                        # Update text in router_context
                        router_context["text"] = filtered_text

            # Store mode and user_id for context manager
            router_context["session_mode"] = current_mode
            router_context["session_user_id"] = user_id

            # Check for routine triggers
            routine_name = None
            routine_actions_list = None

            try:
                from core.routines import detect_routine, execute_routine, consolidate_results
                from app import action_router

                # Get user routines if authenticated
                user_routines = None
                if user_id:
                    user_routines = memory.get_user_routines(user_id)

                detected_routine_name, routine_def = detect_routine(filtered_text, user_routines)

                if detected_routine_name and routine_def:
                    logging.info(f"[ROUTINES] Detected routine: {detected_routine_name}")

                    # Build routine execution context
                    routine_context = {
                        "session_id": session_id,
                        "user_id": user_id,
                        "mode": current_mode,
                        "action_router": action_router,
                        "memory": memory
                    }

                    # Execute routine actions
                    execution_results = execute_routine(routine_def, routine_context)

                    # Consolidate results using lightweight LLM
                    result = consolidate_results(
                        routine_def,
                        execution_results,
                        route_request,
                        memory,
                        user_id
                    )

                    # Store routine metadata for database
                    routine_name = detected_routine_name
                    routine_actions_list = execution_results.get("actions", [])

                else:
                    # Normal LLM routing
                    result = route_request(router_context)

            except Exception as e:
                logging.error(f"[ROUTINES] Routine execution failed: {e}", exc_info=True)
                # Fall back to normal LLM routing
                result = route_request(router_context)

            full_text = result.get("text", "")
            chunk_size = 32

            for i in range(0, len(full_text), chunk_size):
                chunk = full_text[i:i + chunk_size]
                yield f"data: {json.dumps({'token': chunk})}\n\n"

            # Save the turn to database BEFORE sending end event
            # This ensures metadata is persisted before frontend reloads messages
            context_manager.update(session_id, filtered_text, result, provider_registry, mode=current_mode, user_id=user_id, routine_name=routine_name, routine_actions=routine_actions_list)

            # Send metadata at end of stream
            end_payload = {
                "provider": result.get("provider"),
                "model": result.get("model"),
                "task_type": result.get("task_type"),
                "fallback_reason": result.get("fallback_reason"),
                "routing": result.get("routing"),
            }

            # Include debug instruction if present
            if result.get("debug_instruction"):
                end_payload["debug_instruction"] = result.get("debug_instruction")

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


@message_bp.route("/proactive/dismiss/<int:turn_id>", methods=["POST"])
def dismiss_proactive_notification(turn_id):
    """
    Dismiss a proactive notification.
    URL param: turn_id (the turn ID to dismiss)
    Requires authentication.
    Returns: { "success": true/false, "message": "..." }
    """
    from app import memory
    from flask import g
    from core.proactive.message_poster import dismiss_proactive_message

    # Get authenticated user
    user_id = g.get('user_id')
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required"}), 401

    # Dismiss the message
    success = dismiss_proactive_message(memory, turn_id, user_id)

    if success:
        return jsonify({"success": True, "message": "Notification dismissed"})
    else:
        return jsonify({"success": False, "message": "Failed to dismiss notification"}), 400
