#!/usr/bin/env python3
"""
Password Reset Utility for THEO

Usage:
    python reset_password.py <username> <new_password>

Example:
    python reset_password.py admin mynewpassword

This script allows you to reset a user's password directly via the database.
Useful when you've forgotten your password and can't log in.
"""

import sys
from core.memory import MemoryStore
from config import Config
from auth import hash_password


def reset_password(username, new_password):
    """Reset a user's password."""
    memory = MemoryStore(Config.DATABASE_URL)

    # Get user
    user = memory.get_user_by_username(username)
    if not user:
        print(f"❌ Error: User '{username}' not found")
        return False

    # Hash new password
    new_hash = hash_password(new_password)

    # Update password
    memory.update_user_password(user["id"], new_hash)

    print(f"✅ Password reset successfully for user '{username}'")
    print(f"   You can now log in with the new password.")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python reset_password.py <username> <new_password>")
        print()
        print("Example:")
        print("    python reset_password.py admin mynewpassword")
        sys.exit(1)

    username = sys.argv[1]
    new_password = sys.argv[2]

    if len(new_password) < 4:
        print("❌ Error: Password must be at least 4 characters")
        sys.exit(1)

    success = reset_password(username, new_password)
    sys.exit(0 if success else 1)
