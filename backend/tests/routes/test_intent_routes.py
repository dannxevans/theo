"""
Tests for intent routes.

Tests intent CRUD operations.
"""

import pytest


def test_list_intents(client, memory, sample_intent):
    """Test list all intents."""
    response = client.get("/api/intents")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) > 0

    # Check intent structure
    intent = data[0]
    assert "id" in intent
    assert "name" in intent
    assert "keywords" in intent


def test_list_intents_empty(client):
    """Test list intents when none exist."""
    response = client.get("/api/intents")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)


def test_get_intent(client, memory, sample_intent):
    """Test get specific intent by ID."""
    response = client.get(f"/api/intents/{sample_intent['id']}")

    assert response.status_code == 200
    data = response.json

    assert data["id"] == sample_intent["id"]
    assert data["name"] == sample_intent["name"]
    assert data["keywords"] == sample_intent["keywords"]


def test_get_intent_not_found(client):
    """Test get nonexistent intent."""
    response = client.get("/api/intents/nonexistent")

    assert response.status_code == 404
    assert "error" in response.json


def test_create_intent(client, memory):
    """Test create new intent."""
    response = client.post("/api/intents", json={
        "id": "creative",
        "name": "Creative Writing",
        "description": "Help with creative content",
        "keywords": "story,poem,creative,write",
        "priority": 5,
        "enabled": True
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["intent_id"] == "creative"

    # Verify created
    intent = memory.get_intent("local", "creative")
    assert intent is not None
    assert intent["name"] == "Creative Writing"


def test_create_intent_missing_required_fields(client):
    """Test create intent with missing required fields."""
    # Missing name
    response = client.post("/api/intents", json={
        "id": "test"
    })
    assert response.status_code == 400

    # Missing id
    response = client.post("/api/intents", json={
        "name": "Test Intent"
    })
    assert response.status_code == 400


def test_create_intent_with_defaults(client, memory):
    """Test create intent uses default values."""
    response = client.post("/api/intents", json={
        "id": "minimal",
        "name": "Minimal Intent"
    })

    assert response.status_code == 200

    # Verify defaults
    intent = memory.get_intent("local", "minimal")
    assert intent["description"] == ""
    assert intent["keywords"] == ""
    assert intent["priority"] == 0
    assert intent["enabled"] is True


def test_update_intent(client, memory, sample_intent):
    """Test update existing intent."""
    response = client.put(f"/api/intents/{sample_intent['id']}", json={
        "name": "Updated Name",
        "description": "Updated description",
        "priority": 20
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify updated
    intent = memory.get_intent("local", sample_intent["id"])
    assert intent["name"] == "Updated Name"
    assert intent["description"] == "Updated description"
    assert intent["priority"] == 20


def test_update_intent_partial(client, memory, sample_intent):
    """Test update intent with partial fields."""
    original_keywords = sample_intent["keywords"]

    response = client.put(f"/api/intents/{sample_intent['id']}", json={
        "name": "New Name Only"
    })

    assert response.status_code == 200

    # Verify only name changed
    intent = memory.get_intent("local", sample_intent["id"])
    assert intent["name"] == "New Name Only"
    assert intent["keywords"] == original_keywords


def test_update_intent_enable_disable(client, memory, sample_intent):
    """Test enable/disable intent."""
    response = client.put(f"/api/intents/{sample_intent['id']}", json={
        "enabled": False
    })

    assert response.status_code == 200

    intent = memory.get_intent("local", sample_intent["id"])
    assert intent["enabled"] is False

    # Re-enable
    response = client.put(f"/api/intents/{sample_intent['id']}", json={
        "enabled": True
    })

    assert response.status_code == 200
    intent = memory.get_intent("local", sample_intent["id"])
    assert intent["enabled"] is True


def test_update_nonexistent_intent(client):
    """Test update nonexistent intent."""
    response = client.put("/api/intents/nonexistent", json={
        "name": "Updated"
    })

    assert response.status_code == 500


def test_delete_intent(client, memory, sample_intent):
    """Test delete intent."""
    response = client.delete(f"/api/intents/{sample_intent['id']}")

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify deleted
    intent = memory.get_intent("local", sample_intent["id"])
    assert intent is None


def test_delete_nonexistent_intent(client):
    """Test delete nonexistent intent."""
    response = client.delete("/api/intents/nonexistent")

    # Should return error (intent operations are more strict)
    assert response.status_code == 500


def test_create_duplicate_intent(client, memory, sample_intent):
    """Test create intent with duplicate ID."""
    response = client.post("/api/intents", json={
        "id": sample_intent["id"],
        "name": "Duplicate",
        "keywords": "test"
    })

    # Should fail or update depending on implementation
    assert response.status_code in [200, 500]
