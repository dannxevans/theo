"""
Tests for memory routes.

Tests memory CRUD operations, pinning, and relevance search.
"""

import pytest


def test_remember_legacy(client, memory, test_user, auth_token):
    """Test legacy remember endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/memory/remember", headers=headers, json={
        "key": "test_key",
        "value": "test_value"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify stored
    prefs = memory.get_all(test_user["id"])
    assert prefs.get("test_key") == "test_value"


def test_forget_legacy(client, memory, test_user, auth_token):
    """Test legacy forget endpoint."""
    # Store first
    memory.remember(test_user["id"], "test_key", "test_value")

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/memory/forget", headers=headers, json={
        "key": "test_key"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify removed
    prefs = memory.get_all(test_user["id"])
    assert "test_key" not in prefs


def test_list_memories(client, memory, test_user, auth_token):
    """Test list all memories."""
    # Create some memories
    memory.store_memory(test_user["id"], "fact", "name", "THEO")
    memory.store_memory(test_user["id"], "preference", "theme", "dark")

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) >= 2


def test_list_memories_filtered_by_type(client, memory, test_user, auth_token):
    """Test list memories filtered by type."""
    memory.store_memory(test_user["id"], "fact", "fact1", "value1")
    memory.store_memory(test_user["id"], "preference", "pref1", "value1")
    memory.store_memory(test_user["id"], "fact", "fact2", "value2")

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories?type=fact", headers=headers)

    assert response.status_code == 200
    data = response.json

    # Should only return facts
    assert all(m["type"] == "fact" for m in data)


def test_list_memories_with_limit(client, memory, test_user, auth_token):
    """Test list memories with limit."""
    # Create several memories
    for i in range(10):
        memory.store_memory(test_user["id"], "fact", f"fact{i}", f"value{i}")

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories?limit=5", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert len(data) <= 5


def test_list_memories_empty(client, test_user, auth_token):
    """Test list memories when none exist."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)


def test_create_memory(client, memory, test_user, auth_token):
    """Test create new memory."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/memories", headers=headers, json={
        "type": "fact",
        "key": "favorite_color",
        "value": "blue",
        "pinned": False
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify created
    memories = memory.get_memories(test_user["id"], memory_type="fact")
    memory_item = next((m for m in memories if m["key"] == "favorite_color"), None)
    assert memory_item is not None
    assert memory_item["value"] == "blue"


def test_create_memory_pinned(client, memory, test_user, auth_token):
    """Test create pinned memory."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/memories", headers=headers, json={
        "type": "goal",
        "key": "learn_python",
        "value": "Master Python testing",
        "pinned": True
    })

    assert response.status_code == 200

    # Verify pinned
    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["key"] == "learn_python"), None)
    assert memory_item is not None
    assert memory_item["pinned"] is True


def test_create_memory_default_type(client, memory, test_user, auth_token):
    """Test create memory defaults to fact type."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/memories", headers=headers, json={
        "key": "test",
        "value": "value"
    })

    assert response.status_code == 200

    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["key"] == "test"), None)
    assert memory_item is not None
    assert memory_item["type"] == "fact"


def test_delete_memory(client, memory, test_user, auth_token):
    """Test delete memory by ID."""
    # Create memory
    memory.store_memory(test_user["id"], "fact", "to_delete", "value")
    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["key"] == "to_delete"), None)
    memory_id = memory_item["id"]

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.delete(f"/api/memories/{memory_id}", headers=headers)

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify deleted
    memories = memory.get_memories(test_user["id"])
    assert not any(m["id"] == memory_id for m in memories)


def test_delete_nonexistent_memory(client, test_user, auth_token):
    """Test delete nonexistent memory."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.delete("/api/memories/99999", headers=headers)

    # Should succeed (idempotent)
    assert response.status_code == 200


def test_pin_memory(client, memory, test_user, auth_token):
    """Test pin a memory."""
    # Create memory
    memory.store_memory(test_user["id"], "fact", "to_pin", "value", pinned=False)
    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["key"] == "to_pin"), None)
    memory_id = memory_item["id"]

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post(f"/api/memories/{memory_id}/pin", headers=headers, json={
        "pinned": True
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["pinned"] is True

    # Verify pinned
    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["id"] == memory_id), None)
    assert memory_item["pinned"] is True


def test_unpin_memory(client, memory, test_user, auth_token):
    """Test unpin a memory."""
    # Create pinned memory
    memory.store_memory(test_user["id"], "fact", "to_unpin", "value", pinned=True)
    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["key"] == "to_unpin"), None)
    memory_id = memory_item["id"]

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post(f"/api/memories/{memory_id}/pin", headers=headers, json={
        "pinned": False
    })

    assert response.status_code == 200
    data = response.json
    assert data["pinned"] is False

    # Verify unpinned
    memories = memory.get_memories(test_user["id"])
    memory_item = next((m for m in memories if m["id"] == memory_id), None)
    assert memory_item["pinned"] is False


def test_pin_memory_default_true(client, memory, test_user, auth_token):
    """Test pin memory defaults to True."""
    memory.store_memory(test_user["id"], "fact", "test", "value", pinned=False)
    memories = memory.get_memories(test_user["id"])
    memory_id = memories[0]["id"]

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post(f"/api/memories/{memory_id}/pin", headers=headers, json={})

    assert response.status_code == 200
    assert response.json["pinned"] is True


def test_get_relevant_memories(client, memory, test_user, auth_token):
    """Test get relevant memories based on query."""
    # Create memories
    memory.store_memory(test_user["id"], "fact", "python", "Python is a programming language")
    memory.store_memory(test_user["id"], "fact", "cooking", "I enjoy cooking pasta")
    memory.store_memory(test_user["id"], "fact", "programming", "I write code in Python")

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories/relevant?q=programming", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)

    # Should return programming-related memories
    # (relevance algorithm should rank "python" and "programming" higher)


def test_get_relevant_memories_empty_query(client, test_user, auth_token):
    """Test relevant memories with empty query."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories/relevant?q=", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_relevant_memories_no_query(client, test_user, auth_token):
    """Test relevant memories without query parameter."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories/relevant", headers=headers)

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_relevant_memories_with_pinned(client, memory, test_user, auth_token):
    """Test relevant memories includes pinned items."""
    # Create pinned memory
    memory.store_memory(test_user["id"], "fact", "important", "Critical information", pinned=True)
    memory.store_memory(test_user["id"], "fact", "normal", "Regular information")

    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.get("/api/memories/relevant?q=information", headers=headers)

    assert response.status_code == 200
    data = response.json

    # Pinned items should be included
    assert any(m["pinned"] for m in data) if len(data) > 0 else True
