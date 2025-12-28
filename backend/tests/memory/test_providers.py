"""
Tests for provider operations.

Tests provider CRUD, health tracking, and metadata management.
"""

import pytest
from datetime import datetime


def test_upsert_provider_create(memory):
    """Test create new provider."""
    provider = {
        "id": "gpt4",
        "name": "GPT-4",
        "type": "openai",
        "model": "gpt-4",
        "api_key": "sk-test",
        "enabled": True
    }

    memory.upsert_provider(provider)

    retrieved = memory.get_provider("gpt4")
    assert retrieved is not None
    assert retrieved["name"] == "GPT-4"


def test_upsert_provider_update(memory):
    """Test update existing provider."""
    provider = {
        "id": "test",
        "name": "Original",
        "type": "openai",
        "enabled": True
    }
    memory.upsert_provider(provider)

    updated = {
        "id": "test",
        "name": "Updated",
        "type": "openai",
        "enabled": False
    }
    memory.upsert_provider(updated)

    retrieved = memory.get_provider("test")
    assert retrieved["name"] == "Updated"
    assert retrieved["enabled"] is False


def test_get_provider(memory):
    """Test get specific provider."""
    memory.upsert_provider({
        "id": "test",
        "name": "Test",
        "type": "openai",
        "enabled": True
    })

    provider = memory.get_provider("test")
    assert provider["id"] == "test"
    assert provider["name"] == "Test"


def test_get_provider_nonexistent(memory):
    """Test get nonexistent provider returns None."""
    provider = memory.get_provider("nonexistent")
    assert provider is None


def test_list_providers(memory):
    """Test list all providers."""
    memory.upsert_provider({"id": "p1", "name": "Provider 1", "type": "openai", "enabled": True})
    memory.upsert_provider({"id": "p2", "name": "Provider 2", "type": "anthropic", "enabled": True})

    providers = memory.list_providers()
    assert len(providers) >= 2


def test_list_providers_empty(memory):
    """Test list providers when none exist."""
    providers = memory.list_providers()
    assert isinstance(providers, list)


def test_delete_provider(memory):
    """Test delete provider."""
    memory.upsert_provider({"id": "to_delete", "name": "Delete Me", "type": "openai", "enabled": True})

    memory.delete_provider("to_delete")

    provider = memory.get_provider("to_delete")
    assert provider is None


def test_init_provider_metadata(memory):
    """Test initialize provider metadata."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})

    memory.init_provider_metadata("test", cost_per_1k_input=10, cost_per_1k_output=30)

    metadata = memory.get_provider_metadata("test")
    assert metadata is not None
    assert metadata["cost_per_1k_input_tokens"] == 10
    assert metadata["cost_per_1k_output_tokens"] == 30


def test_get_provider_metadata(memory):
    """Test get provider metadata."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    metadata = memory.get_provider_metadata("test")
    assert "total_requests" in metadata
    assert "failed_requests" in metadata
    assert "health_status" in metadata


def test_get_provider_metadata_nonexistent(memory):
    """Test get metadata for nonexistent provider."""
    metadata = memory.get_provider_metadata("nonexistent")
    assert metadata is None


def test_get_all_provider_metadata(memory):
    """Test get metadata for all providers."""
    memory.upsert_provider({"id": "p1", "name": "P1", "type": "openai", "enabled": True})
    memory.upsert_provider({"id": "p2", "name": "P2", "type": "anthropic", "enabled": True})
    memory.init_provider_metadata("p1")
    memory.init_provider_metadata("p2")

    all_metadata = memory.get_all_provider_metadata()
    assert isinstance(all_metadata, dict)
    assert "p1" in all_metadata
    assert "p2" in all_metadata


def test_log_request(memory):
    """Test log provider request."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.log_request(
        session_id="session1",
        provider_id="test",
        intent="general",
        success=True,
        latency_ms=150,
        input_tokens=100,
        output_tokens=200,
        estimated_cost=50
    )

    # Request should be logged
    metadata = memory.get_provider_metadata("test")
    assert metadata["total_requests"] >= 1


def test_update_provider_health_success(memory):
    """Test update provider health on success."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.update_provider_health("test", success=True, latency_ms=100)

    metadata = memory.get_provider_metadata("test")
    assert metadata["total_requests"] > 0
    assert metadata["last_success_at"] is not None


def test_update_provider_health_failure(memory):
    """Test update provider health on failure."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.update_provider_health("test", success=False)

    metadata = memory.get_provider_metadata("test")
    assert metadata["failed_requests"] > 0
    assert metadata["last_failure_at"] is not None


def test_get_provider_health_summary(memory):
    """Test get health summary for all providers."""
    memory.upsert_provider({"id": "p1", "name": "P1", "type": "openai", "enabled": True})
    memory.init_provider_metadata("p1")
    memory.update_provider_health("p1", success=True)

    summary = memory.get_provider_health_summary()
    assert isinstance(summary, dict)


def test_estimate_cost(memory):
    """Test estimate request cost."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test", cost_per_1k_input=10, cost_per_1k_output=30)

    cost = memory.estimate_cost("test", input_tokens=1000, output_tokens=500)

    # 1000 tokens * 10 + 500 tokens * 15 = 10 + 15 = 25 micro-dollars
    assert cost > 0


def test_delete_provider_metadata(memory):
    """Test delete provider metadata."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.delete_provider_metadata("test")

    metadata = memory.get_provider_metadata("test")
    assert metadata is None


def test_provider_lifecycle(memory):
    """Test complete provider lifecycle."""
    # Create provider
    memory.upsert_provider({
        "id": "lifecycle",
        "name": "Lifecycle Test",
        "type": "openai",
        "model": "gpt-4",
        "enabled": True
    })

    # Initialize metadata
    memory.init_provider_metadata("lifecycle", cost_per_1k_input=10, cost_per_1k_output=30)

    # Log some requests
    memory.update_provider_health("lifecycle", success=True, latency_ms=100)
    memory.update_provider_health("lifecycle", success=True, latency_ms=120)
    memory.update_provider_health("lifecycle", success=False)

    # Check metadata
    metadata = memory.get_provider_metadata("lifecycle")
    assert metadata["total_requests"] == 3
    assert metadata["failed_requests"] == 1

    # Delete provider
    memory.delete_provider("lifecycle")
    memory.delete_provider_metadata("lifecycle")

    # Verify deleted
    assert memory.get_provider("lifecycle") is None
    assert memory.get_provider_metadata("lifecycle") is None
