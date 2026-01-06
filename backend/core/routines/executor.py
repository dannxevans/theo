"""
Routine executor module.

Executes routine actions by delegating to existing action handlers.
"""

import logging
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from typing import Dict, Any, List


def execute_routine(routine_def, context):
    """
    Execute a routine by running its defined actions.

    Args:
        routine_def: Routine definition dict
        context: Execution context containing:
            - session_id: Session ID
            - user_id: User ID
            - mode: Session mode ("work" or "personal")
            - action_router: ActionRouter instance
            - memory: MemoryStore instance

    Returns:
        Dict with:
            - routine_name: Name of the routine
            - actions: List of action results
            - success_count: Number of successful actions
            - failure_count: Number of failed actions
            - partial_success: Boolean indicating if some actions failed
    """
    session_id = context.get("session_id")
    user_id = context.get("user_id", DEFAULT_USER_ID)
    mode = context.get("mode", "personal")
    action_router = context.get("action_router")
    memory = context.get("memory")

    routine_name = routine_def.get("name", "Unnamed Routine")
    actions = routine_def.get("actions", [])

    logging.info(f"[ROUTINES] Executing routine '{routine_name}' with {len(actions)} actions")

    action_results = []
    success_count = 0
    failure_count = 0

    for action in actions:
        action_type = action.get("type")
        action_description = action.get("description", action_type)
        action_params = action.get("params", {})
        custom_prompt = action.get("customPrompt")

        logging.info(f"[ROUTINES] Executing action: {action_type}")

        try:
            result = _execute_action(
                action_type,
                action_params,
                session_id,
                user_id,
                mode,
                action_router,
                memory,
                custom_prompt=custom_prompt,
                action_description=action_description
            )

            action_results.append({
                "type": action_type,
                "description": action_description,
                "status": "success",
                "result": result
            })

            success_count += 1
            logging.info(f"[ROUTINES] Action {action_type} completed successfully")

        except Exception as e:
            logging.error(f"[ROUTINES] Action {action_type} failed: {e}")

            action_results.append({
                "type": action_type,
                "description": action_description,
                "status": "failed",
                "error": str(e)
            })

            failure_count += 1

    return {
        "routine_name": routine_name,
        "actions": action_results,
        "success_count": success_count,
        "failure_count": failure_count,
        "partial_success": failure_count > 0 and success_count > 0
    }


