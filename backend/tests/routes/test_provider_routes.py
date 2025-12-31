"""
Tests for provider routes.

Tests AI provider CRUD operations, health monitoring, and metadata management.
"""

import pytest
from unittest.mock import patch


def test_list_providers(client, memory, sample_provider):
    """Test list all providers."""
    response = client.get("/api/providers")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)
    assert len(data) > 0

    # Check provider structure (API keys should be hidden)
    provider = data[0]
    assert "id" in provider
    assert "name" in provider
    assert "type" in provider
    assert "api_key" not in provider


def test_list_providers_empty(client):
    """Test list providers when none exist."""
    response = client.get("/api/providers")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, list)


def test_list_providers_no_api_keys_exposed(client, memory):
    """Test list providers never exposes API keys."""
    memory.upsert_provider({
        "id": "secret-provider",
        "name": "Secret Provider",
        "type": "openai",
        "model": "gpt-4",
        "api_key": "sk-super-secret-key",
        "enabled": True
    })

    response = client.get("/api/providers")

    assert response.status_code == 200
    data = response.json

    # Verify no API keys in response
    for provider in data:
        assert "api_key" not in provider


def test_upsert_provider_create(client, memory):
    """Test create new provider."""
    response = client.post("/api/providers", json={
        "id": "new-provider",
        "name": "New Provider",
        "type": "anthropic",
        "model": "claude-3",
        "api_key": "sk-test-key",
        "enabled": True
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify created
    provider = memory.get_provider("new-provider")
    assert provider is not None
    assert provider["name"] == "New Provider"

    # Verify metadata initialized
    metadata = memory.get_provider_metadata("new-provider")
    assert metadata is not None


def test_upsert_provider_update(client, memory, sample_provider):
    """Test update existing provider."""
    response = client.post("/api/providers", json={
        "id": sample_provider["id"],
        "name": "Updated Name",
        "type": sample_provider["type"],
        "model": "updated-model",
        "api_key": sample_provider["api_key"],
        "enabled": False
    })

    assert response.status_code == 200

    # Verify updated
    provider = memory.get_provider(sample_provider["id"])
    assert provider["name"] == "Updated Name"
    assert provider["model"] == "updated-model"
    assert provider["enabled"] is False


def test_upsert_provider_optional_fields(client, memory):
    """Test create provider with optional fields."""
    response = client.post("/api/providers", json={
        "id": "minimal-provider",
        "name": "Minimal Provider",
        "type": "openai",
        "base_url": "https://custom.openai.com",
        "model": "gpt-4"
    })

    assert response.status_code == 200

    provider = memory.get_provider("minimal-provider")
    assert provider is not None
    assert provider["base_url"] == "https://custom.openai.com"


def test_delete_provider(client, memory, sample_provider):
    """Test delete provider."""
    response = client.delete(f"/api/providers/{sample_provider['id']}")

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify deleted
    provider = memory.get_provider(sample_provider["id"])
    assert provider is None

    # Verify metadata cleaned up
    metadata = memory.get_provider_metadata(sample_provider["id"])
    assert metadata is None


def test_delete_nonexistent_provider(client):
    """Test delete nonexistent provider."""
    response = client.delete("/api/providers/nonexistent")

    # Should succeed (idempotent)
    assert response.status_code == 200


def test_get_provider_health(client, memory, sample_provider):
    """Test get provider health summary."""
    # Log some requests to create health data
    memory.update_provider_health(sample_provider["id"], success=True, latency_ms=100)
    memory.update_provider_health(sample_provider["id"], success=True, latency_ms=150)
    memory.update_provider_health(sample_provider["id"], success=False)

    response = client.get("/api/providers/health")

    assert response.status_code == 200
    data = response.json

    # Check structure
    assert sample_provider["id"] in data
    provider_health = data[sample_provider["id"]]
    assert "total_requests" in provider_health
    assert "failure_rate" in provider_health
    assert "health_status" in provider_health


def test_get_provider_health_empty(client):
    """Test get provider health when no providers exist."""
    response = client.get("/api/providers/health")

    assert response.status_code == 200
    data = response.json
    assert isinstance(data, dict)


def test_get_provider_metadata(client, memory, sample_provider):
    """Test get metadata for specific provider."""
    response = client.get(f"/api/providers/{sample_provider['id']}/metadata")

    assert response.status_code == 200
    data = response.json

    assert "total_requests" in data
    assert "failed_requests" in data
    assert "health_status" in data
    assert "avg_latency_ms" in data


def test_get_provider_metadata_not_found(client):
    """Test get metadata for nonexistent provider."""
    response = client.get("/api/providers/nonexistent/metadata")

    assert response.status_code == 404
    assert "error" in response.json


def test_update_provider_metadata(client, memory, sample_provider):
    """Test update provider cost metadata."""
    response = client.post(f"/api/providers/{sample_provider['id']}/metadata", json={
        "cost_per_1k_input": 100,
        "cost_per_1k_output": 300
    })

    assert response.status_code == 200
    assert response.json["status"] == "ok"

    # Verify updated
    metadata = memory.get_provider_metadata(sample_provider["id"])
    assert metadata["cost_per_1k_input_tokens"] == 100
    assert metadata["cost_per_1k_output_tokens"] == 300


def test_update_provider_metadata_defaults(client, memory, sample_provider):
    """Test update provider metadata with default values."""
    response = client.post(f"/api/providers/{sample_provider['id']}/metadata", json={})

    assert response.status_code == 200

    # Should set to 0
    metadata = memory.get_provider_metadata(sample_provider["id"])
    assert metadata["cost_per_1k_input_tokens"] == 0
    assert metadata["cost_per_1k_output_tokens"] == 0
