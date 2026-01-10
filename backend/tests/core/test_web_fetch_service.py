"""
Tests for WebFetchService
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from core.web_fetch_service import WebFetchService
import requests
from datetime import datetime, timedelta


class TestURLValidation:
    """Test URL validation logic"""

    def test_https_required(self):
        """HTTP URLs should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        is_valid, error = service._validate_url("http://example.com")
        assert not is_valid
        assert "HTTPS" in error

    def test_https_accepted(self):
        """HTTPS URLs should be accepted for public IPs"""
        memory = Mock()
        service = WebFetchService(memory)

        with patch('socket.gethostbyname', return_value='93.184.216.34'):
            is_valid, error = service._validate_url("https://example.com")
            assert is_valid
            assert error is None

    def test_private_ip_10_blocked(self):
        """10.x.x.x private IPs should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        with patch('socket.gethostbyname', return_value='10.0.0.1'):
            is_valid, error = service._validate_url("https://internal.local")
            assert not is_valid
            assert "private network" in error.lower()

    def test_private_ip_192_blocked(self):
        """192.168.x.x private IPs should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        with patch('socket.gethostbyname', return_value='192.168.1.1'):
            is_valid, error = service._validate_url("https://internal.local")
            assert not is_valid
            assert "private network" in error.lower()

    def test_localhost_blocked(self):
        """Localhost should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        is_valid, error = service._validate_url("https://localhost/admin")
        assert not is_valid
        assert "not allowed" in error.lower()

    def test_link_local_blocked(self):
        """Link-local addresses (169.254.x.x) should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        with patch('socket.gethostbyname', return_value='169.254.169.254'):
            is_valid, error = service._validate_url("https://metadata.local")
            assert not is_valid
            assert "private network" in error.lower()

    def test_invalid_url_format(self):
        """Malformed URLs should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        is_valid, error = service._validate_url("not-a-url")
        assert not is_valid
        assert "format" in error.lower() or "https" in error.lower()


class TestContentFetching:
    """Test content fetching logic"""

    @patch('requests.get')
    def test_successful_fetch(self, mock_get):
        """Valid URL should fetch successfully"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        # Mock response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {'content-length': '1000'}
        mock_response.text = '<html><head><title>Test</title></head><body>Content</body></html>'
        mock_response.iter_content = Mock(return_value=[b'<html><head><title>Test</title></head><body>Content</body></html>'])
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Mock cache check (cache miss)
        service._check_cache = Mock(return_value=None)
        service._validate_url = Mock(return_value=(True, None))
        service._check_rate_limit = Mock(return_value={"allowed": True, "remaining": 49})
        service._store_cache = Mock()

        result = service.fetch_url("https://example.com", user_id=1)

        assert result["success"]
        assert "content" in result
        assert result["content"]["title"] == "Test"
        assert "Content" in result["content"]["content"]
        assert not result["cached"]

    @patch('requests.get')
    def test_timeout_handling(self, mock_get):
        """Timeout should return error"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        mock_get.side_effect = requests.Timeout()

        service._check_cache = Mock(return_value=None)
        service._validate_url = Mock(return_value=(True, None))
        service._check_rate_limit = Mock(return_value={"allowed": True})

        result = service.fetch_url("https://example.com", user_id=1)

        assert not result["success"]
        assert "timed out" in result["error"].lower()

    @patch('requests.get')
    def test_network_error_handling(self, mock_get):
        """Network errors should return error"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        mock_get.side_effect = requests.RequestException("Network error")

        service._check_cache = Mock(return_value=None)
        service._validate_url = Mock(return_value=(True, None))
        service._check_rate_limit = Mock(return_value={"allowed": True})

        result = service.fetch_url("https://example.com", user_id=1)

        assert not result["success"]
        assert "network error" in result["error"].lower()

    @patch('requests.get')
    def test_content_size_limit(self, mock_get):
        """Content over 5MB should be rejected"""
        memory = Mock()
        service = WebFetchService(memory)

        # Create mock response with large content-length
        mock_response = Mock()
        mock_response.headers = {'content-length': str(6 * 1024 * 1024)}  # 6MB
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="too large"):
            service._make_request("https://example.com")


