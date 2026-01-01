"""
Tests for routing routes with authentication and user_id.

Tests cover:
- Routing preference CRUD operations respect user_id from g.user_id
- User isolation for routing preferences
- Authentication headers required
"""

import pytest
import json


def test_get_routing_preferences_with_auth(client, auth_headers, memory, test_user):
    """Test getting routing preferences with auth token."""
    # Create a test intent first
    memory.create_intent(
        user_id=str(test_user["id"]),
        intent_id="test_intent",
        name="Test Intent",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    # Set a routing preference
    memory.set_routing_preference(
        user_id=str(test_user["id"]),
        intent="test_intent",
        provider_id="openai"
    )

    response = client.get('/api/routing', headers=auth_headers)

    assert response.status_code == 200
    data = json.loads(response.data)

    # Should be a dict with intent -> provider_id mappings
    assert isinstance(data, dict)
    assert data.get('test_intent')['provider_id'] == 'openai'


def test_set_routing_preference_with_auth(client, auth_headers, memory, test_user):
    """Test setting a routing preference with auth token."""
    # Create intent first
    memory.create_intent(
        user_id=str(test_user["id"]),
        intent_id="test_intent",
        name="Test Intent",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    response = client.post(
        '/api/routing',
        headers=auth_headers,
        data=json.dumps({
            'intent': 'test_intent',
            'provider_id': 'anthropic'
        })
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify it was set
    prefs = memory.get_routing_preferences(str(test_user["id"]))
    assert prefs.get('test_intent')['provider_id'] == 'anthropic'


def test_delete_routing_preference_with_auth(client, auth_headers, memory, test_user):
    """Test deleting a routing preference with auth token."""
    # Create intent and set preference first
    memory.create_intent(
        user_id=str(test_user["id"]),
        intent_id="test_intent",
        name="Test Intent",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    memory.set_routing_preference(
        user_id=str(test_user["id"]),
        intent="test_intent",
        provider_id="openai"
    )

    # Delete it
    response = client.delete(
        '/api/routing/test_intent',
        headers=auth_headers
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify deletion
    prefs = memory.get_routing_preferences(str(test_user["id"]))
    assert 'test_intent' not in prefs


def test_user_isolation_routing_preferences(memory, test_user, admin_user):
    """Test that users cannot see each other's routing preferences."""
    # Create intents for each user
    memory.create_intent(str(test_user["id"]), "intent1", "Intent 1", "", "test", 50, True)
    memory.create_intent(str(admin_user["id"]), "intent2", "Intent 2", "", "test", 50, True)

    # Set routing preferences
    memory.set_routing_preference(str(test_user["id"]), "intent1", "openai")
    memory.set_routing_preference(str(admin_user["id"]), "intent2", "anthropic")

    # Get preferences for each user
    user1_prefs = memory.get_routing_preferences(str(test_user["id"]))
    user2_prefs = memory.get_routing_preferences(str(admin_user["id"]))

    # Each user should only see their own preferences
    assert 'intent1' in user1_prefs
    assert 'intent2' not in user1_prefs

    assert 'intent2' in user2_prefs
    assert 'intent1' not in user2_prefs


def test_routing_preference_upsert(memory, test_user):
    """Test that setting a routing preference twice updates it."""
    # Create intent
    memory.create_intent(str(test_user["id"]), "test_intent", "Test", "", "test", 50, True)

    # Set initial preference
    memory.set_routing_preference(str(test_user["id"]), "test_intent", "openai")
    prefs = memory.get_routing_preferences(str(test_user["id"]))
    assert prefs['test_intent']['provider_id'] == 'openai'

    # Update preference
    memory.set_routing_preference(str(test_user["id"]), "test_intent", "anthropic")
    prefs = memory.get_routing_preferences(str(test_user["id"]))
    assert prefs['test_intent']['provider_id'] == 'anthropic'


def test_get_routing_preferences_empty(client, auth_headers):
    """Test getting routing preferences when none are set."""
    response = client.get('/api/routing', headers=auth_headers)

    assert response.status_code == 200
    data = json.loads(response.data)

    # Should return empty dict
    assert isinstance(data, dict)
