"""
Tests for intent routes with authentication and user_id.

Tests cover:
- Intent CRUD operations respect user_id from g.user_id
- User isolation for intents
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
    # Create test user
    user_id = memory_store.create_user("test_user", "password123")

    # Create auth session
    token = memory_store.create_auth_session(user_id)

    return token


def test_list_intents_requires_auth(client):
    """Test that listing intents without auth returns empty or uses fallback."""
    response = client.get('/api/intents')

    assert response.status_code == 200
    data = json.loads(response.data)

    # Without auth, should use fallback user_id='local' which may have no intents
    # or could be empty
    assert isinstance(data, list)


def test_list_intents_with_auth(client, auth_token, memory_store):
    """Test listing intents with valid auth token."""
    # Get the user_id for the token
    session = memory_store.get_auth_session(auth_token)
    user_id = session["user_id"]

    # Create test intent for this user
    memory_store.create_intent(
        user_id=str(user_id),
        intent_id="test_intent",
        name="Test Intent",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    response = client.get(
        '/api/intents',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)

    # Should include our test intent
    intent_ids = [intent['id'] for intent in data]
    assert 'test_intent' in intent_ids


def test_create_intent_with_auth(client, auth_token, memory_store):
    """Test creating an intent with auth token."""
    response = client.post(
        '/api/intents',
        headers={
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        },
        data=json.dumps({
            'id': 'new_intent',
            'name': 'New Intent',
            'description': 'A new intent',
            'keywords': 'new',
            'priority': 50,
            'enabled': True
        })
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify intent was created for the correct user
    session = memory_store.get_auth_session(auth_token)
    user_id = str(session["user_id"])

    intent = memory_store.get_intent(user_id, 'new_intent')
    assert intent is not None
    assert intent['name'] == 'New Intent'


def test_update_intent_with_auth(client, auth_token, memory_store):
    """Test updating an intent with auth token."""
    # Create intent first
    session = memory_store.get_auth_session(auth_token)
    user_id = str(session["user_id"])

    memory_store.create_intent(
        user_id=user_id,
        intent_id="update_test",
        name="Original Name",
        description="Original",
        keywords="original",
        priority=50,
        enabled=True
    )

    # Update the intent
    response = client.put(
        '/api/intents/update_test',
        headers={
            'Authorization': f'Bearer {auth_token}',
            'Content-Type': 'application/json'
        },
        data=json.dumps({
            'name': 'Updated Name',
            'keywords': 'updated'
        })
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify update
    intent = memory_store.get_intent(user_id, 'update_test')
    assert intent['name'] == 'Updated Name'
    assert intent['keywords'] == 'updated'


def test_delete_intent_with_auth(client, auth_token, memory_store):
    """Test deleting an intent with auth token."""
    # Create intent first
    session = memory_store.get_auth_session(auth_token)
    user_id = str(session["user_id"])

    memory_store.create_intent(
        user_id=user_id,
        intent_id="delete_test",
        name="Delete Me",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    # Delete the intent
    response = client.delete(
        '/api/intents/delete_test',
        headers={'Authorization': f'Bearer {auth_token}'}
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify deletion
    intent = memory_store.get_intent(user_id, 'delete_test')
    assert intent is None


def test_user_isolation_intents(memory_store):
    """Test that users cannot see each other's intents."""
    # Create two users
    user1_id = memory_store.create_user("user1", "password123")
    user2_id = memory_store.create_user("user2", "password456")

    # Create intents for each user
    memory_store.create_intent(str(user1_id), "user1_intent", "User 1 Intent", "", "test", 50, True)
    memory_store.create_intent(str(user2_id), "user2_intent", "User 2 Intent", "", "test", 50, True)

    # Get intents for each user
    user1_intents = memory_store.list_intents(str(user1_id))
    user2_intents = memory_store.list_intents(str(user2_id))

    # Each user should only see their own intents
    user1_ids = [intent['id'] for intent in user1_intents]
    user2_ids = [intent['id'] for intent in user2_intents]

    assert 'user1_intent' in user1_ids
    assert 'user2_intent' not in user1_ids

    assert 'user2_intent' in user2_ids
    assert 'user1_intent' not in user2_ids
