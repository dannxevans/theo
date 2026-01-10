"""
Web Fetch Service for THEO
Handles fetching and processing web content with security controls
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import ipaddress
import hashlib
import socket
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Optional, Tuple, Dict, Any, List

logger = logging.getLogger(__name__)

# Security Configuration
REQUEST_TIMEOUT = 10  # seconds
MAX_CONTENT_SIZE = 5 * 1024 * 1024  # 5MB
USER_AGENT = 'THEO-Assistant/1.0 (Web Fetch; +https://prod.duckyfuzz.uk)'
CACHE_TTL_SECONDS = 3600  # 1 hour
RATE_LIMIT_WINDOW_HOURS = 1
RATE_LIMIT_MAX_REQUESTS = 50

# Blocked IP ranges (private networks)
BLOCKED_IP_RANGES = [
    ipaddress.IPv4Network('10.0.0.0/8'),
    ipaddress.IPv4Network('172.16.0.0/12'),
    ipaddress.IPv4Network('192.168.0.0/16'),
    ipaddress.IPv4Network('127.0.0.0/8'),
    ipaddress.IPv4Network('169.254.0.0/16'),  # Link-local + Cloud metadata
]

BLOCKED_DOMAINS = ['localhost', '0.0.0.0']


class WebFetchService:
    """Service for fetching and processing web content"""

    def __init__(self, memory):
        """
        Initialize web fetch service

        Args:
            memory: MemoryStore instance for database access
        """
        self.memory = memory
        self.engine = memory.engine
        self.web_fetch_cache = memory.tables.get("web_fetch_cache")

    def fetch_urls(self, urls: List[str], user_id: int) -> Dict[str, Any]:
        """
        Fetch and process content from multiple URLs

        Args:
            urls: List of HTTPS URLs to fetch
            user_id: User requesting the fetch

        Returns:
            Dict with keys:
                - success: bool indicating if at least one fetch succeeded
                - results: list of dicts for each URL with content/error
                - summary: overall summary of results
        """
        results = []
        success_count = 0

        for url in urls:
            result = self.fetch_url(url, user_id)
            results.append({
                'url': url,
                'success': result['success'],
                'content': result.get('content'),
                'error': result.get('error'),
                'cached': result.get('cached', False)
            })
            if result['success']:
                success_count += 1

        return {
            'success': success_count > 0,
            'results': results,
            'summary': f"{success_count}/{len(urls)} URLs fetched successfully"
        }

    def fetch_url(self, url: str, user_id: int) -> Dict[str, Any]:
        """
        Fetch and process content from a URL

        Args:
            url: The HTTPS URL to fetch
            user_id: User requesting the fetch

        Returns:
            Dict with keys:
                - success: bool indicating if fetch succeeded
                - content: dict with extracted content (if successful)
                - error: error message (if failed)
                - cached: bool indicating if result was from cache
        """
        try:
            # Check rate limit
            rate_limit_check = self._check_rate_limit(user_id)
            if not rate_limit_check["allowed"]:
                return {
                    "success": False,
                    "error": rate_limit_check["error"],
                    "cached": False
                }

            # Validate URL
            is_valid, error_msg = self._validate_url(url)
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "cached": False
                }

            # Check cache
            cached_content = self._check_cache(url, user_id)
            if cached_content:
                logger.info(f"Cache hit for URL: {url}")
                return {
                    "success": True,
                    "content": cached_content,
                    "cached": True
                }

            # Fetch content
            logger.info(f"Fetching URL: {url}")
            response = self._make_request(url)

            # Extract content
            extracted = self._extract_content(response.text, url)

            # Store in cache
            self._store_cache(url, user_id, extracted)

            return {
                "success": True,
                "content": extracted,
                "cached": False
            }

        except requests.Timeout:
            logger.warning(f"Timeout fetching URL: {url}")
            return {
                "success": False,
                "error": "Request timed out. The website took too long to respond.",
                "cached": False
            }

        except requests.RequestException as e:
            logger.error(f"Request error for URL {url}: {e}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}",
                "cached": False
            }

        except Exception as e:
            logger.error(f"Unexpected error fetching URL {url}: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"An unexpected error occurred: {str(e)}",
                "cached": False
            }

    def _validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate URL for security

        Args:
            url: URL to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            parsed = urlparse(url)

            # Must be HTTPS
            if parsed.scheme != 'https':
                return False, "Only HTTPS URLs are supported for security reasons."

            # Must have a netloc
            if not parsed.netloc:
                return False, "Invalid URL format."

            # Check domain blocklist
            domain = parsed.netloc.lower()
            if domain in BLOCKED_DOMAINS:
                return False, f"Access to {domain} is not allowed."

            # Resolve domain to IP and check against blocked ranges
            try:
                ip_str = socket.gethostbyname(parsed.netloc)
                ip = ipaddress.IPv4Address(ip_str)

                for blocked_range in BLOCKED_IP_RANGES:
                    if ip in blocked_range:
                        logger.warning(f"Blocked private IP attempt: {url} -> {ip_str}")
                        return False, "Access to private network addresses is not allowed."

            except socket.gaierror:
                return False, f"Could not resolve domain: {parsed.netloc}"
            except Exception as e:
                logger.error(f"IP validation error: {e}")
                return False, f"URL validation failed: {str(e)}"

            return True, None

        except Exception as e:
            logger.error(f"URL parsing error: {e}")
            return False, f"Invalid URL format: {str(e)}"

    def _make_request(self, url: str) -> requests.Response:
        """
        Make HTTP request with security controls

        Args:
            url: URL to fetch

        Returns:
            Response object

        Raises:
            requests.RequestException on failure
            ValueError if content too large
        """
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers=headers,
            stream=True,
            allow_redirects=True,
            verify=True  # Verify SSL certificates
        )

        response.raise_for_status()

        # Check content length before downloading
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > MAX_CONTENT_SIZE:
            raise ValueError(f"Content too large: {content_length} bytes (max {MAX_CONTENT_SIZE})")

        # Download with size check
        chunks = []
        total_size = 0
        for chunk in response.iter_content(chunk_size=8192):
            total_size += len(chunk)
            if total_size > MAX_CONTENT_SIZE:
                raise ValueError(f"Content exceeds size limit (max {MAX_CONTENT_SIZE} bytes)")
            chunks.append(chunk)

        # Reconstruct response with full content
        response._content = b''.join(chunks)

        return response

    def _extract_content(self, html: str, url: str) -> Dict[str, Any]:
        """
        Extract readable content from HTML

        Args:
            html: Raw HTML string
            url: Source URL

        Returns:
            Dict with extracted content
        """
        soup = BeautifulSoup(html, 'lxml')

        # Remove unwanted elements
        for tag in ['script', 'style', 'iframe', 'object', 'embed', 'link', 'meta', 'base']:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove navigation, footers, ads
        for tag in ['nav', 'footer', 'aside', 'header']:
            for element in soup.find_all(tag):
                element.decompose()

        # Remove common ad classes
        ad_classes = ['ad', 'advertisement', 'sponsored', 'promo', 'social-share', 'comments']
        for class_name in ad_classes:
            for element in soup.find_all(class_=lambda x: x and class_name in x.lower()):
                element.decompose()

        # Extract title
        title = None
        if soup.title:
            title = soup.title.string
        elif soup.find('h1'):
            title = soup.find('h1').get_text()

        # Extract meta description
        description = None
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            description = meta_desc['content']

        # Extract main content
        # Try to find main content container
        main_content = None
        for selector in ['article', 'main', '[role="main"]', '.content', '.post', '.entry']:
            if isinstance(selector, str) and selector.startswith('.'):
                element = soup.find(class_=selector[1:])
            elif isinstance(selector, str) and selector.startswith('['):
                # Simple role selector
                element = soup.find(attrs={'role': 'main'})
            else:
                element = soup.find(selector)

            if element:
                main_content = element
                break

        # Fallback to body if no main content found
        if not main_content:
            main_content = soup.find('body')

        # Extract text
        if main_content:
            content_text = main_content.get_text(separator='\n', strip=True)
        else:
            content_text = soup.get_text(separator='\n', strip=True)

        # Clean up text
        lines = [line.strip() for line in content_text.split('\n')]
        lines = [line for line in lines if line]  # Remove empty lines
        content_text = '\n'.join(lines)

        # Calculate metadata
        word_count = len(content_text.split())

        return {
            'title': title,
            'description': description,
            'content': content_text,
            'url': url,
            'metadata': {
                'word_count': word_count,
                'content_length': len(content_text),
            }
        }

    def _check_cache(self, url: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Check if URL content is cached and valid

        Args:
            url: URL to check
            user_id: User ID

        Returns:
            Cached content dict or None
        """
        try:
            url_hash = self._hash_url(url)

            query = text("""
                SELECT title, content, metadata, fetched_at
                FROM web_fetch_cache
                WHERE user_id = :user_id
                  AND url_hash = :url_hash
                  AND expires_at > :now
                ORDER BY fetched_at DESC
                LIMIT 1
            """)

            with self.engine.begin() as conn:
                result = conn.execute(
                    query,
                    {
                        "user_id": user_id,
                        "url_hash": url_hash,
                        "now": datetime.now()
                    }
                ).fetchone()

                if result:
                    import json
                    return {
                        'title': result[0],
                        'content': result[1],
                        'url': url,
                        'metadata': json.loads(result[2]) if result[2] else {},
                        'cached_at': result[3]
                    }

            return None

        except Exception as e:
            logger.error(f"Cache check error: {e}")
            return None

    def _store_cache(self, url: str, user_id: int, content: Dict[str, Any]):
        """
        Store fetched content in cache

        Args:
            url: URL fetched
            user_id: User ID
            content: Extracted content dict
        """
        try:
            import json

            url_hash = self._hash_url(url)
            content_hash = hashlib.sha256(content['content'].encode()).hexdigest()
            now = datetime.now()
            expires_at = now + timedelta(seconds=CACHE_TTL_SECONDS)

            query = text("""
                INSERT INTO web_fetch_cache
                (user_id, url, url_hash, title, content, metadata, fetched_at, expires_at, content_hash)
                VALUES
                (:user_id, :url, :url_hash, :title, :content, :metadata, :fetched_at, :expires_at, :content_hash)
            """)

            with self.engine.begin() as conn:
                conn.execute(
                    query,
                    {
                        "user_id": user_id,
                        "url": url,
                        "url_hash": url_hash,
                        "title": content.get('title'),
                        "content": content['content'],
                        "metadata": json.dumps(content.get('metadata', {})),
                        "fetched_at": now,
                        "expires_at": expires_at,
                        "content_hash": content_hash
                    }
                )

            logger.info(f"Cached content for URL: {url}")

        except Exception as e:
            logger.error(f"Cache storage error: {e}")

    def _check_rate_limit(self, user_id: int) -> Dict[str, Any]:
        """
        Check if user has exceeded rate limits

        Args:
            user_id: User ID to check

        Returns:
            Dict with allowed, remaining, error keys
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=RATE_LIMIT_WINDOW_HOURS)

            query = text("""
                SELECT COUNT(*) as request_count
                FROM feature_provider_usage_logs
                WHERE user_id = :user_id
                  AND provider_type = 'web_fetch'
                  AND created_at > :cutoff_time
            """)

            with self.engine.begin() as conn:
                result = conn.execute(
                    query,
                    {"user_id": user_id, "cutoff_time": cutoff_time}
                ).fetchone()

                count = result[0] if result else 0

                if count >= RATE_LIMIT_MAX_REQUESTS:
                    return {
                        "allowed": False,
                        "remaining": 0,
                        "error": f"Rate limit exceeded: {RATE_LIMIT_MAX_REQUESTS} requests per {RATE_LIMIT_WINDOW_HOURS} hour(s)"
                    }

                return {
                    "allowed": True,
                    "remaining": RATE_LIMIT_MAX_REQUESTS - count,
                    "error": None
                }

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Allow on error to avoid blocking legitimate requests
            return {"allowed": True, "remaining": 0, "error": None}

    def format_response(self, content: Dict[str, Any], url: str) -> str:
        """
        Format extracted content for LLM consumption

        Args:
            content: Extracted content dict
            url: Source URL

        Returns:
            Formatted string
        """
        parts = []

        if content.get('title'):
            parts.append(f"Title: {content['title']}\n")

        if content.get('description'):
            parts.append(f"Description: {content['description']}\n")

        parts.append(f"Source: {url}\n")

        if content.get('metadata'):
            word_count = content['metadata'].get('word_count', 0)
            parts.append(f"Word Count: {word_count}\n")

        parts.append("\nContent:\n")
        parts.append(content['content'])

        return '\n'.join(parts)

    def format_multi_response(self, results: List[Dict[str, Any]]) -> str:
        """
        Format multiple URL results for LLM consumption

        Args:
            results: List of result dicts from fetch_urls

        Returns:
            Formatted string
        """
        parts = []
        parts.append(f"Fetched {len(results)} URL(s):\n")

        for i, result in enumerate(results, 1):
            parts.append(f"\n{'=' * 60}")
            parts.append(f"URL {i}: {result['url']}")
            parts.append('=' * 60)

            if result['success']:
                parts.append(self.format_response(result['content'], result['url']))
                if result.get('cached'):
                    parts.append("\n[Cached content]")
            else:
                parts.append(f"\nError: {result['error']}")

        return '\n'.join(parts)

    @staticmethod
    def cleanup_expired_cache(conn):
        """
        Clean up expired cache entries
        This should be called periodically (e.g., daily cron job)

        Args:
            conn: Database connection
        """
        try:
            query = text("""
                DELETE FROM web_fetch_cache
                WHERE expires_at < :now
            """)

            result = conn.execute(query, {"now": datetime.now()})
            deleted_count = result.rowcount
            conn.commit()

            logger.info(f"Cleaned up {deleted_count} expired cache entries")
            return deleted_count

        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            conn.rollback()
            return 0

    @staticmethod
    def _hash_url(url: str) -> str:
        """Generate hash of URL for cache key"""
        return hashlib.sha256(url.encode()).hexdigest()
