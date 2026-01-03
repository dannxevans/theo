"""
Tests for voice API routes.
"""

import pytest
import io
from unittest.mock import Mock, patch, MagicMock
from flask import Flask
from routes.voice_routes import voice_bp


@pytest.fixture
def app():
    """Create Flask app for testing."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.register_blueprint(voice_bp, url_prefix='/api/voice')
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    from core.memory import MemoryStore
    from config import Config
    from auth.password import hash_password
    memory = MemoryStore(Config.DATABASE_URL)

    password_hash = hash_password("test_password")
    import uuid
    username = f"testuser_{uuid.uuid4().hex[:8]}"
    memory.create_user(username, password_hash, is_admin=False)
    user = memory.get_user_by_username(username)

    return {
        "id": user["id"],
        "username": user["username"],
        "is_admin": user["is_admin"]
    }


@pytest.fixture
def auth_token(app, test_user):
    """Create an authentication token for the test user."""
    from core.memory import MemoryStore
    from config import Config
    from datetime import datetime, timedelta
    from auth.password import generate_session_token

    memory = MemoryStore(Config.DATABASE_URL)

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=1)
    memory.create_auth_session(token, test_user["id"], expires_at)
    return token


@pytest.fixture
def auth_headers(auth_token):
    """Create authorization headers with bearer token."""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture
def mock_tts_provider():
    """Mock TTS provider."""
    with patch('routes.voice_routes.get_tts_provider') as mock:
        provider = Mock()
        provider.synthesize.return_value = b"audio_data"
        provider.model = "test-tts-model"
        provider.list_voices.return_value = [
            {"id": "alloy", "name": "Alloy", "description": "Neutral voice"},
            {"id": "echo", "name": "Echo", "description": "Clear voice"}
        ]
        mock.return_value = (provider, None)
        yield mock


@pytest.fixture
def mock_stt_provider():
    """Mock STT provider."""
    with patch('routes.voice_routes.get_stt_provider') as mock:
        provider = Mock()
        provider.transcribe.return_value = {
            "text": "Hello, this is a test",
            "language": "en"
        }
        mock.return_value = (provider, None)
        yield mock


class TestVoiceRoutes:
    """Test suite for voice API routes."""

    def test_tts_endpoint_success(self, client, mock_tts_provider, auth_headers):
        """Test TTS endpoint with valid request."""
        response = client.post('/api/voice/tts', headers=auth_headers, json={
            'text': 'Hello world',
            'voice': 'alloy',
            'speed': 1.0
        })

        assert response.status_code == 200
        assert response.data == b"audio_data"
        assert response.content_type == "audio/mpeg"

        # Verify provider was called correctly
        provider = mock_tts_provider.return_value[0]
        provider.synthesize.assert_called_once_with(
            text='Hello world',
            voice='alloy',
            speed=1.0,
            output_format='mp3'
        )

    def test_tts_endpoint_missing_text(self, client, mock_tts_provider, auth_headers):
        """Test TTS endpoint without text."""
        response = client.post('/api/voice/tts', headers=auth_headers, json={})

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_tts_endpoint_provider_not_configured(self, client, auth_headers):
        """Test TTS endpoint when provider is not configured."""
        with patch('routes.voice_routes.get_tts_provider') as mock:
            mock.return_value = (None, "Provider not configured")

            response = client.post('/api/voice/tts', headers=auth_headers, json={'text': 'test'})

            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data

    def test_tts_endpoint_synthesis_error(self, client, mock_tts_provider, auth_headers):
        """Test TTS endpoint with synthesis error."""
        provider = mock_tts_provider.return_value[0]
        provider.synthesize.side_effect = Exception("Synthesis failed")

        response = client.post('/api/voice/tts', headers=auth_headers, json={'text': 'test'})

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    def test_tts_endpoint_default_parameters(self, client, mock_tts_provider, auth_headers):
        """Test TTS endpoint with default parameters."""
        response = client.post('/api/voice/tts', headers=auth_headers, json={'text': 'test'})

        assert response.status_code == 200

        provider = mock_tts_provider.return_value[0]
        call_kwargs = provider.synthesize.call_args.kwargs
        assert call_kwargs.get('voice') == 'alloy'
        assert call_kwargs.get('speed') == 1.0

    def test_stt_endpoint_success(self, client, mock_stt_provider, auth_headers):
        """Test STT endpoint with valid audio file."""
        # Create a mock audio file
        audio_data = b"fake_audio_data"
        data = {
            'audio': (io.BytesIO(audio_data), 'recording.webm'),
            'format': 'webm'
        }

        response = client.post(
            '/api/voice/stt',
            data=data,
            content_type='multipart/form-data',
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data['text'] == "Hello, this is a test"
        assert data['language'] == "en"

        # Verify provider was called
        provider = mock_stt_provider.return_value[0]
        provider.transcribe.assert_called_once()

    def test_stt_endpoint_missing_audio(self, client, mock_stt_provider, auth_headers):
        """Test STT endpoint without audio file."""
        response = client.post('/api/voice/stt', data={}, headers=auth_headers)

        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data

    def test_stt_endpoint_with_language(self, client, mock_stt_provider, auth_headers):
        """Test STT endpoint with specified language."""
        audio_data = b"fake_audio_data"
        data = {
            'audio': (io.BytesIO(audio_data), 'recording.webm'),
            'format': 'webm',
            'language': 'es'
        }

        response = client.post(
            '/api/voice/stt',
            data=data,
            content_type='multipart/form-data',
            headers=auth_headers
        )

        assert response.status_code == 200

        provider = mock_stt_provider.return_value[0]
        call_kwargs = provider.transcribe.call_args.kwargs
        assert call_kwargs.get('language') == 'es'

    def test_stt_endpoint_provider_not_configured(self, client, auth_headers):
        """Test STT endpoint when provider is not configured."""
        with patch('routes.voice_routes.get_stt_provider') as mock:
            mock.return_value = (None, "Provider not configured")

            audio_data = b"fake_audio_data"
            data = {
                'audio': (io.BytesIO(audio_data), 'recording.webm'),
                'format': 'webm'
            }

            response = client.post(
                '/api/voice/stt',
                data=data,
                content_type='multipart/form-data',
            headers=auth_headers
            )

            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data

    def test_stt_endpoint_transcription_error(self, client, mock_stt_provider, auth_headers):
        """Test STT endpoint with transcription error."""
        provider = mock_stt_provider.return_value[0]
        provider.transcribe.side_effect = Exception("Transcription failed")

        audio_data = b"fake_audio_data"
        data = {
            'audio': (io.BytesIO(audio_data), 'recording.webm'),
            'format': 'webm'
        }

        response = client.post(
            '/api/voice/stt',
            data=data,
            content_type='multipart/form-data',
            headers=auth_headers
        )

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data

    def test_voices_endpoint_success(self, client, mock_tts_provider, auth_headers):
        """Test voices endpoint."""
        response = client.get('/api/voice/voices', headers=auth_headers)

        assert response.status_code == 200
        data = response.get_json()
        assert 'voices' in data
        assert len(data['voices']) == 2
        assert data['voices'][0]['id'] == 'alloy'
        assert data['voices'][1]['id'] == 'echo'

    def test_voices_endpoint_provider_not_configured(self, client, auth_headers):
        """Test voices endpoint when provider is not configured."""
        with patch('routes.voice_routes.get_tts_provider') as mock:
            mock.return_value = (None, "Provider not configured")

            response = client.get('/api/voice/voices', headers=auth_headers)

            assert response.status_code == 500
            data = response.get_json()
            assert 'error' in data

    def test_voices_endpoint_error(self, client, mock_tts_provider, auth_headers):
        """Test voices endpoint with error."""
        provider = mock_tts_provider.return_value[0]
        provider.list_voices.side_effect = Exception("Failed to list voices")

        response = client.get('/api/voice/voices', headers=auth_headers)

        assert response.status_code == 500
        data = response.get_json()
        assert 'error' in data


class TestProviderHelpers:
    """Test provider initialization helpers."""

    @patch('routes.voice_routes.OpenAITTSProvider')
    @patch('app.provider_registry')
    def test_get_tts_provider_success(self, mock_registry, mock_provider_class, auth_headers):
        """Test successful TTS provider initialization."""
        from routes.voice_routes import get_tts_provider

        # Mock registry response
        mock_registry.get_by_type.return_value = {
            'api_key': 'test-key'
        }

        # Mock provider initialization
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        provider, error = get_tts_provider()

        assert provider is not None
        assert error is None
        mock_provider_class.assert_called_once_with(
            api_key='test-key',
            model='tts-1'
        )

    @patch('app.provider_registry')
    def test_get_tts_provider_no_api_key(self, mock_registry, auth_headers):
        """Test TTS provider when API key is not configured."""
        from routes.voice_routes import get_tts_provider

        mock_registry.get_by_type.return_value = None

        provider, error = get_tts_provider()

        assert provider is None
        assert error == "OpenAI API key not configured"

    @patch('routes.voice_routes.OpenAIWhisperProvider')
    @patch('app.provider_registry')
    def test_get_stt_provider_success(self, mock_registry, mock_provider_class, auth_headers):
        """Test successful STT provider initialization."""
        from routes.voice_routes import get_stt_provider

        mock_registry.get_by_type.return_value = {
            'api_key': 'test-key'
        }

        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider

        provider, error = get_stt_provider()

        assert provider is not None
        assert error is None
        mock_provider_class.assert_called_once_with(
            api_key='test-key'
        )
