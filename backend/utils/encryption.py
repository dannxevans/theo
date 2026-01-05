"""
Encryption utilities for sensitive data storage.

Uses Fernet (symmetric encryption) from cryptography library.
"""

import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
import logging

logger = logging.getLogger(__name__)


class ConfigEncryption:
    """Handle encryption/decryption of configuration data."""

    def __init__(self):
        """Initialize encryption with key from environment or generated."""
        # Get encryption key from environment or generate one
        self.encryption_key = os.getenv("ENCRYPTION_KEY")

        if not self.encryption_key:
            # Generate a key from a secret (fallback for development)
            secret = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
            salt = b"theo-oauth-config-salt"  # Static salt for consistent keys

            kdf = PBKDF2(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret.encode()))
            self.encryption_key = key.decode()

            logger.warning(
                "[ENCRYPTION] Using derived encryption key. "
                "Set ENCRYPTION_KEY environment variable for production."
            )

        self.cipher = Fernet(self.encryption_key.encode())

    def encrypt_config(self, config_dict: dict) -> str:
        """
        Encrypt configuration dictionary to string.

        Args:
            config_dict: Dictionary with configuration data

        Returns:
            str: Encrypted configuration as base64 string
        """
        try:
            json_str = json.dumps(config_dict)
            encrypted_bytes = self.cipher.encrypt(json_str.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"[ENCRYPTION] Failed to encrypt config: {e}")
            raise

    def decrypt_config(self, encrypted_str: str) -> dict:
        """
        Decrypt configuration string to dictionary.

        Args:
            encrypted_str: Encrypted configuration string

        Returns:
            dict: Decrypted configuration dictionary
        """
        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_str.encode())
            json_str = decrypted_bytes.decode()
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"[ENCRYPTION] Failed to decrypt config: {e}")
            raise


# Global instance
_encryption = None


def get_encryption() -> ConfigEncryption:
    """Get or create global encryption instance."""
    global _encryption
    if _encryption is None:
        _encryption = ConfigEncryption()
    return _encryption


def encrypt_oauth_config(config: dict) -> str:
    """Convenience function to encrypt OAuth config."""
    return get_encryption().encrypt_config(config)


def decrypt_oauth_config(encrypted: str) -> dict:
    """Convenience function to decrypt OAuth config."""
    return get_encryption().decrypt_config(encrypted)
