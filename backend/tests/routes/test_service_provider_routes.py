"""
Tests for service provider routes.

Tests service provider CRUD operations.
"""

import pytest
from datetime import datetime


def test_get_service_providers(client, memory, auth_headers, test_user):
    """Test get all service providers."""
    # Create providers
    memory.store_service_provider(
        user_id=test_user["id"],
        name="Test Calendar",
        category="calendar",
        provider_type="m365"
    )

    response = client.get("/api/service-providers", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert "providers" in data
    assert len(data["providers"]) > 0


def test_get_service_providers_filtered(client, memory, auth_headers, test_user):
    """Test get service providers filtered by category."""
    memory.store_service_provider(
        user_id=test_user["id"],
        name="Calendar",
        category="calendar",
        provider_type="m365"
    )
    memory.store_service_provider(
        user_id=test_user["id"],
        name="Email",
        category="email",
        provider_type="smtp"
    )

    response = client.get("/api/service-providers?category=calendar", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    providers = data["providers"]

    # Should only return calendar providers
    assert all(p["category"] == "calendar" for p in providers)


def test_get_service_providers_empty(client, auth_headers):
    """Test get service providers when none exist."""
    response = client.get("/api/service-providers", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["providers"] == []


def test_get_service_providers_unauthorized(client):
    """Test get service providers requires authentication."""
    response = client.get("/api/service-providers")

    assert response.status_code == 401


def test_create_service_provider(client, memory, auth_headers, test_user):
    """Test create service provider."""
    response = client.post("/api/service-providers", headers=auth_headers, json={
        "name": "Test Provider",
        "category": "calendar",
        "provider_type": "google",
        "trust_level": "manual"
    })

    assert response.status_code == 201
    data = response.json
    assert data["success"] is True
    assert "provider_id" in data

    # Verify created
    provider = memory.get_service_provider(data["provider_id"])
    assert provider is not None
    assert provider["name"] == "Test Provider"


def test_create_service_provider_with_optional_fields(client, auth_headers):
    """Test create service provider with optional fields."""
    response = client.post("/api/service-providers", headers=auth_headers, json={
        "name": "Full Provider",
        "category": "calendar",
        "provider_type": "m365",
        "capabilities": '["read_calendar", "write_calendar"]',
        "api_base_url": "https://graph.microsoft.com",
        "auth_method": "oauth2",
        "trust_level": "confirm",
        "booking_method": "api",
        "preferred_for_category": True
    })

    assert response.status_code == 201


def test_create_service_provider_missing_fields(client, auth_headers):
    """Test create service provider with missing required fields."""
    response = client.post("/api/service-providers", headers=auth_headers, json={
        "name": "Incomplete"
    })

    assert response.status_code == 400
    assert "error" in response.json


def test_create_service_provider_unauthorized(client):
    """Test create service provider requires authentication."""
    response = client.post("/api/service-providers", json={
        "name": "Test",
        "category": "calendar",
        "provider_type": "m365"
    })

    assert response.status_code == 401


def test_get_service_provider_by_id(client, memory, auth_headers, test_user):
    """Test get specific service provider."""
    provider_id = memory.store_service_provider(
        user_id=test_user["id"],
        name="Test Provider",
        category="calendar",
        provider_type="m365"
    )

    response = client.get(f"/api/service-providers/{provider_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert "provider" in data
    assert data["provider"]["id"] == provider_id


def test_get_service_provider_not_found(client, auth_headers):
    """Test get nonexistent service provider."""
    response = client.get("/api/service-providers/99999", headers=auth_headers)

    assert response.status_code == 404


def test_get_service_provider_wrong_user(client, memory, auth_headers, test_user, admin_user):
    """Test get service provider from different user."""
    # Create provider for admin user
    provider_id = memory.store_service_provider(
        user_id=admin_user["id"],
        name="Admin Provider",
        category="calendar",
        provider_type="m365"
    )

    # Try to access as test_user
    response = client.get(f"/api/service-providers/{provider_id}", headers=auth_headers)

    assert response.status_code == 403


def test_update_service_provider(client, memory, auth_headers, test_user):
    """Test update service provider."""
    provider_id = memory.store_service_provider(
        user_id=test_user["id"],
        name="Original Name",
        category="calendar",
        provider_type="m365"
    )

    response = client.put(f"/api/service-providers/{provider_id}", headers=auth_headers, json={
        "name": "Updated Name",
        "is_enabled": False
    })

    assert response.status_code == 200
    data = response.json
    assert data["success"] is True

    # Verify updated
    provider = memory.get_service_provider(provider_id)
    assert provider["name"] == "Updated Name"
    assert provider["is_enabled"] is False


def test_update_service_provider_not_found(client, auth_headers):
    """Test update nonexistent service provider."""
    response = client.put("/api/service-providers/99999", headers=auth_headers, json={
        "name": "Updated"
    })

    assert response.status_code == 404


def test_update_service_provider_wrong_user(client, memory, auth_headers, admin_user):
    """Test update service provider from different user."""
    provider_id = memory.store_service_provider(
        user_id=admin_user["id"],
        name="Admin Provider",
        category="calendar",
        provider_type="m365"
    )

    response = client.put(f"/api/service-providers/{provider_id}", headers=auth_headers, json={
        "name": "Hacked"
    })

    assert response.status_code == 403


def test_delete_service_provider(client, memory, auth_headers, test_user):
    """Test delete service provider."""
    provider_id = memory.store_service_provider(
        user_id=test_user["id"],
        name="To Delete",
        category="calendar",
        provider_type="m365"
    )

    response = client.delete(f"/api/service-providers/{provider_id}", headers=auth_headers)

    assert response.status_code == 200
    data = response.json
    assert data["success"] is True

    # Verify deleted
    provider = memory.get_service_provider(provider_id)
    assert provider is None


def test_delete_service_provider_not_found(client, auth_headers):
    """Test delete nonexistent service provider."""
    response = client.delete("/api/service-providers/99999", headers=auth_headers)

    assert response.status_code == 404


def test_delete_service_provider_wrong_user(client, memory, auth_headers, admin_user):
    """Test delete service provider from different user."""
    provider_id = memory.store_service_provider(
        user_id=admin_user["id"],
        name="Admin Provider",
        category="calendar",
        provider_type="m365"
    )

    response = client.delete(f"/api/service-providers/{provider_id}", headers=auth_headers)

    assert response.status_code == 403