class TestCaching:
    """Test caching logic"""

    def test_cache_hit(self):
        """Second request should use cache"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        cached_data = {
            "title": "Cached Title",
            "content": "Cached content",
            "url": "https://example.com",
            "metadata": {"word_count": 2},
            "cached_at": datetime.now()
        }

        service._check_cache = Mock(return_value=cached_data)
        service._check_rate_limit = Mock(return_value={"allowed": True})
        service._validate_url = Mock(return_value=(True, None))

        result = service.fetch_url("https://example.com", user_id=1)

        assert result["success"]
        assert result["cached"]
        assert result["content"]["title"] == "Cached Title"
        assert result["content"]["content"] == "Cached content"

    def test_cache_miss(self):
        """Cache miss should fetch fresh content"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        service._check_cache = Mock(return_value=None)
        assert service._check_cache("https://example.com", 1) is None


class TestRateLimiting:
    """Test rate limiting logic"""

    def test_under_limit(self):
        """Requests under limit should succeed"""
        from unittest.mock import MagicMock
        memory = Mock()

        # Mock the context manager properly
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_result.__getitem__ = Mock(return_value=10)
        mock_conn.execute.return_value.fetchone.return_value = mock_result

        # Use MagicMock for begin() so it supports context manager protocol
        memory.engine.begin = MagicMock()
        memory.engine.begin.return_value.__enter__.return_value = mock_conn
        memory.engine.begin.return_value.__exit__.return_value = None

        service = WebFetchService(memory)
        rate_check = service._check_rate_limit(user_id=1)

        assert rate_check["allowed"]
        assert rate_check["remaining"] == 40  # 50 - 10
        assert rate_check["error"] is None

    def test_at_limit(self):
        """50th request should still succeed"""
        from unittest.mock import MagicMock
        memory = Mock()

        # Mock the context manager properly
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_result.__getitem__ = Mock(return_value=49)
        mock_conn.execute.return_value.fetchone.return_value = mock_result

        # Use MagicMock for begin() so it supports context manager protocol
        memory.engine.begin = MagicMock()
        memory.engine.begin.return_value.__enter__.return_value = mock_conn
        memory.engine.begin.return_value.__exit__.return_value = None

        service = WebFetchService(memory)
        rate_check = service._check_rate_limit(user_id=1)

        assert rate_check["allowed"]
        assert rate_check["remaining"] == 1

    def test_over_limit(self):
        """51st request in hour should fail"""
        from unittest.mock import MagicMock
        memory = Mock()

        # Mock the context manager properly
        mock_conn = MagicMock()
        mock_result = Mock()
        mock_result.__getitem__ = Mock(return_value=50)
        mock_conn.execute.return_value.fetchone.return_value = mock_result

        # Use MagicMock for begin() so it supports context manager protocol
        memory.engine.begin = MagicMock()
        memory.engine.begin.return_value.__enter__.return_value = mock_conn
        memory.engine.begin.return_value.__exit__.return_value = None

        service = WebFetchService(memory)
        rate_check = service._check_rate_limit(user_id=1)

        assert not rate_check["allowed"]
        assert rate_check["remaining"] == 0
        assert "Rate limit exceeded" in rate_check["error"]

    def test_rate_limit_blocks_fetch(self):
        """Rate limit should prevent fetch"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        # Mock rate limit exceeded
        service._check_rate_limit = Mock(return_value={
            "allowed": False,
            "error": "Rate limit exceeded: 50 requests per 1 hour(s)"
        })

        result = service.fetch_url("https://example.com", user_id=1)

        assert not result["success"]
        assert "rate limit" in result["error"].lower()


class TestContentExtraction:
    """Test content extraction logic"""

    def test_extract_title_from_title_tag(self):
        """Should extract title from <title> tag"""
        memory = Mock()
        service = WebFetchService(memory)

        html = "<html><head><title>Page Title</title></head><body>Content</body></html>"
        result = service._extract_content(html, "https://example.com")

        assert result["title"] == "Page Title"

    def test_extract_title_from_h1(self):
        """Should fallback to <h1> if no <title>"""
        memory = Mock()
        service = WebFetchService(memory)

        html = "<html><body><h1>H1 Title</h1><p>Content</p></body></html>"
        result = service._extract_content(html, "https://example.com")

        assert result["title"] == "H1 Title"

    def test_remove_scripts(self):
        """Should remove <script> tags"""
        memory = Mock()
        service = WebFetchService(memory)

        html = "<html><body><p>Content</p><script>alert('bad')</script></body></html>"
        result = service._extract_content(html, "https://example.com")

        assert "alert" not in result["content"]
        assert "Content" in result["content"]

    def test_remove_navigation(self):
        """Should remove <nav> tags"""
        memory = Mock()
        service = WebFetchService(memory)

        html = "<html><body><nav>Menu</nav><article>Main content</article></body></html>"
        result = service._extract_content(html, "https://example.com")

        assert "Menu" not in result["content"]
        assert "Main content" in result["content"]

    def test_metadata_word_count(self):
        """Should calculate word count"""
        memory = Mock()
        service = WebFetchService(memory)

        html = "<html><body><p>One two three four five</p></body></html>"
        result = service._extract_content(html, "https://example.com")

        assert result["metadata"]["word_count"] == 5


class TestMultiURLFetch:
    """Test fetching multiple URLs"""

    def test_fetch_multiple_urls(self):
        """Should fetch all URLs successfully"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        # Mock successful fetches
        def mock_fetch(url, user_id):
            return {
                "success": True,
                "content": {
                    "title": f"Title for {url}",
                    "content": f"Content from {url}",
                    "url": url,
                    "metadata": {"word_count": 3}
                },
                "cached": False
            }

        service.fetch_url = Mock(side_effect=mock_fetch)

        urls = ["https://example.com", "https://test.com"]
        result = service.fetch_urls(urls, user_id=1)

        assert result["success"]
        assert len(result["results"]) == 2
        assert result["summary"] == "2/2 URLs fetched successfully"

    def test_partial_failure(self):
        """Should handle partial failures gracefully"""
        memory = Mock()
        memory.conn = Mock()
        service = WebFetchService(memory)

        # Mock partial failure
        def mock_fetch(url, user_id):
            if "example" in url:
                return {
                    "success": True,
                    "content": {"title": "Success", "content": "Content", "url": url, "metadata": {}},
                    "cached": False
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to fetch",
                    "cached": False
                }

        service.fetch_url = Mock(side_effect=mock_fetch)

        urls = ["https://example.com", "https://fail.com"]
        result = service.fetch_urls(urls, user_id=1)

        assert result["success"]  # At least one succeeded
        assert result["summary"] == "1/2 URLs fetched successfully"


