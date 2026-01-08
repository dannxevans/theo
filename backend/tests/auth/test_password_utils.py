"""
Tests for password utility functions.

Tests password generation and validation for user management.
"""

import pytest
from auth.password_utils import generate_random_password, validate_password_strength


class TestGenerateRandomPassword:
    """Test password generation function."""

    def test_generates_password_with_default_length(self):
        """Test password is generated with default 16 character length."""
        password = generate_random_password()
        assert len(password) == 16

    def test_generates_password_with_custom_length(self):
        """Test password is generated with custom length."""
        password = generate_random_password(20)
        assert len(password) == 20

    def test_minimum_length_enforced(self):
        """Test password generation fails below minimum length."""
        with pytest.raises(ValueError, match="at least 8 characters"):
            generate_random_password(7)

    def test_password_contains_uppercase(self):
        """Test generated password contains uppercase letter."""
        password = generate_random_password()
        assert any(c.isupper() for c in password)

    def test_password_contains_lowercase(self):
        """Test generated password contains lowercase letter."""
        password = generate_random_password()
        assert any(c.islower() for c in password)

    def test_password_contains_digit(self):
        """Test generated password contains digit."""
        password = generate_random_password()
        assert any(c.isdigit() for c in password)

    def test_password_contains_special_char(self):
        """Test generated password contains special character."""
        password = generate_random_password()
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        assert any(c in special_chars for c in password)

    def test_passwords_are_unique(self):
        """Test that generated passwords are unique (not repeating)."""
        passwords = [generate_random_password() for _ in range(100)]
        assert len(set(passwords)) == 100  # All unique

    def test_password_meets_strength_requirements(self):
        """Test generated password passes strength validation."""
        password = generate_random_password()
        is_valid, error_msg = validate_password_strength(password)
        assert is_valid is True
        assert error_msg == ""


class TestValidatePasswordStrength:
    """Test password strength validation function."""

    def test_valid_strong_password(self):
        """Test valid password passes all requirements."""
        is_valid, error_msg = validate_password_strength("SecureP@ss123")
        assert is_valid is True
        assert error_msg == ""

    def test_empty_password_fails(self):
        """Test empty password is rejected."""
        is_valid, error_msg = validate_password_strength("")
        assert is_valid is False
        assert "required" in error_msg.lower()

    def test_too_short_password_fails(self):
        """Test password under 8 characters is rejected."""
        is_valid, error_msg = validate_password_strength("Pass1!")
        assert is_valid is False
        assert "at least 8 characters" in error_msg

    def test_no_uppercase_fails(self):
        """Test password without uppercase letter is rejected."""
        is_valid, error_msg = validate_password_strength("password123!")
        assert is_valid is False
        assert "uppercase" in error_msg.lower()

    def test_no_lowercase_fails(self):
        """Test password without lowercase letter is rejected."""
        is_valid, error_msg = validate_password_strength("PASSWORD123!")
        assert is_valid is False
        assert "lowercase" in error_msg.lower()

    def test_no_digit_fails(self):
        """Test password without digit is rejected."""
        is_valid, error_msg = validate_password_strength("Password!")
        assert is_valid is False
        assert "number" in error_msg.lower()

    def test_no_special_char_fails(self):
        """Test password without special character is rejected."""
        is_valid, error_msg = validate_password_strength("Password123")
        assert is_valid is False
        assert "special character" in error_msg.lower()

    def test_various_special_chars_accepted(self):
        """Test various special characters are accepted."""
        special_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        for char in special_chars:
            password = f"Password123{char}"
            is_valid, error_msg = validate_password_strength(password)
            assert is_valid is True, f"Failed for special char: {char}"

    def test_exactly_8_chars_valid(self):
        """Test password with exactly 8 characters is valid."""
        is_valid, error_msg = validate_password_strength("Pass123!")
        assert is_valid is True
        assert error_msg == ""

    def test_very_long_password_valid(self):
        """Test very long password is valid."""
        long_password = "P@ssw0rd" + "a" * 100
        is_valid, error_msg = validate_password_strength(long_password)
        assert is_valid is True

    def test_unicode_password_with_requirements(self):
        """Test password with unicode characters but meeting requirements."""
        is_valid, error_msg = validate_password_strength("Pässw0rd!")
        assert is_valid is True

    def test_none_password_fails(self):
        """Test None password is rejected."""
        is_valid, error_msg = validate_password_strength(None)
        assert is_valid is False
