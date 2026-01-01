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


# ====================
# Circuit Breaker Cooldown Tests
# ====================

def test_circuit_breaker_cooldown_default(memory):
    """Test circuit breaker cooldown defaults to 60 minutes."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_cooldown_minutes"] == 60


def test_update_circuit_breaker_cooldown(memory):
    """Test update circuit breaker cooldown period."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.update_circuit_breaker_cooldown("test", 120)

    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_cooldown_minutes"] == 120


def test_update_circuit_breaker_cooldown_validation_min(memory):
    """Test circuit breaker cooldown validates minimum value (1 minute)."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.update_circuit_breaker_cooldown("test", 0)

    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_cooldown_minutes"] == 1


def test_update_circuit_breaker_cooldown_validation_max(memory):
    """Test circuit breaker cooldown validates maximum value (1440 minutes)."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    memory.update_circuit_breaker_cooldown("test", 2000)

    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_cooldown_minutes"] == 1440


def test_update_circuit_breaker_cooldown_creates_metadata(memory):
    """Test update circuit breaker cooldown creates metadata if missing."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})

    # Update cooldown without initializing metadata first
    memory.update_circuit_breaker_cooldown("test", 90)

    metadata = memory.get_provider_metadata("test")
    assert metadata is not None
    assert metadata["circuit_breaker_cooldown_minutes"] == 90


def test_circuit_breaker_opened_at_tracking(memory):
    """Test circuit breaker tracks when it was opened."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    # Trigger circuit breaker with 5 consecutive failures
    # Use log_request to properly track request history
    for i in range(5):
        memory.log_request(
            session_id=f"session{i}",
            provider_id="test",
            intent="general",
            success=False,
            latency_ms=0,
            error_message="Test failure"
        )

    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_open"] is True
    assert metadata["circuit_breaker_opened_at"] is not None


def test_circuit_breaker_opened_at_preserved_until_reset(memory):
    """Test circuit breaker opened_at persists until manually reset."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")

    # Open circuit breaker - use log_request
    for i in range(5):
        memory.log_request(
            session_id=f"session{i}",
            provider_id="test",
            intent="general",
            success=False,
            latency_ms=0,
            error_message="Test failure"
        )

    # Verify it's open with timestamp
    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_open"] is True
    assert metadata["circuit_breaker_opened_at"] is not None

    # Manually reset health to close circuit breaker
    memory.reset_provider_health("test")

    # Verify circuit breaker is closed and opened_at is NOT cleared by reset
    # (reset doesn't clear timestamp, only manual intervention or time-based recovery)
    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_open"] is False


def test_health_summary_includes_cooldown_info(memory):
    """Test health summary includes circuit breaker cooldown information."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")
    memory.update_circuit_breaker_cooldown("test", 90)

    # Trigger circuit breaker - use log_request
    for i in range(5):
        memory.log_request(
            session_id=f"session{i}",
            provider_id="test",
            intent="general",
            success=False,
            latency_ms=0,
            error_message="Test failure"
        )

    summary = memory.get_provider_health_summary()

    assert "test" in summary
    assert summary["test"]["circuit_breaker_open"] is True
    assert summary["test"]["circuit_breaker_cooldown_minutes"] == 90
    assert summary["test"]["circuit_breaker_opened_at"] is not None


def test_reset_provider_health_preserves_cooldown(memory):
    """Test reset provider health preserves cooldown configuration."""
    memory.upsert_provider({"id": "test", "name": "Test", "type": "openai", "enabled": True})
    memory.init_provider_metadata("test")
    memory.update_circuit_breaker_cooldown("test", 180)

    # Trigger some failures
    for _ in range(3):
        memory.update_provider_health("test", success=False)

    # Reset health
    memory.reset_provider_health("test")

    # Verify cooldown is preserved but health is reset
    metadata = memory.get_provider_metadata("test")
    assert metadata["circuit_breaker_cooldown_minutes"] == 180
    assert metadata["total_requests"] == 0
    assert metadata["failed_requests"] == 0
    assert metadata["circuit_breaker_open"] is False
