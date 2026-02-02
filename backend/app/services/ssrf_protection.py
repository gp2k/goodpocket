"""
SSRF (Server-Side Request Forgery) protection.
Validates URLs to prevent requests to internal/private resources.
"""
import ipaddress
import re
import socket
from urllib.parse import urlparse
from typing import Optional

import structlog

logger = structlog.get_logger()

# Blocked URL schemes
BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "javascript"}

# Regex for common private hostnames
PRIVATE_HOSTNAME_PATTERNS = [
    r"^localhost$",
    r"^127\.\d+\.\d+\.\d+$",
    r"^0\.0\.0\.0$",
    r"^10\.\d+\.\d+\.\d+$",
    r"^172\.(1[6-9]|2\d|3[01])\.\d+\.\d+$",
    r"^192\.168\.\d+\.\d+$",
    r"^169\.254\.\d+\.\d+$",  # Link-local
    r"^::1$",
    r"^fc00:",  # IPv6 ULA
    r"^fe80:",  # IPv6 link-local
    r"\.local$",
    r"\.internal$",
    r"\.localhost$",
    r"^metadata\.google\.internal$",  # GCP metadata
    r"^169\.254\.169\.254$",  # Cloud metadata endpoint
]

PRIVATE_HOSTNAME_REGEX = re.compile(
    "|".join(f"({p})" for p in PRIVATE_HOSTNAME_PATTERNS),
    re.IGNORECASE
)


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is private, reserved, or loopback.
    
    Args:
        ip_str: IP address string
        
    Returns:
        True if the IP is private/reserved/loopback
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_reserved
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
        )
    except ValueError:
        # Invalid IP, consider it potentially dangerous
        return True


def resolve_hostname(hostname: str) -> Optional[str]:
    """
    Resolve hostname to IP address.
    
    Args:
        hostname: Hostname to resolve
        
    Returns:
        IP address string or None if resolution fails
    """
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


def validate_url(url: str) -> bool:
    """
    Validate a URL for SSRF protection.
    
    Checks:
    - URL scheme (must be http or https)
    - Hostname not matching private patterns
    - Resolved IP not in private ranges
    
    Args:
        url: URL to validate
        
    Returns:
        True if URL is safe to fetch, False otherwise
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        scheme = parsed.scheme.lower()
        if scheme in BLOCKED_SCHEMES or scheme not in {"http", "https"}:
            logger.warning("Blocked URL scheme", url=url, scheme=scheme)
            return False
        
        # Check hostname exists
        hostname = parsed.hostname
        if not hostname:
            logger.warning("URL missing hostname", url=url)
            return False
        
        hostname_lower = hostname.lower()
        
        # Check against private hostname patterns
        if PRIVATE_HOSTNAME_REGEX.search(hostname_lower):
            logger.warning("Blocked private hostname", url=url, hostname=hostname)
            return False
        
        # Resolve and check IP
        resolved_ip = resolve_hostname(hostname)
        if resolved_ip and is_private_ip(resolved_ip):
            logger.warning(
                "Blocked private IP",
                url=url,
                hostname=hostname,
                resolved_ip=resolved_ip
            )
            return False
        
        # Check port (block common internal ports)
        port = parsed.port
        if port and port not in {80, 443, 8080, 8443}:
            # Allow common web ports, be cautious with others
            # For MVP, we'll allow all ports but log it
            logger.info("Non-standard port used", url=url, port=port)
        
        return True
        
    except Exception as e:
        logger.warning("URL validation error", url=url, error=str(e))
        return False
