"""
Shared test fixtures for route tests.

Provides Flask app, test client, database, and authentication fixtures.
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from app import app as flask_app
from core.memory import MemoryStore
from auth import hash_password, generate_session_token


@pytest.fixture
def app():
    """
    Create and configure Flask app for testing.
    """
    # Use in-memory SQLite database for tests
    db_fd, db_path = tempfile.mkstemp()

    flask_app.config.update({
        "TESTING": True,
        "DATABASE_URL": f"sqlite:///{db_path}",
        "SECRET_KEY": "test-secret-key",
    })

    yield flask_app

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """
    Create Flask test client.
    """
    return app.test_client()


@pytest.fixture
def memory():
    """
    Create MemoryStore with in-memory database.
    """
    db_fd, db_path = tempfile.mkstemp()
    memory_store = MemoryStore(f"sqlite:///{db_path}")

    yield memory_store

    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def test_user(memory):
    """
    Create a test user.
    """
    password_hash = hash_password("testpass123")
    memory.create_user("testuser", password_hash, is_admin=False)
    user = memory.get_user_by_username("testuser")

    return {
        "id": user["id"],
        "username": user["username"],
        "password": "testpass123",
        "is_admin": user["is_admin"]
    }


@pytest.fixture
def admin_user(memory):
    """
    Create a test admin user.
    """
    password_hash = hash_password("adminpass123")
    memory.create_user("adminuser", password_hash, is_admin=True)
    user = memory.get_user_by_username("adminuser")

    return {
        "id": user["id"],
        "username": user["username"],
        "password": "adminpass123",
        "is_admin": user["is_admin"]
    }


@pytest.fixture
def auth_token(memory, test_user):
    """
    Create authentication token for test user.
    """
    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(days=7)
    memory.create_auth_session(token, test_user["id"], expires_at)

    return token


@pytest.fixture
def auth_headers(auth_token):
    """
    Create authorization headers with bearer token.
    """
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def login_helper(client, memory):
    """
    Helper function to login and get auth token.
    """
    def login(username="testuser", password="testpass123"):
        response = client.post("/api/auth/login", json={
            "username": username,
            "password": password
        })
        if response.status_code == 200:
            return response.json["token"]
        return None

    return login


@pytest.fixture
def mock_openai():
    """
    Mock OpenAI API calls.
    """
    with patch("openai.ChatCompletion.create") as mock:
        mock.return_value = {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-4",
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a mocked response"
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        yield mock


@pytest.fixture
def mock_anthropic():
    """
    Mock Anthropic API calls.
    """
    with patch("anthropic.Anthropic") as mock:
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="This is a mocked response")]
        mock_response.usage = MagicMock(
            input_tokens=10,
            output_tokens=20
        )
        mock_client.messages.create.return_value = mock_response
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def mock_m365():
    """
    Mock M365 Graph API calls.
    """
    with patch("requests.get") as mock_get, \
         patch("requests.post") as mock_post:

        # Mock successful calendar query
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "value": [
                    {
                        "id": "event123",
                        "subject": "Test Meeting",
                        "start": {"dateTime": "2025-01-15T10:00:00"},
                        "end": {"dateTime": "2025-01-15T11:00:00"}
                    }
                ]
            }
        )

        # Mock successful event creation
        mock_post.return_value = MagicMock(
            status_code=201,
            json=lambda: {
                "id": "event456",
                "subject": "New Event"
            }
        )

        yield {"get": mock_get, "post": mock_post}


@pytest.fixture
def mock_llm_provider():
    """
    Mock generic LLM provider for route_request.
    """
    with patch("core.router.route_request") as mock:
        mock.return_value = {
            "text": "Mocked LLM response",
            "provider": "mock-provider",
            "model": "mock-model",
            "task_type": "general"
        }
        yield mock


@pytest.fixture
def sample_session(memory):
    """
    Create a sample session with messages.
    """
    session_id = "test-session-123"

    # Save some conversation turns
    memory.save_turn(session_id, "user", "Hello, how are you?")
    memory.save_turn(session_id, "assistant", "I'm doing well, thank you!")
    memory.save_turn(session_id, "user", "What's the weather like?")
    memory.save_turn(session_id, "assistant", "I don't have access to weather data.")

    # Set a title
    memory.save_session_title(session_id, "Test Conversation")

    return session_id


@pytest.fixture
def sample_memories(memory):
    """
    Create sample memories for testing.
    """
    memories = []

    # Create various types of memories
    memory.store_memory("local", "fact", "favorite_color", "blue", pinned=True)
    memory.store_memory("local", "preference", "theme", "dark mode")
    memory.store_memory("local", "goal", "learning", "Learn Python testing")

    memories = memory.get_memories("local")
    return memories


@pytest.fixture
def sample_provider(memory):
    """
    Create a sample AI provider.
    """
    provider = {
        "id": "test-provider",
        "name": "Test Provider",
        "type": "openai",
        "model": "gpt-4",
        "api_key": "sk-test-key",
        "enabled": True
    }

    memory.upsert_provider(provider)
    memory.init_provider_metadata(provider["id"])

    return provider


@pytest.fixture
def sample_intent(memory):
    """
    Create a sample intent.
    """
    memory.create_intent(
        user_id="local",
        intent_id="coding",
        name="Coding Assistant",
        description="Help with code",
        keywords="code,programming,function,class",
        priority=10,
        enabled=True
    )

    return memory.get_intent("local", "coding")
