"""
Request utility functions.

Provides utilities for handling Flask request data, including:
- Client IP address detection from various headers
"""


def get_client_ip(request):
    """
    Extract client IP address from Flask request.

    Checks multiple sources in priority order:
    1. X-Forwarded-For header (first IP in list, from proxies)
    2. X-Real-IP header (from nginx/reverse proxies)
    3. request.remote_addr (direct connection)

    Args:
        request: Flask request object

    Returns:
        IP address as string (IPv4 or IPv6)
    """
    # Check X-Forwarded-For (may contain comma-separated list)
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # Take the first IP in the chain (original client)
        ip = forwarded_for.split(',')[0].strip()
        if ip:
            return ip

    # Check X-Real-IP
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip.strip()

    # Fall back to remote_addr
    return request.remote_addr
