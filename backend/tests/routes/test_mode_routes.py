"""
Tests for mode routes.

Tests mode management (work/personal), mode settings, and work subtab configuration.
"""

import pytest
import json


def test_get_mode_unauthorized(client):
    """Test get mode requires authentication."""
    response = client.get("/api/mode")

    assert response.status_code == 401


def test_get_mode_default(client, auth_headers, test_user):
    """Test get mode returns default."""
    response = client.get("/api/mode", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert "active_mode" in data


def test_set_mode_work(client, memory, auth_headers, test_user):
    """Test set mode to work."""
    response = client.post("/api/mode", headers=auth_headers, json={
        "mode": "work"
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["mode"] == "work"

    # Verify persisted
    config = memory.get_user_mode(test_user["id"])
    assert config["active_mode"] == "work"


def test_set_mode_personal(client, memory, auth_headers, test_user):
    """Test set mode to personal."""
    response = client.post("/api/mode", headers=auth_headers, json={
        "mode": "personal"
    })

    assert response.status_code == 200
    data = response.json
    assert data["mode"] == "personal"


def test_set_mode_invalid(client, auth_headers):
    """Test set mode to invalid value."""
    response = client.post("/api/mode", headers=auth_headers, json={
        "mode": "invalid"
    })

    assert response.status_code == 400
    assert "error" in response.json


def test_set_mode_unauthorized(client):
    """Test set mode requires authentication."""
    response = client.post("/api/mode", json={"mode": "work"})

    assert response.status_code == 401


def test_get_mode_settings_all(client, memory, auth_headers, test_user):
    """Test get all mode settings."""
    # Create settings for both modes
    memory.create_or_update_mode_settings(
        test_user["id"],
        "work",
        system_prompt_override="Professional assistant",
        tone="professional"
    )
    memory.create_or_update_mode_settings(
        test_user["id"],
        "personal",
        tone="casual"
    )

    response = client.get("/api/mode/settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, dict)


def test_get_mode_setting_work(client, memory, auth_headers, test_user):
    """Test get work mode settings."""
    memory.create_or_update_mode_settings(
        test_user["id"],
        "work",
        system_prompt_override="Work mode prompt",
        tone="professional"
    )

    response = client.get("/api/mode/settings/work", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["system_prompt_override"] == "Work mode prompt"
    assert data["tone"] == "professional"


def test_get_mode_setting_personal(client, memory, auth_headers, test_user):
    """Test get personal mode settings."""
    response = client.get("/api/mode/settings/personal", headers=auth_headers)

    assert response.status_code == 200


def test_get_mode_setting_invalid(client, auth_headers):
    """Test get invalid mode settings."""
    response = client.get("/api/mode/settings/invalid", headers=auth_headers)

    assert response.status_code == 400


def test_update_mode_settings(client, memory, auth_headers, test_user):
    """Test update mode settings."""
    response = client.post("/api/mode/settings/work", headers=auth_headers, json={
        "system_prompt_override": "Updated prompt",
        "preferred_provider_id": 1,
        "tone": "professional"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify updated
    settings = memory.get_mode_settings(test_user["id"], "work")
    assert settings["system_prompt_override"] == "Updated prompt"
    assert settings["tone"] == "professional"


def test_update_mode_settings_partial(client, memory, auth_headers, test_user):
    """Test update mode settings with partial data."""
    response = client.post("/api/mode/settings/work", headers=auth_headers, json={
        "tone": "casual"
    })

    assert response.status_code == 200


def test_get_work_subtab_code(client, memory, auth_headers, test_user):
    """Test get code subtab configuration."""
    memory.update_work_subtab_config(
        test_user["id"],
        "code",
        json.dumps({"language": "python", "framework": "django"})
    )

    response = client.get("/api/mode/work/subtab/code", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert "language" in data or "config_json" in data


def test_get_work_subtab_email(client, auth_headers):
    """Test get email subtab configuration."""
    response = client.get("/api/mode/work/subtab/email", headers=auth_headers)

    assert response.status_code == 200


def test_get_work_subtab_conversation(client, auth_headers):
    """Test get conversation subtab configuration."""
    response = client.get("/api/mode/work/subtab/conversation", headers=auth_headers)

    assert response.status_code == 200


def test_get_work_subtab_invalid(client, auth_headers):
    """Test get invalid subtab."""
    response = client.get("/api/mode/work/subtab/invalid", headers=auth_headers)

    assert response.status_code == 400


def test_update_work_subtab_code(client, memory, auth_headers, test_user):
    """Test update code subtab configuration."""
    config = {
        "language": "python",
        "framework": "flask",
        "additional_context": "Focus on testing"
    }

    response = client.post(
        "/api/mode/work/subtab/code",
        headers=auth_headers,
        json=config
    )

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify saved
    saved_config = memory.get_work_subtab_config(test_user["id"], "code")
    assert saved_config is not None


def test_update_work_subtab_email(client, auth_headers):
    """Test update email subtab configuration."""
    config = {
        "tone": "professional",
        "signature": "Best regards"
    }

    response = client.post(
        "/api/mode/work/subtab/email",
        headers=auth_headers,
        json=config
    )

    assert response.status_code == 200


def test_get_all_work_subtabs(client, memory, auth_headers, test_user):
    """Test get all work subtab configurations."""
    # Create some subtab configs
    memory.update_work_subtab_config(
        test_user["id"],
        "code",
        json.dumps({"language": "python"})
    )
    memory.update_work_subtab_config(
        test_user["id"],
        "email",
        json.dumps({"tone": "professional"})
    )

    response = client.get("/api/mode/work/subtabs", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, dict) or isinstance(data, list)


def test_mode_operations_expired_token(client, memory, test_user):
    """Test mode operations with expired token."""
    from auth import generate_session_token
    from datetime import datetime, timedelta

    token = generate_session_token()
    expires_at = datetime.utcnow() - timedelta(hours=1)
    memory.create_auth_session(token, test_user["id"], expires_at)

    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/mode", headers=headers)
    assert response.status_code == 401
