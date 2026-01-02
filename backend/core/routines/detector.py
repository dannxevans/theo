"""
Routine detection module.

Detects if a user message triggers a defined routine.
"""

import logging
from .definitions import ROUTINES


def detect_routine(user_message):
    """
    Detect if a user message matches any routine trigger.

    Args:
        user_message: User's input text

    Returns:
        Tuple of (routine_name, routine_definition) if matched, (None, None) otherwise
    """
    if not user_message:
        return None, None

    # Normalize the user message for matching
    normalized_message = user_message.lower().strip()

    # Check each routine's triggers
    for routine_name, routine_def in ROUTINES.items():
        triggers = routine_def.get("triggers", [])

        for trigger in triggers:
            # Case-insensitive exact match or starts with
            normalized_trigger = trigger.lower().strip()

            if normalized_message == normalized_trigger or normalized_message.startswith(normalized_trigger):
                logging.info(f"[ROUTINES] Detected routine '{routine_name}' from trigger '{trigger}'")
                return routine_name, routine_def

    return None, None


def is_routine_trigger(user_message):
    """
    Check if a message is a routine trigger.

    Args:
        user_message: User's input text

    Returns:
        Boolean indicating if message triggers a routine
    """
    routine_name, _ = detect_routine(user_message)
    return routine_name is not None
