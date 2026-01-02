"""
Routine consolidator module.

Consolidates routine execution results into a single cohesive response
using a lightweight LLM.
"""

import logging
from core.user_utils import normalize_user_id, DEFAULT_USER_ID
from typing import Dict, Any


def consolidate_results(routine_def, execution_results, router_func, memory, user_id=DEFAULT_USER_ID):
    """
    Consolidate routine execution results into a single response.

    Args:
        routine_def: Routine definition dict
        execution_results: Results from execute_routine()
        router_func: route_request function for LLM calls
        memory: MemoryStore instance
        user_id: User ID for routing preferences

    Returns:
        Dict with:
            - text: Consolidated response text
            - provider: LLM provider used
            - model: LLM model used
            - metadata: Additional metadata
    """
    routine_name = routine_def.get("name", "Routine")
    consolidation_prompt_template = routine_def.get("consolidation_prompt", "")

    actions = execution_results.get("actions", [])
    success_count = execution_results.get("success_count", 0)
    failure_count = execution_results.get("failure_count", 0)

    logging.info(f"[ROUTINES] Consolidating results for '{routine_name}': {success_count} succeeded, {failure_count} failed")

    # Build the consolidation prompt with action results
    prompt_parts = [consolidation_prompt_template, "\n\n---\n\n"]

    # Add action results
    for action in actions:
        action_type = action.get("type")
        action_desc = action.get("description", action_type)
        status = action.get("status")

        prompt_parts.append(f"## {action_desc}\n")

        if status == "success":
            result = action.get("result", {})
            result_text = result.get("text", "No details available")
            prompt_parts.append(f"Status: ✓ Success\n\n{result_text}\n\n")
        else:
            error = action.get("error", "Unknown error")
            prompt_parts.append(f"Status: ✗ Failed\n\nError: {error}\n\n")

    # Add instruction for handling failures
    if failure_count > 0:
        prompt_parts.append("\n---\n\n")
        prompt_parts.append(
            "NOTE: Some actions failed. Please acknowledge the failures gracefully "
            "and focus on the information that is available. Do not apologize excessively "
            "or make the user feel that the routine failed completely.\n"
        )

    consolidation_prompt = "".join(prompt_parts)

    # Use lightweight LLM (system intent) for consolidation
    try:
        router_context = {
            "text": consolidation_prompt,
            "user_id": user_id,
            "force_intent": "system",  # Use lightweight LLM
            "memory": memory
        }

        result = router_func(router_context)

        logging.info(f"[ROUTINES] Consolidation completed via {result.get('provider', 'unknown')}")

        return {
            "text": result.get("text", "Routine completed."),
            "provider": result.get("provider"),
            "model": result.get("model"),
            "metadata": {
                "routine": routine_name,
                "success_count": success_count,
                "failure_count": failure_count,
                "partial_success": execution_results.get("partial_success", False)
            }
        }

    except Exception as e:
        logging.error(f"[ROUTINES] Consolidation failed: {e}")

        # Fallback: Generate a simple text response
        if failure_count == len(actions):
            fallback_text = f"I tried to run the {routine_name} routine, but unfortunately all actions failed. Please try again later."
        elif failure_count > 0:
            fallback_text = f"I've completed the {routine_name} routine, but some actions couldn't be completed. Here's what I found:\n\n"
            for action in actions:
                if action.get("status") == "success":
                    result_text = action.get("result", {}).get("text", "")
                    if result_text:
                        fallback_text += f"{result_text}\n\n"
        else:
            fallback_text = f"I've completed the {routine_name} routine. Here's a summary:\n\n"
            for action in actions:
                result_text = action.get("result", {}).get("text", "")
                if result_text:
                    fallback_text += f"{result_text}\n\n"

        return {
            "text": fallback_text.strip(),
            "provider": "fallback",
            "model": None,
            "metadata": {
                "routine": routine_name,
                "success_count": success_count,
                "failure_count": failure_count,
                "partial_success": execution_results.get("partial_success", False),
                "consolidation_failed": True
            }
        }
