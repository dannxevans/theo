"""
Tests for Perplexity AI provider.

Tests provider instantiation, chat, streaming, search mode, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from providers.perplexity import PerplexityProvider


class TestPerplexityProviderInstantiation:
    """Test Perplexity provider initialization."""

    def test_init_with_valid_api_key(self):
        """Test successful initialization with API key."""
        provider = PerplexityProvider(api_key="pplx-test-key")
        assert provider.api_key == "pplx-test-key"
        assert provider.base_url == "https://api.perplexity.ai"
        assert provider.model == "llama-3.1-sonar-small-128k-online"
        assert provider.search_mode is True

    def test_init_with_custom_base_url(self):
        """Test initialization with custom base URL."""
        provider = PerplexityProvider(
            api_key="pplx-test-key",
            base_url="https://custom.api.com"
        )
        assert provider.base_url == "https://custom.api.com"

    def test_init_with_custom_model(self):
        """Test initialization with custom model."""
        provider = PerplexityProvider(
            api_key="pplx-test-key",
            model="llama-3.1-sonar-large-128k-online"
        )
        assert provider.model == "llama-3.1-sonar-large-128k-online"

    def test_init_with_search_mode_disabled(self):
        """Test initialization with search mode disabled."""
        provider = PerplexityProvider(
            api_key="pplx-test-key",
            search_mode=False
        )
        assert provider.search_mode is False

    def test_init_without_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(ValueError, match="requires an api_key"):
            PerplexityProvider(api_key=None)

    def test_init_with_empty_api_key(self):
        """Test initialization fails with empty API key."""
        with pytest.raises(ValueError, match="requires an api_key"):
            PerplexityProvider(api_key="")


class TestPerplexityChatMethod:
    """Test Perplexity chat completion."""

    @patch('providers.perplexity.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "content": "The capital of France is Paris."
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 15
            },
            "citations": [
                "https://en.wikipedia.org/wiki/Paris"
            ]
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        result = provider.chat(
            system="You are a helpful assistant",
            messages=[{"role": "user", "content": "What is the capital of France?"}]
        )

        assert result == "The capital of France is Paris."
        assert provider._last_usage["input_tokens"] == 10
        assert provider._last_usage["output_tokens"] == 15
        assert provider._last_usage["citations"] == ["https://en.wikipedia.org/wiki/Paris"]
        assert provider._last_usage["web_grounded"] is True

    @patch('providers.perplexity.requests.post')
    def test_chat_with_system_prompt_injection(self, mock_post):
        """Test system prompt behavior differs between search and non-search mode."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        # Test search mode (default): system prompt should NOT be injected
        provider = PerplexityProvider(api_key="pplx-test-key", search_mode=True)
        provider.chat(
            system="Important context",
            messages=[
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "Reply"},
                {"role": "user", "content": "Second message"}
            ]
        )

        # Verify system prompt was NOT injected in search mode
        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        assert len(payload["messages"]) == 3
        assert payload["messages"][0]["content"] == "First message"
        assert payload["messages"][1]["content"] == "Reply"
        # In search mode, query should be clean without system context
        assert payload["messages"][2]["content"] == "Second message"
        assert "IMPORTANT PERSISTENT CONTEXT" not in payload["messages"][2]["content"]

        # Test non-search mode: system prompt SHOULD be injected
        provider_non_search = PerplexityProvider(api_key="pplx-test-key", search_mode=False)
        provider_non_search.chat(
            system="Important context",
            messages=[
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "Reply"},
                {"role": "user", "content": "Second message"}
            ]
        )

        # Verify system prompt WAS injected in non-search mode
        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        assert len(payload["messages"]) == 3
        assert "Context:" in payload["messages"][2]["content"]
        assert "Important context" in payload["messages"][2]["content"]
        assert "Second message" in payload["messages"][2]["content"]

    @patch('providers.perplexity.requests.post')
    def test_chat_with_temperature(self, mock_post):
        """Test chat with custom temperature."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(
            messages=[{"role": "user", "content": "Test"}],
            temperature=0.8
        )

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["temperature"] == 0.8

    @patch('providers.perplexity.requests.post')
    def test_chat_with_search_domain_filter(self, mock_post):
        """Test chat with domain filtering."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(
            messages=[{"role": "user", "content": "Test"}],
            search_domain_filter=["wikipedia.org", "britannica.com"]
        )

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["search_domain_filter"] == ["wikipedia.org", "britannica.com"]

    @patch('providers.perplexity.requests.post')
    def test_chat_api_error(self, mock_post):
        """Test chat with API error response."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request: Invalid model"
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")

        with pytest.raises(RuntimeError, match="Perplexity API error 400"):
            provider.chat(messages=[{"role": "user", "content": "Test"}])

    @patch('providers.perplexity.requests.post')
    def test_chat_timeout(self, mock_post):
        """Test chat with request timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        provider = PerplexityProvider(api_key="pplx-test-key")

        with pytest.raises(RuntimeError, match="timed out"):
            provider.chat(messages=[{"role": "user", "content": "Test"}])

    @patch('providers.perplexity.requests.post')
    def test_chat_network_error(self, mock_post):
        """Test chat with network error."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        provider = PerplexityProvider(api_key="pplx-test-key")

        with pytest.raises(RuntimeError, match="request failed"):
            provider.chat(messages=[{"role": "user", "content": "Test"}])

    @patch('providers.perplexity.requests.post')
    def test_chat_unexpected_response_format(self, mock_post):
        """Test chat with unexpected API response format."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "invalid": "response"
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")

        with pytest.raises(RuntimeError, match="Unexpected Perplexity response"):
            provider.chat(messages=[{"role": "user", "content": "Test"}])

    @patch('providers.perplexity.requests.post')
    def test_chat_with_search_mode_disabled(self, mock_post):
        """Test chat without search mode."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key", search_mode=False)
        provider.chat(messages=[{"role": "user", "content": "Test"}])

        call_args = mock_post.call_args
        payload = call_args[1]["json"]

        # When search_mode is False, return_citations should not be set
        assert "return_citations" not in payload or payload.get("return_citations") is False


class TestPerplexityStreamChat:
    """Test Perplexity streaming chat."""

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_success(self, mock_post):
        """Test successful streaming chat."""
        # Mock streaming response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            b'data: {"choices": [{"delta": {"content": " world"}}]}',
            b'data: {"choices": [{"delta": {"content": "!"}}]}',
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        chunks = list(provider.stream_chat(
            messages=[{"role": "user", "content": "Test"}]
        ))

        assert chunks == ["Hello", " world", "!"]

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_with_empty_chunks(self, mock_post):
        """Test streaming chat handles empty content chunks."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {}}]}',  # Empty delta
            b'data: {"choices": [{"delta": {"content": "Text"}}]}',
            b'',  # Empty line
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        chunks = list(provider.stream_chat(
            messages=[{"role": "user", "content": "Test"}]
        ))

        assert chunks == ["Text"]

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_api_error(self, mock_post):
        """Test streaming chat with API error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")

        with pytest.raises(RuntimeError, match="Perplexity API error 401"):
            list(provider.stream_chat(messages=[{"role": "user", "content": "Test"}]))

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_timeout(self, mock_post):
        """Test streaming chat with timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()

        provider = PerplexityProvider(api_key="pplx-test-key")

        with pytest.raises(RuntimeError, match="streaming request timed out"):
            list(provider.stream_chat(messages=[{"role": "user", "content": "Test"}]))

    @patch('providers.perplexity.requests.post')
    def test_stream_chat_payload_configuration(self, mock_post):
        """Test streaming chat payload includes stream=True."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [b'data: [DONE]']
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        list(provider.stream_chat(messages=[{"role": "user", "content": "Test"}]))

        call_args = mock_post.call_args
        payload = call_args[1]["json"]
        assert payload["stream"] is True


class TestPerplexitySearchCapabilities:
    """Test Perplexity search-specific features."""

    @patch('providers.perplexity.requests.post')
    def test_citations_extracted_correctly(self, mock_post):
        """Test citations are extracted from response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Paris is the capital."}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            "citations": [
                "https://source1.com",
                "https://source2.com",
                "https://source3.com"
            ]
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(messages=[{"role": "user", "content": "Capital of France?"}])

        assert len(provider._last_usage["citations"]) == 3
        assert "https://source1.com" in provider._last_usage["citations"]

    @patch('providers.perplexity.requests.post')
    def test_no_citations_in_response(self, mock_post):
        """Test handling when no citations in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(messages=[{"role": "user", "content": "Test"}])

        assert provider._last_usage["citations"] == []

    @patch('providers.perplexity.requests.post')
    def test_web_grounded_flag(self, mock_post):
        """Test web_grounded flag reflects search_mode."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        # Test with search mode enabled
        provider_search = PerplexityProvider(api_key="pplx-test-key", search_mode=True)
        provider_search.chat(messages=[{"role": "user", "content": "Test"}])
        assert provider_search._last_usage["web_grounded"] is True

        # Test with search mode disabled
        provider_no_search = PerplexityProvider(api_key="pplx-test-key", search_mode=False)
        provider_no_search.chat(messages=[{"role": "user", "content": "Test"}])
        assert provider_no_search._last_usage["web_grounded"] is False


