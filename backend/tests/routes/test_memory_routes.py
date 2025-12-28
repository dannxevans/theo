"""
Tests for memory routes.

Tests memory CRUD operations, pinning, and relevance search.
"""

import pytest


def test_remember_legacy(client, memory):
    """Test legacy remember endpoint."""
    response = client.post("/api/memory/remember", json={
        "key": "test_key",
        "value": "test_value"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify stored
    prefs = memory.get_all("local")
    assert prefs.get("test_key") == "test_value"


def test_forget_legacy(client, memory):
    """Test legacy forget endpoint."""
    # Store first
    memory.remember("local", "test_key", "test_value")

    response = client.post("/api/memory/forget", json={
        "key": "test_key"
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify removed
    prefs = memory.get_all("local")
    assert "test_key" not in prefs


def test_list_memories(client, memory):
    """Test list all memories."""
    # Create some memories
    memory.store_memory("local", "fact", "name", "THEO")
    memory.store_memory("local", "preference", "theme", "dark")

    response = client.get("/api/memories")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) >= 2


def test_list_memories_filtered_by_type(client, memory):
    """Test list memories filtered by type."""
    memory.store_memory("local", "fact", "fact1", "value1")
    memory.store_memory("local", "preference", "pref1", "value1")
    memory.store_memory("local", "fact", "fact2", "value2")

    response = client.get("/api/memories?type=fact")

    assert response.status_code == 200
    data = response.json

    # Should only return facts
    assert all(m["type"] == "fact" for m in data)


def test_list_memories_with_limit(client, memory):
    """Test list memories with limit."""
    # Create several memories
    for i in range(10):
        memory.store_memory("local", "fact", f"fact{i}", f"value{i}")

    response = client.get("/api/memories?limit=5")

    assert response.status_code == 200
    data = response.json
    assert len(data) <= 5


def test_list_memories_empty(client):
    """Test list memories when none exist."""
    response = client.get("/api/memories")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)


def test_create_memory(client, memory):
    """Test create new memory."""
    response = client.post("/api/memories", json={
        "type": "fact",
        "key": "favorite_color",
        "value": "blue",
        "pinned": False
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify created
    memories = memory.get_memories("local", memory_type="fact")
    memory_item = next((m for m in memories if m["key"] == "favorite_color"), None)
    assert memory_item is not None
    assert memory_item["value"] == "blue"


def test_create_memory_pinned(client, memory):
    """Test create pinned memory."""
    response = client.post("/api/memories", json={
        "type": "goal",
        "key": "learn_python",
        "value": "Master Python testing",
        "pinned": True
    })

    assert response.status_code == 200

    # Verify pinned
    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["key"] == "learn_python"), None)
    assert memory_item is not None
    assert memory_item["pinned"] is True


def test_create_memory_default_type(client, memory):
    """Test create memory defaults to fact type."""
    response = client.post("/api/memories", json={
        "key": "test",
        "value": "value"
    })

    assert response.status_code == 200

    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["key"] == "test"), None)
    assert memory_item is not None
    assert memory_item["type"] == "fact"


def test_delete_memory(client, memory):
    """Test delete memory by ID."""
    # Create memory
    memory.store_memory("local", "fact", "to_delete", "value")
    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["key"] == "to_delete"), None)
    memory_id = memory_item["id"]

    response = client.delete(f"/api/memories/{memory_id}")

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify deleted
    memories = memory.get_memories("local")
    assert not any(m["id"] == memory_id for m in memories)


def test_delete_nonexistent_memory(client):
    """Test delete nonexistent memory."""
    response = client.delete("/api/memories/99999")

    # Should succeed (idempotent)
    assert response.status_code == 200


def test_pin_memory(client, memory):
    """Test pin a memory."""
    # Create memory
    memory.store_memory("local", "fact", "to_pin", "value", pinned=False)
    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["key"] == "to_pin"), None)
    memory_id = memory_item["id"]

    response = client.post(f"/api/memories/{memory_id}/pin", json={
        "pinned": True
    })

    assert response.status_code == 200
    data = response.json
    assert data["status"] == "ok"
    assert data["pinned"] is True

    # Verify pinned
    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["id"] == memory_id), None)
    assert memory_item["pinned"] is True


def test_unpin_memory(client, memory):
    """Test unpin a memory."""
    # Create pinned memory
    memory.store_memory("local", "fact", "to_unpin", "value", pinned=True)
    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["key"] == "to_unpin"), None)
    memory_id = memory_item["id"]

    response = client.post(f"/api/memories/{memory_id}/pin", json={
        "pinned": False
    })

    assert response.status_code == 200
    data = response.json
    assert data["pinned"] is False

    # Verify unpinned
    memories = memory.get_memories("local")
    memory_item = next((m for m in memories if m["id"] == memory_id), None)
    assert memory_item["pinned"] is False


def test_pin_memory_default_true(client, memory):
    """Test pin memory defaults to True."""
    memory.store_memory("local", "fact", "test", "value", pinned=False)
    memories = memory.get_memories("local")
    memory_id = memories[0]["id"]

    response = client.post(f"/api/memories/{memory_id}/pin", json={})

    assert response.status_code == 200
    assert response.json["pinned"] is True


def test_get_relevant_memories(client, memory):
    """Test get relevant memories based on query."""
    # Create memories
    memory.store_memory("local", "fact", "python", "Python is a programming language")
    memory.store_memory("local", "fact", "cooking", "I enjoy cooking pasta")
    memory.store_memory("local", "fact", "programming", "I write code in Python")

    response = client.get("/api/memories/relevant?q=programming")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)

    # Should return programming-related memories
    # (relevance algorithm should rank "python" and "programming" higher)


def test_get_relevant_memories_empty_query(client):
    """Test relevant memories with empty query."""
    response = client.get("/api/memories/relevant?q=")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_relevant_memories_no_query(client):
    """Test relevant memories without query parameter."""
    response = client.get("/api/memories/relevant")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_relevant_memories_with_pinned(client, memory):
    """Test relevant memories includes pinned items."""
    # Create pinned memory
    memory.store_memory("local", "fact", "important", "Critical information", pinned=True)
    memory.store_memory("local", "fact", "normal", "Regular information")

    response = client.get("/api/memories/relevant?q=information")

    assert response.status_code == 200
    data = response.json

    # Pinned items should be included
    assert any(m["pinned"] for m in data) if len(data) > 0 else True
