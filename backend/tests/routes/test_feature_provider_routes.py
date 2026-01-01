"""
Tests for feature provider routes.

Tests API endpoints for managing external feature providers.
"""

import pytest


def test_get_feature_providers_empty(client, memory):
    """Test getting feature providers when none configured."""
    response = client.get("/api/feature-providers")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0


def test_configure_feature_provider(client, memory):
    """Test configuring a new feature provider."""
    response = client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "test_api_key_12345",
        "is_enabled": True
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"

    # Verify it was saved in database by fetching it
    verify_response = client.get("/api/feature-providers/openweather")
    assert verify_response.status_code == 200

    verify_data = verify_response.json
    assert verify_data["provider_type"] == "openweather"
    assert verify_data["provider_name"] == "OpenWeather"
    assert verify_data["is_enabled"] is True

    # Verify API key was saved in preferences
    prefs = memory.get_all("local")
    assert "feature_provider_openweather_api_key" in prefs
    assert prefs["feature_provider_openweather_api_key"] == "test_api_key_12345"


def test_configure_feature_provider_missing_name(client):
    """Test configuring provider without provider_name."""
    response = client.post("/api/feature-providers/openweather", json={
        "api_key": "test_key"
    })

    assert response.status_code == 400
    assert "error" in response.json


def test_get_feature_provider(client, memory):
    """Test getting a specific feature provider."""
    # First configure a provider
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "test_key",
        "is_enabled": True
    })

    # Get the provider
    response = client.get("/api/feature-providers/openweather")

    assert response.status_code == 200
    data = response.json

    assert data["provider_type"] == "openweather"
    assert data["provider_name"] == "OpenWeather"
    assert data["is_enabled"] is True
    assert data["has_api_key"] is True


def test_get_feature_provider_not_found(client):
    """Test getting a provider that doesn't exist."""
    response = client.get("/api/feature-providers/nonexistent")

    assert response.status_code == 404
    assert "error" in response.json


def test_get_all_feature_providers(client, memory):
    """Test getting all configured feature providers."""
    # Configure multiple providers
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "weather_key",
        "is_enabled": True
    })

    client.post("/api/feature-providers/here_traffic", json={
        "provider_name": "HERE Traffic",
        "api_key": "traffic_key",
        "is_enabled": False
    })

    # Get all providers
    response = client.get("/api/feature-providers")

    assert response.status_code == 200
    data = response.json

    assert len(data) == 2

    # Find each provider
    weather_provider = next((p for p in data if p["provider_type"] == "openweather"), None)
    traffic_provider = next((p for p in data if p["provider_type"] == "here_traffic"), None)

    assert weather_provider is not None
    assert weather_provider["provider_name"] == "OpenWeather"
    assert weather_provider["is_enabled"] is True
    assert weather_provider["has_api_key"] is True

    assert traffic_provider is not None
    assert traffic_provider["provider_name"] == "HERE Traffic"
    assert traffic_provider["is_enabled"] is False
    assert traffic_provider["has_api_key"] is True


def test_update_feature_provider(client, memory):
    """Test updating an existing feature provider."""
    # First configure a provider
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "old_key",
        "is_enabled": True
    })

    # Update it
    response = client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather Updated",
        "api_key": "new_key",
        "is_enabled": False
    })

    assert response.status_code == 200

    # Verify it was updated
    get_response = client.get("/api/feature-providers/openweather")
    data = get_response.json

    assert data["provider_name"] == "OpenWeather Updated"
    assert data["is_enabled"] is False

    # Verify new API key
    prefs = memory.get_all("local")
    assert prefs["feature_provider_openweather_api_key"] == "new_key"


def test_update_provider_without_api_key(client, memory):
    """Test updating provider settings without changing API key."""
    # First configure a provider
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "original_key",
        "is_enabled": True
    })

    # Update without providing api_key
    response = client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather Updated",
        "is_enabled": False
    })

    assert response.status_code == 200

    # Verify API key wasn't changed
    prefs = memory.get_all("local")
    assert prefs["feature_provider_openweather_api_key"] == "original_key"


def test_delete_feature_provider(client, memory):
    """Test deleting a feature provider."""
    # First configure a provider
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "test_key",
        "is_enabled": True
    })

    # Delete it
    response = client.delete("/api/feature-providers/openweather")

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify it was deleted from database
    get_response = client.get("/api/feature-providers/openweather")
    assert get_response.status_code == 404

    # Verify API key was deleted from preferences
    prefs = memory.get_all("local")
    assert "feature_provider_openweather_api_key" not in prefs


def test_delete_nonexistent_provider(client):
    """Test deleting a provider that doesn't exist."""
    # Should not error, just silently succeed
    response = client.delete("/api/feature-providers/nonexistent")

    assert response.status_code == 200


def test_feature_provider_api_key_not_exposed(client, memory):
    """Test that API keys are never returned in responses."""
    # Configure a provider with an API key
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather",
        "api_key": "super_secret_key_12345",
        "is_enabled": True
    })

    # Get the provider
    response = client.get("/api/feature-providers/openweather")
    data = response.json

    # Should not contain the actual API key
    assert "api_key" not in data
    assert "super_secret_key_12345" not in str(data)
    assert data["has_api_key"] is True  # Only indicates presence


def test_feature_provider_unique_per_user(client, memory):
    """Test that providers are unique per user_id and provider_type."""
    # Configure for "local" user
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather Local",
        "api_key": "local_key",
        "is_enabled": True
    })

    # Try to configure again - should update, not create duplicate
    client.post("/api/feature-providers/openweather", json={
        "provider_name": "OpenWeather Updated",
        "api_key": "updated_key",
        "is_enabled": False
    })

    # Verify only one entry exists by checking the updated values
    response = client.get("/api/feature-providers/openweather")
    assert response.status_code == 200

    data = response.json
    assert data["provider_name"] == "OpenWeather Updated"
    assert data["is_enabled"] is False

    # If there were duplicates, we'd have undefined behavior above
    # The UNIQUE constraint on (user_id, provider_type) ensures only one exists
