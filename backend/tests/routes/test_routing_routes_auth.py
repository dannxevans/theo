"""
Tests for routing routes with authentication and user_id.

Tests cover:
- Routing preference CRUD operations respect user_id from g.user_id
- User isolation for routing preferences
- Authentication headers required
"""

import pytest
import json
from app import app
from core.memory import MemoryStore
from config import Config


@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def memory_store():
    """Get the memory store instance."""
    return MemoryStore(Config.DATABASE_URL)


@pytest.fixture
def auth_token(memory_store):
    """Create a test user and return auth token."""
    user_id = memory_store.create_user("test_user", "password123")
    token = memory_store.create_auth_session(user_id)

    # Create a test intent for routing
    memory_store.create_intent(
        user_id=str(user_id),
        intent_id="test_intent",
        name="Test Intent",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    return token


def test_get_routing_preferences_with_auth(client, auth_token, memory_store):
    """Test getting routing preferences with auth token."""
    # Set a routing preference
    session = memory_store.get_auth_session(auth_token)
    user_id = str(session["user_id"])

    memory_store.set_routing_preference(
        user_id=user_id,
        intent="test_intent",
        provider_id="openai"
    )

    response = client.get(
        '/api/routing',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)

    # Should be a dict with intent -> provider_id mappings
    assert isinstance(data, dict)
    assert data.get('test_intent') == 'openai'


def test_set_routing_preference_with_auth(client, auth_token, memory_store):
    """Test setting a routing preference with auth token."""
    response = client.post(
        '/api/routing',
        headers={
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        },
        data=json.dumps({
            'intent': 'test_intent',
            'provider_id': 'anthropic'
        })
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify it was set
    session = memory_store.get_auth_session(auth_token)
    user_id = str(session["user_id"])

    prefs = memory_store.get_routing_preferences(user_id)
    assert prefs.get('test_intent') == 'anthropic'


def test_delete_routing_preference_with_auth(client, auth_token, memory_store):
    """Test deleting a routing preference with auth token."""
    # Set preference first
    session = memory_store.get_auth_session(auth_token)
    user_id = str(session["user_id"])

    memory_store.set_routing_preference(
        user_id=user_id,
        intent="test_intent",
        provider_id="openai"
    )

    # Delete it
    response = client.delete(
        '/api/routing/test_intent',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify deletion
    prefs = memory_store.get_routing_preferences(user_id)
    assert 'test_intent' not in prefs


def test_user_isolation_routing_preferences(memory_store):
    """Test that users cannot see each other's routing preferences."""
    # Create two users
    user1_id = memory_store.create_user("user1", "password123")
    user2_id = memory_store.create_user("user2", "password456")

    # Create intents for each user
    memory_store.create_intent(str(user1_id), "intent1", "Intent 1", "", "test", 50, True)
    memory_store.create_intent(str(user2_id), "intent2", "Intent 2", "", "test", 50, True)

    # Set routing preferences
    memory_store.set_routing_preference(str(user1_id), "intent1", "openai")
    memory_store.set_routing_preference(str(user2_id), "intent2", "anthropic")

    # Get preferences for each user
    user1_prefs = memory_store.get_routing_preferences(str(user1_id))
    user2_prefs = memory_store.get_routing_preferences(str(user2_id))

    # Each user should only see their own preferences
    assert 'intent1' in user1_prefs
    assert 'intent2' not in user1_prefs

    assert 'intent2' in user2_prefs
    assert 'intent1' not in user2_prefs


def test_routing_preference_upsert(memory_store):
    """Test that setting a routing preference twice updates it."""
    user_id = memory_store.create_user("test_user", "password123")
    memory_store.create_intent(str(user_id), "test_intent", "Test", "", "test", 50, True)

    # Set initial preference
    memory_store.set_routing_preference(str(user_id), "test_intent", "openai")
    prefs = memory_store.get_routing_preferences(str(user_id))
    assert prefs['test_intent'] == 'openai'

    # Update preference
    memory_store.set_routing_preference(str(user_id), "test_intent", "anthropic")
    prefs = memory_store.get_routing_preferences(str(user_id))
    assert prefs['test_intent'] == 'anthropic'


def test_get_routing_preferences_empty(client, auth_token):
    """Test getting routing preferences when none are set."""
    response = client.get(
        '/api/routing',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)

    # Should return empty dict
    assert isinstance(data, dict)
    assert len(data) == 0 or all(v is None for v in data.values())