class TestPerplexityTokenTracking:
    """Test token usage tracking."""

    @patch('providers.perplexity.requests.post')
    def test_token_usage_tracking(self, mock_post):
        """Test input and output tokens are tracked correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {
                "prompt_tokens": 123,
                "completion_tokens": 456
            },
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(messages=[{"role": "user", "content": "Test"}])

        assert provider._last_usage["input_tokens"] == 123
        assert provider._last_usage["output_tokens"] == 456

    @patch('providers.perplexity.requests.post')
    def test_zero_token_usage(self, mock_post):
        """Test handling of zero token usage."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0
            },
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(messages=[{"role": "user", "content": ""}])

        assert provider._last_usage["input_tokens"] == 0
        assert provider._last_usage["output_tokens"] == 0

    @patch('providers.perplexity.requests.post')
    def test_missing_usage_data(self, mock_post):
        """Test handling when usage data is missing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(messages=[{"role": "user", "content": "Test"}])

        assert provider._last_usage["input_tokens"] == 0
        assert provider._last_usage["output_tokens"] == 0


class TestPerplexityHeadersAndAuth:
    """Test API headers and authentication."""

    @patch('providers.perplexity.requests.post')
    def test_authorization_header(self, mock_post):
        """Test Authorization header is set correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-my-secret-key")
        provider.chat(messages=[{"role": "user", "content": "Test"}])

        call_args = mock_post.call_args
        headers = call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer pplx-my-secret-key"
        assert headers["Content-Type"] == "application/json"

    @patch('providers.perplexity.requests.post')
    def test_api_endpoint_url(self, mock_post):
        """Test correct API endpoint URL is used."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5},
            "citations": []
        }
        mock_post.return_value = mock_response

        provider = PerplexityProvider(api_key="pplx-test-key")
        provider.chat(messages=[{"role": "user", "content": "Test"}])

        call_args = mock_post.call_args
        url = call_args[0][0]
        assert url == "https://api.perplexity.ai/chat/completions"
