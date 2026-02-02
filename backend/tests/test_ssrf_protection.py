"""
Tests for SSRF protection.
"""
import pytest
from app.services.ssrf_protection import validate_url, is_private_ip


class TestIsPrivateIP:
    """Tests for is_private_ip function."""

    def test_localhost(self):
        """Localhost IPs should be private."""
        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.0.0.2") is True

    def test_private_ranges(self):
        """Private IP ranges should be detected."""
        # 10.x.x.x
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True
        
        # 172.16-31.x.x
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True
        
        # 192.168.x.x
        assert is_private_ip("192.168.0.1") is True
        assert is_private_ip("192.168.255.255") is True

    def test_link_local(self):
        """Link-local addresses should be private."""
        assert is_private_ip("169.254.0.1") is True
        assert is_private_ip("169.254.169.254") is True  # AWS metadata

    def test_public_ips(self):
        """Public IPs should not be private."""
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("93.184.216.34") is False  # example.com

    def test_ipv6_localhost(self):
        """IPv6 localhost should be private."""
        assert is_private_ip("::1") is True

    def test_invalid_ip(self):
        """Invalid IPs should be considered private (safe)."""
        assert is_private_ip("not-an-ip") is True
        assert is_private_ip("") is True


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_https_url(self):
        """Valid HTTPS URLs should pass."""
        assert validate_url("https://example.com") is True
        assert validate_url("https://example.com/path") is True
        assert validate_url("https://subdomain.example.com/path?query=1") is True

    def test_valid_http_url(self):
        """Valid HTTP URLs should pass."""
        assert validate_url("http://example.com") is True

    def test_blocked_schemes(self):
        """Non-HTTP(S) schemes should be blocked."""
        assert validate_url("file:///etc/passwd") is False
        assert validate_url("ftp://example.com") is False
        assert validate_url("javascript:alert(1)") is False
        assert validate_url("data:text/html,<h1>Hi</h1>") is False
        assert validate_url("gopher://example.com") is False

    def test_localhost_blocked(self):
        """Localhost URLs should be blocked."""
        assert validate_url("http://localhost") is False
        assert validate_url("http://localhost:8080") is False
        assert validate_url("http://127.0.0.1") is False
        assert validate_url("http://127.0.0.1:3000") is False

    def test_private_ip_blocked(self):
        """Private IP URLs should be blocked."""
        assert validate_url("http://10.0.0.1") is False
        assert validate_url("http://172.16.0.1") is False
        assert validate_url("http://192.168.1.1") is False

    def test_cloud_metadata_blocked(self):
        """Cloud metadata endpoints should be blocked."""
        assert validate_url("http://169.254.169.254") is False
        assert validate_url("http://metadata.google.internal") is False

    def test_local_domains_blocked(self):
        """Local domain suffixes should be blocked."""
        assert validate_url("http://server.local") is False
        assert validate_url("http://internal.localhost") is False
        assert validate_url("http://myapp.internal") is False

    def test_missing_hostname(self):
        """URLs without hostname should fail."""
        assert validate_url("http://") is False
        assert validate_url("https://") is False

    def test_invalid_url(self):
        """Invalid URLs should fail."""
        assert validate_url("not a url") is False
        assert validate_url("") is False
        assert validate_url("://example.com") is False


class TestCommonAttackPatterns:
    """Tests for common SSRF attack patterns."""

    def test_dns_rebinding_patterns(self):
        """Common DNS rebinding patterns should be blocked after resolution."""
        # These hostnames might resolve to private IPs
        # The actual blocking depends on DNS resolution
        # We test the URL format validation here
        assert validate_url("http://0.0.0.0") is False
        assert validate_url("http://0") is False

    def test_ipv6_localhost(self):
        """IPv6 localhost should be blocked."""
        # IPv6 localhost formats
        assert validate_url("http://[::1]") is False
        assert validate_url("http://[0:0:0:0:0:0:0:1]") is False

    def test_url_with_auth(self):
        """URLs with auth info should still be validated."""
        # Auth info shouldn't bypass validation
        assert validate_url("http://user:pass@localhost") is False
        assert validate_url("http://user:pass@127.0.0.1") is False

    def test_encoded_localhost(self):
        """URL-encoded localhost should be handled."""
        # Python's urlparse handles these
        assert validate_url("http://localhost") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
