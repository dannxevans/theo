"""
Routine executor module.

Executes routine actions by delegating to existing action handlers.
"""

import logging
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
    user_id = context.get("user_id", "local")
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

        logging.info(f"[ROUTINES] Executing action: {action_type}")

        try:
            result = _execute_action(
                action_type,
                action_params,
                session_id,
                user_id,
                mode,
                action_router,
                memory
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


def _execute_action(action_type, params, session_id, user_id, mode, action_router, memory):
    """
    Execute a single action by delegating to the action router.

    Args:
        action_type: Type of action (e.g., "calendar_read", "email_check")
        params: Action parameters
        session_id: Session ID
        user_id: User ID
        mode: Session mode
        action_router: ActionRouter instance
        memory: MemoryStore instance

    Returns:
        Action result dict

    Raises:
        Exception if action fails
    """
    # Map routine action types to action router intents
    action_type_mapping = {
        "calendar_read": "read_calendar",
        "email_check": "read_email",
        "email_summary": "read_email",  # Will be handled differently
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
