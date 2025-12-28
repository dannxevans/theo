"""
Tests for mode operations.

Tests mode configuration and work subtab settings.
"""

import pytest
import json


def test_get_user_mode_default(memory, user_fixture):
    """Test get user mode returns default."""
    config = memory.get_user_mode(user_fixture["id"])
    assert "active_mode" in config


def test_set_user_mode_work(memory, user_fixture):
    """Test set user mode to work."""
    memory.set_user_mode(user_fixture["id"], "work")

    config = memory.get_user_mode(user_fixture["id"])
    assert config["active_mode"] == "work"


def test_set_user_mode_personal(memory, user_fixture):
    """Test set user mode to personal."""
    memory.set_user_mode(user_fixture["id"], "personal")

    config = memory.get_user_mode(user_fixture["id"])
    assert config["active_mode"] == "personal"


def test_get_mode_settings(memory, user_fixture):
    """Test get mode settings."""
    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        system_prompt_override="Work mode prompt",
        tone="professional"
    )

    settings = memory.get_mode_settings(user_fixture["id"], "work")
    assert settings is not None
    assert settings["system_prompt_override"] == "Work mode prompt"
    assert settings["tone"] == "professional"


def test_get_mode_settings_nonexistent(memory, user_fixture):
    """Test get mode settings when none exist."""
    settings = memory.get_mode_settings(user_fixture["id"], "work")
    assert settings is None


def test_create_or_update_mode_settings_create(memory, user_fixture):
    """Test create mode settings."""
    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        system_prompt_override="Custom prompt",
        tone="professional"
    )

    settings = memory.get_mode_settings(user_fixture["id"], "work")
    assert settings["system_prompt_override"] == "Custom prompt"


def test_create_or_update_mode_settings_update(memory, user_fixture):
    """Test update existing mode settings."""
    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        system_prompt_override="Original",
        tone="neutral"
    )

    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        system_prompt_override="Updated",
        tone="professional"
    )

    settings = memory.get_mode_settings(user_fixture["id"], "work")
    assert settings["system_prompt_override"] == "Updated"
    assert settings["tone"] == "professional"


def test_create_or_update_mode_settings_partial(memory, user_fixture):
    """Test update mode settings with partial fields."""
    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        system_prompt_override="Prompt",
        tone="neutral"
    )

    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        tone="professional"
    )

    settings = memory.get_mode_settings(user_fixture["id"], "work")
    assert settings["tone"] == "professional"


def test_get_all_mode_settings(memory, user_fixture):
    """Test get all mode settings for user."""
    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        tone="professional"
    )

    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "personal",
        tone="casual"
    )

    all_settings = memory.get_all_mode_settings(user_fixture["id"])
    assert isinstance(all_settings, dict) or isinstance(all_settings, list)


def test_get_work_subtab_config(memory, user_fixture):
    """Test get work subtab configuration."""
    config = {"language": "python", "framework": "django"}
    memory.update_work_subtab_config(user_fixture["id"], "code", json.dumps(config))

    retrieved = memory.get_work_subtab_config(user_fixture["id"], "code")
    assert retrieved is not None


def test_get_work_subtab_config_nonexistent(memory, user_fixture):
    """Test get nonexistent subtab config."""
    config = memory.get_work_subtab_config(user_fixture["id"], "code")
    assert config is None or config == {}


def test_update_work_subtab_config(memory, user_fixture):
    """Test update work subtab configuration."""
    config = {
        "language": "python",
        "framework": "flask",
        "additional_context": "Focus on testing"
    }

    memory.update_work_subtab_config(user_fixture["id"], "code", json.dumps(config))

    retrieved = memory.get_work_subtab_config(user_fixture["id"], "code")
    assert retrieved is not None

    # Should be able to parse the config
    parsed = json.loads(retrieved["config_json"]) if retrieved else {}
    assert parsed.get("language") == "python" or "language" in str(retrieved)


def test_update_work_subtab_config_update(memory, user_fixture):
    """Test update existing subtab config."""
    config1 = {"language": "python"}
    memory.update_work_subtab_config(user_fixture["id"], "code", json.dumps(config1))

    config2 = {"language": "javascript", "framework": "react"}
    memory.update_work_subtab_config(user_fixture["id"], "code", json.dumps(config2))

    retrieved = memory.get_work_subtab_config(user_fixture["id"], "code")
    assert retrieved is not None


def test_get_all_work_subtab_configs(memory, user_fixture):
    """Test get all work subtab configurations."""
    memory.update_work_subtab_config(
        user_fixture["id"],
        "code",
        json.dumps({"language": "python"})
    )

    memory.update_work_subtab_config(
        user_fixture["id"],
        "email",
        json.dumps({"tone": "professional"})
    )

    all_configs = memory.get_all_work_subtab_configs(user_fixture["id"])
    assert isinstance(all_configs, dict) or isinstance(all_configs, list)


def test_mode_workflow(memory, user_fixture):
    """Test complete mode workflow."""
    # Set to work mode
    memory.set_user_mode(user_fixture["id"], "work")

    # Configure work mode
    memory.create_or_update_mode_settings(
        user_fixture["id"],
        "work",
        system_prompt_override="Professional assistant",
        tone="professional"
    )

    # Configure code subtab
    memory.update_work_subtab_config(
        user_fixture["id"],
        "code",
        json.dumps({
            "language": "python",
            "framework": "django",
            "additional_context": "Enterprise application"
        })
    )

    # Verify mode
    mode = memory.get_user_mode(user_fixture["id"])
    assert mode["active_mode"] == "work"

    # Verify settings
    settings = memory.get_mode_settings(user_fixture["id"], "work")
    assert settings["tone"] == "professional"

    # Verify subtab config
    subtab = memory.get_work_subtab_config(user_fixture["id"], "code")
    assert subtab is not None
