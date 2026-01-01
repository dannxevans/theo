"""
Tests for settings routes.

Tests debug settings and system prompt configuration.
"""

import pytest


def test_get_debug_setting_default(client, memory):
    """Test get debug setting default value."""
    response = client.get("/api/settings/debug")

    assert response.status_code == 200
    data = response.json
    assert "enabled" in data
    assert isinstance(data["enabled"], bool)


def test_get_debug_setting_enabled(client, memory):
    """Test get debug setting when enabled."""
    memory.remember("local", "debug_enabled", "true")

    response = client.get("/api/settings/debug")

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is True


def test_get_debug_setting_disabled(client, memory):
    """Test get debug setting when disabled."""
    memory.remember("local", "debug_enabled", "false")

    response = client.get("/api/settings/debug")

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is False


def test_set_debug_setting_enable(client, memory):
    """Test enable debug setting."""
    response = client.post("/api/settings/debug", json={
        "enabled": True
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["enabled"] is True

    # Verify persisted
    prefs = memory.get_all("local")
    assert prefs.get("debug_enabled") == "true"


def test_set_debug_setting_disable(client, memory):
    """Test disable debug setting."""
    response = client.post("/api/settings/debug", json={
        "enabled": False
    })

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is False

    # Verify persisted
    prefs = memory.get_all("local")
    assert prefs.get("debug_enabled") == "false"


def test_set_debug_setting_default_false(client):
    """Test set debug defaults to false."""
    response = client.post("/api/settings/debug", json={})

    assert response.status_code == 200
    assert response.json["enabled"] is False


def test_get_system_prompt_settings(client, memory):
    """Test get system prompt configuration."""
    response = client.get("/api/settings/system-prompt")

    assert response.status_code == 200
    data = response.json

    # Check expected fields
    assert "persona_name" in data
    assert "tone" in data
    assert "style_rules" in data


def test_get_system_prompt_settings_default(client, memory):
    """Test get system prompt returns defaults."""
    config = memory.get_system_prompt_config("local")

    response = client.get("/api/settings/system-prompt")

    assert response.status_code == 200
    data = response.json
    assert data["persona_name"] == config["persona_name"]


def test_update_system_prompt_settings(client, memory):
    """Test update system prompt configuration."""
    response = client.post("/api/settings/system-prompt", json={
        "persona_name": "Assistant",
        "tone": "friendly, helpful",
        "style_rules": "Be concise\nUse examples",
        "custom_instructions": "Always explain technical terms"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify updated
    config = memory.get_system_prompt_config("local")
    assert config["persona_name"] == "Assistant"
    assert config["tone"] == "friendly, helpful"


def test_update_system_prompt_partial(client, memory):
    """Test update system prompt with partial fields."""
    response = client.post("/api/settings/system-prompt", json={
        "persona_name": "NewName"
    })

    assert response.status_code == 200

    config = memory.get_system_prompt_config("local")
    assert config["persona_name"] == "NewName"


def test_update_system_prompt_invalid_fields(client):
    """Test update system prompt rejects invalid fields."""
    response = client.post("/api/settings/system-prompt", json={
        "invalid_field": "value"
    })

    assert response.status_code == 400
    assert "error" in response.json


def test_update_system_prompt_empty(client):
    """Test update system prompt with no fields."""
    response = client.post("/api/settings/system-prompt", json={})

    assert response.status_code == 400


def test_update_system_prompt_custom_instructions(client, memory):
    """Test update custom instructions."""
    custom = "Always provide code examples\nUse TypeScript for examples"

    response = client.post("/api/settings/system-prompt", json={
        "custom_instructions": custom
    })

    assert response.status_code == 200

    config = memory.get_system_prompt_config("local")
    assert config["custom_instructions"] == custom


def test_update_system_prompt_clear_custom_instructions(client, memory):
    """Test clear custom instructions."""
    # Set some custom instructions first
    memory.update_system_prompt_config("local", custom_instructions="Test")

    # Clear them
    response = client.post("/api/settings/system-prompt", json={
        "custom_instructions": None
    })

    assert response.status_code == 200

    config = memory.get_system_prompt_config("local")
    assert config["custom_instructions"] is None


def test_get_message_debug_setting_default(client, memory):
    """Test get message debug setting default value."""
    response = client.get("/api/settings/message-debug")

    assert response.status_code == 200
    data = response.json
    assert "enabled" in data
    assert isinstance(data["enabled"], bool)


def test_get_message_debug_setting_enabled(client, memory):
    """Test get message debug setting when enabled."""
    memory.remember("local", "message_debug_enabled", "true")

    response = client.get("/api/settings/message-debug")

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is True


def test_get_message_debug_setting_disabled(client, memory):
    """Test get message debug setting when disabled."""
    memory.remember("local", "message_debug_enabled", "false")

    response = client.get("/api/settings/message-debug")

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is False


def test_set_message_debug_setting_enable(client, memory):
    """Test enable message debug setting."""
    response = client.post("/api/settings/message-debug", json={
        "enabled": True
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["enabled"] is True

    # Verify persisted
    prefs = memory.get_all("local")
    assert prefs.get("message_debug_enabled") == "true"


def test_set_message_debug_setting_disable(client, memory):
    """Test disable message debug setting."""
    response = client.post("/api/settings/message-debug", json={
        "enabled": False
    })

    assert response.status_code == 200
    data = response.json
    assert data["enabled"] is False

    # Verify persisted
    prefs = memory.get_all("local")
    assert prefs.get("message_debug_enabled") == "false"


def test_set_message_debug_setting_default_false(client):
    """Test set message debug defaults to false."""
    response = client.post("/api/settings/message-debug", json={})

    assert response.status_code == 200
    assert response.json["enabled"] is False
