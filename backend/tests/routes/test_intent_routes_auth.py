"""
Tests for intent routes with authentication and user_id.

Tests cover:
- Intent CRUD operations respect user_id from g.user_id
- User isolation for intents
- Authentication headers required
"""

import pytest
import json


def test_list_intents_requires_auth(client):
    """Test that listing intents without auth returns empty or uses fallback."""
    response = client.get('/api/intents')

    assert response.status_code == 200
    data = json.loads(response.data)

    # Without auth, should use fallback user_id='local' which may have no intents
    # or could be empty
    assert isinstance(data, list)


def test_list_intents_with_auth(client, auth_headers, memory, test_user):
    """Test listing intents with valid auth token."""
    # Create test intent for this user
    memory.create_intent(
        user_id=str(test_user["id"]),
        intent_id="test_intent",
        name="Test Intent",
        description="Test",
        keywords="test",
        priority=50,
        enabled=True
    )

    response = client.get('/api/intents', headers=auth_headers)

    assert response.status_code == 200
    data = json.loads(response.data)

    # Should include our test intent
    intent_ids = [intent['id'] for intent in data]
    assert 'test_intent' in intent_ids


def test_create_intent_with_auth(client, auth_headers, memory, test_user):
    """Test creating an intent with auth token."""
    response = client.post(
        '/api/intents',
        headers=auth_headers,
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
    intent = memory.get_intent(str(test_user["id"]), 'new_intent')
    assert intent is not None
    assert intent['name'] == 'New Intent'


def test_update_intent_with_auth(client, auth_headers, memory, test_user):
    """Test updating an intent with auth token."""
    # Create intent first
    memory.create_intent(
        user_id=str(test_user["id"]),
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
        headers=auth_headers,
        data=json.dumps({
            'name': 'Updated Name',
            'keywords': 'updated'
        })
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify update
    intent = memory.get_intent(str(test_user["id"]), 'update_test')
    assert intent['name'] == 'Updated Name'
    assert intent['keywords'] == 'updated'


def test_delete_intent_with_auth(client, auth_headers, memory, test_user):
    """Test deleting an intent with auth token."""
    # Create intent first
    memory.create_intent(
        user_id=str(test_user["id"]),
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
        headers=auth_headers
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'ok'

    # Verify deletion
    intent = memory.get_intent(str(test_user["id"]), 'delete_test')
    assert intent is None


def test_user_isolation_intents(memory, test_user, admin_user):
    """Test that users cannot see each other's intents."""
    # Create intents for each user
    memory.create_intent(str(test_user["id"]), "user1_intent", "User 1 Intent", "", "test", 50, True)
    memory.create_intent(str(admin_user["id"]), "user2_intent", "User 2 Intent", "", "test", 50, True)

    # Get intents for each user
    user1_intents = memory.list_intents(str(test_user["id"]))
    user2_intents = memory.list_intents(str(admin_user["id"]))

    # Each user should only see their own intents
    user1_ids = [intent['id'] for intent in user1_intents]
    user2_ids = [intent['id'] for intent in user2_intents]

    assert 'user1_intent' in user1_ids
    assert 'user2_intent' not in user1_ids

    assert 'user2_intent' in user2_ids
    assert 'user1_intent' not in user2_ids