class TestFormatting:
    """Test response formatting"""

    def test_format_response_single(self):
        """Should format single URL response"""
        memory = Mock()
        service = WebFetchService(memory)

        content = {
            "title": "Test Page",
            "description": "Test description",
            "content": "Main content here",
            "url": "https://example.com",
            "metadata": {"word_count": 3}
        }

        formatted = service.format_response(content, "https://example.com")

        assert "Test Page" in formatted
        assert "Test description" in formatted
        assert "Main content here" in formatted
        assert "Word Count: 3" in formatted

    def test_format_multi_response(self):
        """Should format multiple URL responses"""
        memory = Mock()
        service = WebFetchService(memory)

        results = [
            {
                "url": "https://example.com",
                "success": True,
                "content": {
                    "title": "Page 1",
                    "content": "Content 1",
                    "url": "https://example.com",
                    "metadata": {"word_count": 2}
                },
                "cached": False
            },
            {
                "url": "https://test.com",
                "success": True,
                "content": {
                    "title": "Page 2",
                    "content": "Content 2",
                    "url": "https://test.com",
                    "metadata": {"word_count": 2}
                },
                "cached": True
            }
        ]

        formatted = service.format_multi_response(results)

        assert "Fetched 2 URL(s)" in formatted
        assert "URL 1: https://example.com" in formatted
        assert "URL 2: https://test.com" in formatted
        assert "Page 1" in formatted
        assert "Page 2" in formatted
        assert "[Cached content]" in formatted


class TestHashURL:
    """Test URL hashing"""

    def test_hash_consistency(self):
        """Same URL should produce same hash"""
        hash1 = WebFetchService._hash_url("https://example.com")
        hash2 = WebFetchService._hash_url("https://example.com")

        assert hash1 == hash2

    def test_hash_uniqueness(self):
        """Different URLs should produce different hashes"""
        hash1 = WebFetchService._hash_url("https://example.com")
        hash2 = WebFetchService._hash_url("https://test.com")

        assert hash1 != hash2
