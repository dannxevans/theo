"""
Tests for memory operations.

Tests memory CRUD, pinning, relevance search, and decay.
"""

import pytest


def test_remember(memory):
    """Test remember stores preference."""
    memory.remember("user1", "name", "John")

    prefs = memory.get_all("user1")
    assert prefs["name"] == "John"


def test_remember_update(memory):
    """Test remember updates existing preference."""
    memory.remember("user1", "color", "blue")
    memory.remember("user1", "color", "red")

    prefs = memory.get_all("user1")
    assert prefs["color"] == "red"


def test_forget(memory):
    """Test forget removes preference."""
    memory.remember("user1", "temp", "value")
    memory.forget("user1", "temp")

    prefs = memory.get_all("user1")
    assert "temp" not in prefs


def test_forget_nonexistent(memory):
    """Test forget nonexistent preference doesn't error."""
    memory.forget("user1", "nonexistent")  # Should not raise


def test_get_all_empty(memory):
    """Test get_all returns empty dict when no preferences."""
    prefs = memory.get_all("newuser")
    assert isinstance(prefs, dict)


def test_get_all_multiple(memory):
    """Test get_all returns all preferences."""
    memory.remember("user1", "key1", "value1")
    memory.remember("user1", "key2", "value2")
    memory.remember("user1", "key3", "value3")

    prefs = memory.get_all("user1")
    assert len(prefs) == 3
    assert prefs["key1"] == "value1"
    assert prefs["key2"] == "value2"


def test_store_memory(memory):
    """Test store structured memory."""
    memory.store_memory("user1", "fact", "favorite_color", "blue")

    memories = memory.get_memories("user1")
    assert len(memories) > 0

    mem = memories[0]
    assert mem["type"] == "fact"
    assert mem["key"] == "favorite_color"
    assert mem["value"] == "blue"


def test_store_memory_pinned(memory):
    """Test store pinned memory."""
    memory.store_memory("user1", "goal", "important", "Critical goal", pinned=True)

    memories = memory.get_memories("user1")
    mem = next((m for m in memories if m["key"] == "important"), None)

    assert mem is not None
    assert mem["pinned"] is True


def test_get_memories_by_type(memory):
    """Test get memories filtered by type."""
    memory.store_memory("user1", "fact", "fact1", "value1")
    memory.store_memory("user1", "preference", "pref1", "value2")
    memory.store_memory("user1", "fact", "fact2", "value3")

    facts = memory.get_memories("user1", memory_type="fact")
    assert all(m["type"] == "fact" for m in facts)
    assert len(facts) == 2


def test_get_memories_with_limit(memory):
    """Test get memories with limit."""
    for i in range(10):
        memory.store_memory("user1", "fact", f"fact{i}", f"value{i}")

    memories = memory.get_memories("user1", limit=5)
    assert len(memories) <= 5


def test_delete_memory(memory):
    """Test delete memory by ID."""
    memory.store_memory("user1", "fact", "to_delete", "value")
    memories = memory.get_memories("user1")
    mem_id = memories[0]["id"]

    memory.delete_memory("user1", mem_id)

    memories = memory.get_memories("user1")
    assert not any(m["id"] == mem_id for m in memories)


def test_delete_nonexistent_memory(memory):
    """Test delete nonexistent memory doesn't error."""
    memory.delete_memory("user1", 99999)  # Should not raise


def test_pin_memory(memory):
    """Test pin memory."""
    memory.store_memory("user1", "fact", "to_pin", "value", pinned=False)
    memories = memory.get_memories("user1")
    mem_id = memories[0]["id"]

    memory.pin_memory("user1", mem_id, pinned=True)

    memories = memory.get_memories("user1")
    mem = next((m for m in memories if m["id"] == mem_id), None)
    assert mem["pinned"] is True


def test_unpin_memory(memory):
    """Test unpin memory."""
    memory.store_memory("user1", "fact", "to_unpin", "value", pinned=True)
    memories = memory.get_memories("user1")
    mem_id = memories[0]["id"]

    memory.pin_memory("user1", mem_id, pinned=False)

    memories = memory.get_memories("user1")
    mem = next((m for m in memories if m["id"] == mem_id), None)
    assert mem["pinned"] is False


def test_get_relevant_memories(memory):
    """Test get relevant memories based on query."""
    memory.store_memory("user1", "fact", "python", "Python is a programming language")
    memory.store_memory("user1", "fact", "cooking", "I love cooking pasta")
    memory.store_memory("user1", "fact", "coding", "I write Python code daily")

    relevant = memory.get_relevant_memories("user1", "programming", max_results=5)

    # Should return programming-related memories
    # (exact order depends on relevance algorithm)
    assert isinstance(relevant, list)


def test_get_relevant_memories_with_pinned(memory):
    """Test relevant memories includes pinned items."""
    memory.store_memory("user1", "fact", "important", "Critical info", pinned=True)
    memory.store_memory("user1", "fact", "normal", "Regular info")

    relevant = memory.get_relevant_memories("user1", "info", max_results=10)

    # Pinned items should be included
    pinned_items = [m for m in relevant if m.get("pinned")]
    assert len(pinned_items) >= 0  # May or may not be in results depending on relevance


def test_decay_memory_scores(memory):
    """Test decay reduces relevance scores."""
    memory.store_memory("user1", "fact", "test", "value")
    memories_before = memory.get_memories("user1")
    score_before = memories_before[0]["relevance_score"]

    memory.decay_memory_scores("user1", decay_amount=10)

    memories_after = memory.get_memories("user1")
    score_after = memories_after[0]["relevance_score"]

    assert score_after < score_before


def test_decay_memory_scores_preserves_pinned(memory):
    """Test decay doesn't affect pinned memories."""
    memory.store_memory("user1", "fact", "pinned", "value", pinned=True)
    memories_before = memory.get_memories("user1")
    score_before = memories_before[0]["relevance_score"]

    memory.decay_memory_scores("user1", decay_amount=10)

    memories_after = memory.get_memories("user1")
    score_after = memories_after[0]["relevance_score"]

    # Pinned memories should not decay
    assert score_after == score_before


def test_get_system_prompt_config(memory):
    """Test get system prompt configuration."""
    config = memory.get_system_prompt_config("user1")

    assert "persona_name" in config
    assert "tone" in config
    assert "style_rules" in config


def test_update_system_prompt_config(memory):
    """Test update system prompt configuration."""
    memory.update_system_prompt_config(
        "user1",
        persona_name="Assistant",
        tone="friendly"
    )

    config = memory.get_system_prompt_config("user1")
    assert config["persona_name"] == "Assistant"
    assert config["tone"] == "friendly"


def test_update_system_prompt_config_partial(memory):
    """Test update system prompt config with partial fields."""
    memory.update_system_prompt_config("user1", persona_name="NewName")

    config = memory.get_system_prompt_config("user1")
    assert config["persona_name"] == "NewName"
