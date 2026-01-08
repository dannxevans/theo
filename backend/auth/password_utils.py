"""
Password utility functions for THEO authentication.

Provides password generation and validation for user management.
"""

import secrets
import string
import re
from typing import Tuple


def generate_random_password(length: int = 16) -> str:
    """
    Generate cryptographically secure random password.

    Ensures password meets strength requirements:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    - At least one special character

    Args:
        length: Password length (default: 16, minimum: 8)

    Returns:
        Random password string meeting all requirements

    Raises:
        ValueError: If length < 8
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters")

    # Character sets
    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    all_chars = uppercase + lowercase + digits + special

    # Ensure at least one of each type
    password = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special)
    ]

    # Fill remaining length with random characters from all sets
    password.extend(secrets.choice(all_chars) for _ in range(length - 4))

    # Shuffle to avoid predictable pattern (e.g., always starting with uppercase)
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Validate password meets strength requirements.

    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter (A-Z)
    - At least one lowercase letter (a-z)
    - At least one number (0-9)
    - At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

    Args:
        password: Password string to validate

    Returns:
        Tuple of (is_valid, error_message)
        - (True, "") if password meets all requirements
        - (False, "specific error message") if validation fails

    Examples:
        >>> validate_password_strength("Pass123!")
        (True, "")
        >>> validate_password_strength("short")
        (False, "Password must be at least 8 characters long")
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"

    # Escape special characters for regex
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
        return False, "Password must contain at least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)"

    return True, ""