def _execute_action(action_type, params, session_id, user_id, mode, action_router, memory, custom_prompt=None, action_description=None):
    """
    Execute a single action by delegating to the action router.

    Args:
        action_type: Type of action (e.g., "calendar_read", "email_check", "custom_action")
        params: Action parameters
        session_id: Session ID
        user_id: User ID
        mode: Session mode
        action_router: ActionRouter instance
        memory: MemoryStore instance
        custom_prompt: Custom LLM prompt (for custom_action type)
        action_description: User-provided description (used as query text for some actions)

    Returns:
        Action result dict

    Raises:
        Exception if action fails
    """
    # Handle custom actions separately
    if action_type == "custom_action":
        if not custom_prompt:
            raise ValueError("Custom action requires a custom prompt")

        # Route custom prompt to LLM via router with full context
        from core.router import route_request
        from app import context_manager

        # Build full context including memory facts
        context = context_manager.build_context(session_id, custom_prompt, user_id=user_id)

        route_context = dict(context)
        route_context["text"] = custom_prompt
        route_context["session_id"] = session_id
        route_context["user_id"] = user_id
        route_context["mode"] = mode
        route_context["memory"] = memory
        route_context["force_intent"] = "general"  # Use general intent for custom actions

        result = route_request(route_context)
        return result

    # Map routine action types to action router intents
    action_type_mapping = {
        # Calendar actions
        "calendar_read": "read_calendar",
        "book_appointment": "book_appointment",
        "update_appointment": "update_appointment",
        "cancel_appointment": "cancel_appointment",
        # Email actions
        "email_check": "read_email",
        "email_summary": "read_email",
        "read_email": "read_email",
        "compose_email": "compose_email",
        "email_reply": "email_reply",
        "send_email": "send_email",
        # Task actions
        "tasks_read": "read_tasks",
        "tasks_today": "read_tasks_today",
        "tasks_week": "read_tasks_week",
        "create_task": "create_task",
        "complete_task": "complete_task",
        # Weather and routing
        "weather": "weather",
        "route": "routing",
        # WHOOP health & fitness actions
        "whoop_sleep": "whoop",
        "whoop_recovery": "whoop",
        "whoop_workout": "whoop",
    }

    intent = action_type_mapping.get(action_type)

    if not intent:
        raise ValueError(f"Unknown action type: {action_type}")

    # Build action context based on action type
    if action_type == "calendar_read":
        timeframe = params.get("timeframe", "today")
        action_context = {
            "text": f"What's on my calendar {timeframe}?",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type == "email_check":
        filter_type = params.get("filter", "all")
        unread_only = params.get("unread_only", False)

        query_text = "Show me my "
        if unread_only:
            query_text += "unread "
        if filter_type == "important":
            query_text += "important "
        query_text += "emails"

        action_context = {
            "text": query_text,
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            "filter": filter_type,
            "unread_only": unread_only
        }

    elif action_type == "email_summary":
        filter_type = params.get("filter", "all")
        exclude_important = params.get("exclude_important", False)

        query_text = "Summarize my "
        if filter_type == "unread":
            query_text += "unread "
        if exclude_important:
            query_text += "non-important "
        query_text += "emails"

        action_context = {
            "text": query_text,
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            "filter": filter_type,
            "exclude_important": exclude_important
        }

    elif action_type == "tasks_read":
        # Read all tasks
        action_context = {
            "text": "Show me my tasks",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type == "tasks_today":
        # Read today's tasks
        action_context = {
            "text": "Today's tasks",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type == "tasks_week":
        # Read this week's tasks
        action_context = {
            "text": "This week's tasks",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type == "create_task":
        # Create a new task
        action_context = {
            "text": params.get("text", "Create a task"),
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            **params
        }

    elif action_type == "complete_task":
        # Complete a task
        action_context = {
            "text": params.get("text", "Complete task"),
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            **params
        }

    elif action_type == "weather":
        # Weather action - route through LLM WITHOUT forcing intent
        # The LLM will resolve location aliases (Home/Work) from memory facts
        # then naturally trigger the weather intent with the resolved location
        from core.router import route_request
        from app import context_manager

        # Use the action description as the query text if provided
        # This allows users to customize the weather query (e.g., "Get weather forecast for Work")
        query_text = action_description if action_description and action_description != "Get weather forecast" else "What's the weather?"

        # Build full context including memory facts (home/work addresses, etc.)
        context = context_manager.build_context(session_id, query_text, user_id=user_id)

        route_context = dict(context)
        route_context["text"] = query_text
        route_context["session_id"] = session_id
        route_context["user_id"] = user_id
        route_context["mode"] = mode
        route_context["memory"] = memory
        # DON'T force intent - let LLM resolve location first

        result = route_request(route_context)
        return result

    elif action_type == "route":
        # Routing action - route through LLM WITHOUT forcing intent
        # The LLM will resolve location aliases (Home/Work) from memory facts
        # then naturally trigger the routing intent with the resolved locations
        from core.router import route_request
        from app import context_manager

        # Use the action description as the query text if provided
        # This allows users to customize the route query (e.g., "Get route from Home to Work")
        query_text = action_description if action_description and action_description != "Get route and traffic information" else "Plan a route to work"

        # Build full context including memory facts (home/work addresses, etc.)
        context = context_manager.build_context(session_id, query_text, user_id=user_id)

        route_context = dict(context)
        route_context["text"] = query_text
        route_context["session_id"] = session_id
        route_context["user_id"] = user_id
        route_context["mode"] = mode
        route_context["memory"] = memory
        # DON'T force intent - let LLM resolve locations first

        result = route_request(route_context)
        return result

    elif action_type == "whoop_sleep":
        # WHOOP sleep query action
        action_context = {
            "text": "How did I sleep last night?",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type == "whoop_recovery":
        # WHOOP recovery query action
        action_context = {
            "text": "How recovered am I?",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type == "whoop_workout":
        # WHOOP workout query action
        action_context = {
            "text": "How was my last workout?",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode
        }

    elif action_type in ["send_email", "compose_email", "email_reply"]:
        # Email composition/sending actions
        action_context = {
            "text": params.get("text", f"Execute {action_type}"),
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            **params
        }

    elif action_type in ["book_appointment", "update_appointment", "cancel_appointment"]:
        # Calendar modification actions
        action_context = {
            "text": params.get("text", f"Execute {action_type}"),
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            **params
        }

    else:
        # Generic action context
        action_context = {
            "text": f"Execute {action_type}",
            "session_id": session_id,
            "user_id": user_id,
            "intent": intent,
            "mode": mode,
            **params
        }

    # Execute the action via action router
    result = action_router.route_action_request(action_context)

    return result
