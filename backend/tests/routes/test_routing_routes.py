"""
Tests for routing routes.

Tests routing preference management for intent-to-provider mapping.
"""

import pytest


def test_get_routing_preferences(client, memory, sample_intent, sample_provider):
    """Test get all routing preferences."""
    # Set a routing preference
    memory.set_routing_preference("local", sample_intent["id"], sample_provider["id"])

    response = client.get("/api/routing")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, dict)
    assert sample_intent["id"] in data
    assert data[sample_intent["id"]]["provider_id"] == sample_provider["id"]


def test_get_routing_preferences_empty(client):
    """Test get routing preferences when none exist."""
    response = client.get("/api/routing")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, dict)
    assert len(data) == 0


def test_set_routing_preference(client, memory, sample_intent, sample_provider):
    """Test set routing preference."""
    response = client.post("/api/routing", json={
        "intent": sample_intent["id"],
        "provider_id": sample_provider["id"]
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify set
    prefs = memory.get_routing_preferences("local")
    assert sample_intent["id"] in prefs
    assert prefs[sample_intent["id"]]["provider_id"] == sample_provider["id"]


def test_set_routing_preference_update(client, memory, sample_intent, sample_provider):
    """Test update existing routing preference."""
    # Set initial preference
    memory.set_routing_preference("local", sample_intent["id"], "old-provider")

    # Update to new provider
    response = client.post("/api/routing", json={
        "intent": sample_intent["id"],
        "provider_id": sample_provider["id"]
    })

    assert response.status_code == 200

    # Verify updated
    provider_id = memory.get_routing_provider("local", sample_intent["id"])
    assert provider_id == sample_provider["id"]


def test_set_routing_preference_new_intent(client, memory, sample_provider):
    """Test set routing preference for new intent."""
    response = client.post("/api/routing", json={
        "intent": "new-intent",
        "provider_id": sample_provider["id"]
    })

    assert response.status_code == 200

    # Verify set
    provider_id = memory.get_routing_provider("local", "new-intent")
    assert provider_id == sample_provider["id"]


def test_delete_routing_preference(client, memory, sample_intent, sample_provider):
    """Test delete routing preference."""
    # Set preference first
    memory.set_routing_preference("local", sample_intent["id"], sample_provider["id"])

    response = client.delete(f"/api/routing/{sample_intent['id']}")

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify deleted
    provider_id = memory.get_routing_provider("local", sample_intent["id"])
    assert provider_id is None


def test_delete_nonexistent_routing_preference(client):
    """Test delete nonexistent routing preference."""
    response = client.delete("/api/routing/nonexistent")

    # Should succeed (idempotent)
    assert response.status_code == 200


def test_routing_preferences_multiple_intents(client, memory):
    """Test routing preferences for multiple intents."""
    # Create providers
    memory.upsert_provider({
        "id": "provider1",
        "name": "Provider 1",
        "type": "openai",
        "enabled": True
    })
    memory.upsert_provider({
        "id": "provider2",
        "name": "Provider 2",
        "type": "anthropic",
        "enabled": True
    })

    # Set multiple routing preferences
    client.post("/api/routing", json={
        "intent": "coding",
        "provider_id": "provider1"
    })
    client.post("/api/routing", json={
        "intent": "creative",
        "provider_id": "provider2"
    })

    # Get all preferences
    response = client.get("/api/routing")

    assert response.status_code == 200
    data = response.json
    assert len(data) >= 2

    # Verify both preferences exist
    assert "coding" in data
    assert "creative" in data
    assert data["coding"]["provider_id"] == "provider1"
    assert data["creative"]["provider_id"] == "provider2"


# ====================
# Fallback Provider Tests
# ====================

def test_set_routing_preference_with_fallback(client, memory, sample_intent):
    """Test set routing preference with fallback provider."""
    # Create providers
    memory.upsert_provider({
        "id": "primary",
        "name": "Primary Provider",
        "type": "openai",
        "enabled": True
    })
    memory.upsert_provider({
        "id": "fallback",
        "name": "Fallback Provider",
        "type": "anthropic",
        "enabled": True
    })

    response = client.post("/api/routing", json={
        "intent": sample_intent["id"],
        "provider_id": "primary",
        "fallback_provider_id": "fallback"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify both primary and fallback are set
    prefs = memory.get_routing_preferences("local")
    assert sample_intent["id"] in prefs
    assert prefs[sample_intent["id"]]["provider_id"] == "primary"
    assert prefs[sample_intent["id"]]["fallback_provider_id"] == "fallback"


def test_set_routing_preference_fallback_optional(client, memory, sample_intent):
    """Test set routing preference without fallback (optional)."""
    memory.upsert_provider({
        "id": "primary",
        "name": "Primary Provider",
        "type": "openai",
        "enabled": True
    })

    response = client.post("/api/routing", json={
        "intent": sample_intent["id"],
        "provider_id": "primary"
    })

    assert response.status_code == 200

    # Verify only primary is set, no fallback
    fallback = memory.get_fallback_provider("local", sample_intent["id"])
    assert fallback is None


def test_update_routing_preference_with_fallback(client, memory, sample_intent):
    """Test update routing preference to add fallback."""
    # Create providers
    memory.upsert_provider({
        "id": "primary",
        "name": "Primary Provider",
        "type": "openai",
        "enabled": True
    })
    memory.upsert_provider({
        "id": "fallback",
        "name": "Fallback Provider",
        "type": "anthropic",
        "enabled": True
    })

    # Set without fallback
    client.post("/api/routing", json={
        "intent": sample_intent["id"],
        "provider_id": "primary"
    })

    # Update to add fallback
    response = client.post("/api/routing", json={
        "intent": sample_intent["id"],
        "provider_id": "primary",
        "fallback_provider_id": "fallback"
    })

    assert response.status_code == 200

    # Verify fallback was added
    fallback = memory.get_fallback_provider("local", sample_intent["id"])
    assert fallback == "fallback"


def test_get_routing_preferences_includes_fallback(client, memory):
    """Test GET routing preferences includes fallback information."""
    # Create providers
    memory.upsert_provider({
        "id": "primary",
        "name": "Primary Provider",
        "type": "openai",
        "enabled": True
    })
    memory.upsert_provider({
        "id": "fallback",
        "name": "Fallback Provider",
        "type": "anthropic",
        "enabled": True
    })

    # Set routing with fallback
    client.post("/api/routing", json={
        "intent": "general",
        "provider_id": "primary",
        "fallback_provider_id": "fallback"
    })

    # Get preferences
    response = client.get("/api/routing")

    assert response.status_code == 200
    data = response.json

    assert "general" in data
    assert data["general"]["provider_id"] == "primary"
    assert data["general"]["fallback_provider_id"] == "fallback"


def test_delete_routing_preference_removes_fallback(client, memory, sample_intent):
    """Test delete routing preference also removes fallback."""
    # Create providers
    memory.upsert_provider({
        "id": "primary",
        "name": "Primary Provider",
        "type": "openai",
        "enabled": True
    })
    memory.upsert_provider({
        "id": "fallback",
        "name": "Fallback Provider",
        "type": "anthropic",
        "enabled": True
    })

    # Set with fallback
    memory.set_routing_preference("local", sample_intent["id"], "primary", fallback_provider_id="fallback")

    # Delete
    response = client.delete(f"/api/routing/{sample_intent['id']}")

    assert response.status_code == 200

    # Verify both primary and fallback are removed
    provider = memory.get_routing_provider("local", sample_intent["id"])
    fallback = memory.get_fallback_provider("local", sample_intent["id"])

    assert provider is None
    assert fallback is None
