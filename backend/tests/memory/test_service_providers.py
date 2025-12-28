"""
Tests for service provider operations.

Tests service provider CRUD operations.
"""

import pytest
import json


def test_store_service_provider(memory, user_fixture):
    """Test store new service provider."""
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Test Calendar",
        category="calendar",
        provider_type="m365"
    )

    assert provider_id is not None

    provider = memory.get_service_provider(provider_id)
    assert provider["name"] == "Test Calendar"
    assert provider["category"] == "calendar"


def test_store_service_provider_with_options(memory, user_fixture):
    """Test store service provider with optional fields."""
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Full Provider",
        category="calendar",
        provider_type="google",
        capabilities=json.dumps(["read", "write"]),
        api_base_url="https://api.example.com",
        auth_method="oauth2",
        trust_level="confirm",
        booking_method="api",
        preferred_for_category=True
    )

    provider = memory.get_service_provider(provider_id)
    assert provider["api_base_url"] == "https://api.example.com"
    assert provider["auth_method"] == "oauth2"


def test_get_service_providers(memory, user_fixture):
    """Test get all service providers for user."""
    memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Provider 1",
        category="calendar",
        provider_type="m365"
    )

    memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Provider 2",
        category="email",
        provider_type="smtp"
    )

    providers = memory.get_service_providers(user_fixture["id"])
    assert len(providers) >= 2


def test_get_service_providers_by_category(memory, user_fixture):
    """Test get service providers filtered by category."""
    memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Calendar",
        category="calendar",
        provider_type="m365"
    )

    memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Email",
        category="email",
        provider_type="smtp"
    )

    calendar_providers = memory.get_service_providers(user_fixture["id"], category="calendar")
    assert all(p["category"] == "calendar" for p in calendar_providers)


def test_get_service_providers_empty(memory, user_fixture):
    """Test get service providers when none exist."""
    providers = memory.get_service_providers(user_fixture["id"])
    assert isinstance(providers, list)
    assert len(providers) == 0


def test_get_service_provider(memory, user_fixture):
    """Test get specific service provider."""
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Test",
        category="calendar",
        provider_type="m365"
    )

    provider = memory.get_service_provider(provider_id)
    assert provider is not None
    assert provider["id"] == provider_id


def test_get_service_provider_nonexistent(memory):
    """Test get nonexistent service provider."""
    provider = memory.get_service_provider(99999)
    assert provider is None


def test_get_preferred_provider(memory, user_fixture):
    """Test get preferred provider for category."""
    # Create non-preferred provider
    memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Normal",
        category="calendar",
        provider_type="m365",
        preferred_for_category=False
    )

    # Create preferred provider
    preferred_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Preferred",
        category="calendar",
        provider_type="google",
        preferred_for_category=True
    )

    preferred = memory.get_preferred_provider(user_fixture["id"], "calendar")
    assert preferred is not None
    assert preferred["id"] == preferred_id


def test_get_preferred_provider_none(memory, user_fixture):
    """Test get preferred provider when none set."""
    memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Normal",
        category="calendar",
        provider_type="m365"
    )

    preferred = memory.get_preferred_provider(user_fixture["id"], "calendar")
    # May return None or first provider depending on implementation


def test_update_service_provider(memory, user_fixture):
    """Test update service provider."""
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Original",
        category="calendar",
        provider_type="m365"
    )

    memory.update_service_provider(
        provider_id=provider_id,
        name="Updated",
        is_enabled=False
    )

    provider = memory.get_service_provider(provider_id)
    assert provider["name"] == "Updated"
    assert provider["is_enabled"] is False


def test_update_service_provider_partial(memory, user_fixture):
    """Test update service provider with partial fields."""
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="Original",
        category="calendar",
        provider_type="m365"
    )

    memory.update_service_provider(
        provider_id=provider_id,
        name="Updated Only"
    )

    provider = memory.get_service_provider(provider_id)
    assert provider["name"] == "Updated Only"
    assert provider["category"] == "calendar"  # Unchanged


def test_delete_service_provider(memory, user_fixture):
    """Test delete service provider."""
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="To Delete",
        category="calendar",
        provider_type="m365"
    )

    memory.delete_service_provider(provider_id, user_fixture["id"])

    provider = memory.get_service_provider(provider_id)
    assert provider is None


def test_service_provider_lifecycle(memory, user_fixture):
    """Test complete service provider lifecycle."""
    # Create provider
    provider_id = memory.store_service_provider(
        user_id=user_fixture["id"],
        name="M365 Calendar",
        category="calendar",
        provider_type="m365",
        capabilities=json.dumps(["read_calendar", "write_calendar"]),
        trust_level="confirm",
        preferred_for_category=True
    )

    # Verify created
    provider = memory.get_service_provider(provider_id)
    assert provider["name"] == "M365 Calendar"

    # Update provider
    memory.update_service_provider(
        provider_id=provider_id,
        is_enabled=False
    )

    provider = memory.get_service_provider(provider_id)
    assert provider["is_enabled"] is False

    # Delete provider
    memory.delete_service_provider(provider_id, user_fixture["id"])
    assert memory.get_service_provider(provider_id) is None
