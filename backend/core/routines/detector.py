"""
Routine detection module.

Detects if a user message triggers a defined routine.
All routines are now user-defined and stored in the database.
"""

import logging
import json


def detect_routine(user_message, user_routines=None):
    """
    Detect if a user message matches any routine trigger.
    Checks user-defined routines only (all routines are user-editable).

    Args:
        user_message: User's input text
        user_routines: List of user-defined routines from database

    Returns:
        Tuple of (routine_name, routine_definition) if matched, (None, None) otherwise
    """
    if not user_message:
        return None, None

    if not user_routines:
        return None, None

    # Normalize the user message for matching
    normalized_message = user_message.lower().strip()

    # Check all user routines
    for routine in user_routines:
        # Skip disabled routines
        if not routine.get("enabled"):
            continue

        routine_name = routine.get("name")
        triggers_json = routine.get("triggers")

        if not triggers_json:
            continue

        try:
            triggers = json.loads(triggers_json) if isinstance(triggers_json, str) else triggers_json
        except json.JSONDecodeError:
            logging.error(f"[ROUTINES] Failed to parse triggers for routine '{routine_name}'")
            continue

        for trigger in triggers:
            normalized_trigger = trigger.lower().strip()

            if normalized_message == normalized_trigger or normalized_message.startswith(normalized_trigger):
                logging.info(f"[ROUTINES] Detected routine '{routine_name}' (ID: {routine['id']}) from trigger '{trigger}'")

                # Convert user routine to routine_def format
                try:
                    actions = json.loads(routine["actions"]) if isinstance(routine["actions"], str) else routine["actions"]
                except json.JSONDecodeError:
                    logging.error(f"[ROUTINES] Failed to parse actions for routine '{routine_name}'")
                    continue

                routine_def = {
                    "name": routine_name,
                    "triggers": triggers,
                    "actions": actions,
                    "consolidation_prompt": routine.get("consolidation_prompt", "")
                }

                return str(routine['id']), routine_def

    return None, None


def is_routine_trigger(user_message, user_routines=None):
    """
    Check if a message is a routine trigger.

    Args:
        user_message: User's input text
        user_routines: List of user-defined routines

    Returns:
        Boolean indicating if message triggers a routine
    """
    routine_name, _ = detect_routine(user_message, user_routines)
    return routine_name is not None
