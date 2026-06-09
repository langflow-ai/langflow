"""Unit tests for SSRF protection utilities."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from lfx.utils.ssrf_protection import (
    SSRFProtectionError,
    get_allowed_hosts,
    is_host_allowed,
    is_ip_blocked,
    is_ssrf_protection_enabled,
    resolve_hostname,
    validate_url_for_ssrf,
)


@contextmanager
def mock_ssrf_settings(*, enabled=False, allowed_hosts=None):
    """Context manager to mock SSRF settings."""
    if allowed_hosts is None:
        allowed_hosts = []

    with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
        mock_settings = MagicMock()
        mock_settings.settings.ssrf_protection_enabled = enabled
        mock_settings.settings.ssrf_allowed_hosts = allowed_hosts
        mock_get_settings.return_value = mock_settings
        yield


class TestSSRFProtectionConfiguration:
    """Test SSRF protection configuration and environment variables."""

    def test_ssrf_protection_disabled_by_default(self):
        """Test that SSRF protection is disabled by default (for now)."""
        # TODO: Update this test when default changes to enabled in v2.0
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_protection_enabled = False
            mock_get_settings.return_value = mock_settings
            assert is_ssrf_protection_enabled() is False

    @pytest.mark.parametrize(
        ("setting_value", "expected"),
        [
            (True, True),
            (False, False),
        ],
    )
    def test_ssrf_protection_setting(self, setting_value, expected):
        """Test SSRF protection setting value."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_protection_enabled = setting_value
            mock_get_settings.return_value = mock_settings
            assert is_ssrf_protection_enabled() == expected

    def test_allowed_hosts_empty_by_default(self):
        """Test that allowed hosts is empty by default."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = []
            mock_get_settings.return_value = mock_settings
            assert get_allowed_hosts() == []

    @pytest.mark.parametrize(
        ("setting_value", "expected"),
        [
            ([], []),
            (["example.com"], ["example.com"]),
            (["example.com", "api.example.com"], ["example.com", "api.example.com"]),
            (["192.168.1.0/24", "10.0.0.5"], ["192.168.1.0/24", "10.0.0.5"]),
            (["  example.com  ", "  api.example.com  "], ["example.com", "api.example.com"]),
            (["*.example.com"], ["*.example.com"]),
            (["", "example.com", "  ", "api.example.com"], ["example.com", "api.example.com"]),  # Test filtering
        ],
    )
    def test_allowed_hosts_parsing(self, setting_value, expected):
        """Test allowed hosts list cleaning and filtering."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = setting_value
            mock_get_settings.return_value = mock_settings
            assert get_allowed_hosts() == expected


class TestIPBlocking:
    """Test IP address blocking functionality."""

    @pytest.mark.parametrize(
        "ip",
        [
            # Loopback
            "127.0.0.1",
            "127.0.0.2",
            "127.255.255.255",
            "::1",
            # Private networks (RFC 1918)
            "10.0.0.1",
            "10.255.255.255",
            "172.16.0.1",
            "172.31.255.255",
            "192.168.0.1",
            "192.168.255.255",
            # Link-local / Cloud metadata
            "169.254.0.1",
            "169.254.169.254",  # AWS/GCP/Azure metadata
            "169.254.255.255",
            # Carrier-grade NAT
            "100.64.0.1",
            "100.127.255.255",
            # Documentation/Test ranges
            "192.0.2.1",
            "198.51.100.1",
            "203.0.113.1",
            # Multicast
            "224.0.0.1",
            "239.255.255.255",
            # Reserved
            "240.0.0.1",
            "255.255.255.254",
            # Broadcast
            "255.255.255.255",
            # IPv6 ranges
            "fc00::1",  # ULA
            "fe80::1",  # Link-local
            "ff00::1",  # Multicast
        ],
    )
    def test_blocked_ips(self, ip):
        """Test that private/internal IPs are blocked."""
        assert is_ip_blocked(ip) is True

    @pytest.mark.parametrize(
        "ip",
        [
            # Public IPv4 addresses
            "8.8.8.8",  # Google DNS
            "1.1.1.1",  # Cloudflare DNS
            "93.184.216.34",  # example.com
            "151.101.1.140",  # Reddit
            "13.107.42.14",  # Microsoft
            # Public IPv6 addresses
            "2001:4860:4860::8888",  # Google DNS
            "2606:4700:4700::1111",  # Cloudflare DNS
        ],
    )
    def test_allowed_ips(self, ip):
        """Test that public IPs are allowed."""
        assert is_ip_blocked(ip) is False

    def test_invalid_ip_is_blocked(self):
        """Test that invalid IPs are treated as blocked for safety."""
        assert is_ip_blocked("not.an.ip.address") is True
        assert is_ip_blocked("999.999.999.999") is True


class TestHostnameAllowlist:
    """Test hostname allowlist functionality."""

    def test_exact_hostname_match(self):
        """Test exact hostname matching in allowlist."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = ["internal.company.local"]
            mock_get_settings.return_value = mock_settings
            assert is_host_allowed("internal.company.local") is True
            assert is_host_allowed("other.company.local") is False

    def test_wildcard_hostname_match(self):
        """Test wildcard hostname matching in allowlist."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = ["*.company.local"]
            mock_get_settings.return_value = mock_settings
            assert is_host_allowed("api.company.local") is True
            assert is_host_allowed("internal.company.local") is True
            assert is_host_allowed("company.local") is True
            assert is_host_allowed("other.domain.com") is False

    def test_exact_ip_match(self):
        """Test exact IP matching in allowlist."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = ["192.168.1.5"]
            mock_get_settings.return_value = mock_settings
            assert is_host_allowed("example.com", "192.168.1.5") is True
            assert is_host_allowed("example.com", "192.168.1.6") is False

    def test_cidr_range_match(self):
        """Test CIDR range matching in allowlist."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = ["192.168.1.0/24", "10.0.0.0/16"]
            mock_get_settings.return_value = mock_settings
            assert is_host_allowed("example.com", "192.168.1.5") is True
            assert is_host_allowed("example.com", "192.168.1.255") is True
            assert is_host_allowed("example.com", "192.168.2.5") is False
            assert is_host_allowed("example.com", "10.0.0.1") is True
            assert is_host_allowed("example.com", "10.0.255.255") is True
            assert is_host_allowed("example.com", "10.1.0.1") is False

    def test_multiple_allowed_hosts(self):
        """Test multiple entries in allowlist."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = ["internal.local", "192.168.1.0/24", "*.api.company.com"]
            mock_get_settings.return_value = mock_settings
            assert is_host_allowed("internal.local") is True
            assert is_host_allowed("v1.api.company.com") is True
            assert is_host_allowed("example.com", "192.168.1.100") is True
            assert is_host_allowed("other.com", "10.0.0.1") is False

    def test_empty_allowlist(self):
        """Test that empty allowlist returns False."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_allowed_hosts = []
            mock_get_settings.return_value = mock_settings
            assert is_host_allowed("example.com") is False
            assert is_host_allowed("example.com", "192.168.1.1") is False


class TestHostnameResolution:
    """Test DNS hostname resolution."""

    def test_resolve_public_hostname(self):
        """Test resolving a public hostname."""
        # Use a stable public hostname
        ips = resolve_hostname("dns.google")
        assert len(ips) > 0
        # Should resolve to public IPs (8.8.8.8 or 8.8.4.4)
        assert any(not is_ip_blocked(ip) for ip in ips)

    def test_resolve_localhost(self):
        """Test resolving localhost."""
        ips = resolve_hostname("localhost")
        assert len(ips) > 0
        # Should include 127.0.0.1 or ::1
        assert any(ip in ("127.0.0.1", "::1") for ip in ips)

    def test_resolve_invalid_hostname(self):
        """Test that invalid hostnames raise SSRFProtectionError."""
        with pytest.raises(SSRFProtectionError, match="DNS resolution failed"):
            resolve_hostname("this-hostname-definitely-does-not-exist-12345.invalid")


class TestURLValidation:
    """Test URL validation for SSRF protection."""

    def test_protection_disabled_allows_all(self):
        """Test that when protection is disabled, all URLs are allowed."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_protection_enabled = False
            mock_get_settings.return_value = mock_settings
            # These should all pass without errors when protection is disabled
            validate_url_for_ssrf("http://127.0.0.1", warn_only=False)
            validate_url_for_ssrf("http://169.254.169.254", warn_only=False)
            validate_url_for_ssrf("http://192.168.1.1", warn_only=False)

    def test_invalid_scheme_blocked(self):
        """Test that non-http/https schemes are blocked."""
        with patch("lfx.utils.ssrf_protection.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.ssrf_protection_enabled = True
            mock_get_settings.return_value = mock_settings

            with pytest.raises(SSRFProtectionError, match="Invalid URL scheme"):
                validate_url_for_ssrf("ftp://example.com", warn_only=False)

            with pytest.raises(SSRFProtectionError, match="Invalid URL scheme"):
                validate_url_for_ssrf("file:///etc/passwd", warn_only=False)

    def test_valid_schemes_allowed(self):
        """Test that http and https schemes are explicitly allowed."""
        with (
            mock_ssrf_settings(enabled=True),
            patch("lfx.utils.ssrf_protection.resolve_hostname") as mock_resolve,
        ):
            mock_resolve.return_value = ["93.184.216.34"]  # Public IP (example.com)

            # Should not raise - valid schemes with public IPs
            validate_url_for_ssrf("http://example.com", warn_only=False)
            validate_url_for_ssrf("https://example.com", warn_only=False)
            validate_url_for_ssrf("https://api.example.com/v1", warn_only=False)

    def test_direct_ip_blocking(self):
        """Test blocking of direct IP addresses."""
        with mock_ssrf_settings(enabled=True):
            # Loopback
            with pytest.raises(SSRFProtectionError, match="blocked"):
                validate_url_for_ssrf("http://127.0.0.1", warn_only=False)

            # Private network
            with pytest.raises(SSRFProtectionError, match="blocked"):
                validate_url_for_ssrf("http://192.168.1.1", warn_only=False)

            # Metadata endpoint
            with pytest.raises(SSRFProtectionError, match="blocked"):
                validate_url_for_ssrf("http://169.254.169.254/latest/meta-data/", warn_only=False)

    def test_public_ips_allowed(self):
        """Test that public IP addresses are allowed."""
        with mock_ssrf_settings(enabled=True):
            # Should not raise
            validate_url_for_ssrf("http://8.8.8.8", warn_only=False)
            validate_url_for_ssrf("http://1.1.1.1", warn_only=False)

    def test_public_hostnames_allowed(self):
        """Test that public hostnames are allowed."""
        with mock_ssrf_settings(enabled=True):
            # Test with real DNS to stable Google service
            validate_url_for_ssrf("https://www.google.com", warn_only=False)

            # Mock DNS for other domains
            with patch("lfx.utils.ssrf_protection.resolve_hostname") as mock_resolve:
                mock_resolve.return_value = ["93.184.216.34"]  # Public IP
                validate_url_for_ssrf("https://api.example.com", warn_only=False)
                validate_url_for_ssrf("https://example.com", warn_only=False)

    def test_localhost_hostname_blocked(self):
        """Test that localhost hostname is blocked."""
        with mock_ssrf_settings(enabled=True), pytest.raises(SSRFProtectionError, match="blocked IP address"):
            validate_url_for_ssrf("http://localhost:8080", warn_only=False)

    def test_allowlist_bypass_hostname(self):
        """Test that allowlisted hostnames bypass SSRF checks."""
        with mock_ssrf_settings(enabled=True, allowed_hosts=["internal.company.local"]):
            # Should not raise even if it resolves to private IP
            # (We can't easily test actual resolution without mocking, but the allowlist check happens first)
            validate_url_for_ssrf("http://internal.company.local", warn_only=False)

    def test_allowlist_bypass_ip(self):
        """Test that allowlisted IPs bypass SSRF checks."""
        with mock_ssrf_settings(enabled=True, allowed_hosts=["192.168.1.5"]):
            # Should not raise
            validate_url_for_ssrf("http://192.168.1.5", warn_only=False)

    def test_allowlist_bypass_cidr(self):
        """Test that IPs in allowlisted CIDR ranges bypass SSRF checks."""
        with mock_ssrf_settings(enabled=True, allowed_hosts=["192.168.1.0/24"]):
            # Should not raise
            validate_url_for_ssrf("http://192.168.1.5", warn_only=False)
            validate_url_for_ssrf("http://192.168.1.100", warn_only=False)

    def test_warn_only_mode_logs_warnings(self):
        """Test that warn_only mode logs warnings instead of raising errors."""
        with mock_ssrf_settings(enabled=True), patch("lfx.utils.ssrf_protection.logger") as mock_logger:
            # Should not raise, but should log warning
            validate_url_for_ssrf("http://127.0.0.1", warn_only=True)

            # Check that warning was logged
            mock_logger.warning.assert_called()
            assert any("SSRF Protection Warning" in str(call) for call in mock_logger.warning.call_args_list)

    def test_malformed_url_raises_value_error(self):
        """Test that malformed URLs raise ValueError."""
        with mock_ssrf_settings(enabled=True), pytest.raises(ValueError, match="Invalid URL"):
            validate_url_for_ssrf("not a valid url", warn_only=False)

    def test_missing_hostname_blocked(self):
        """Test that URLs without hostname are blocked."""
        with mock_ssrf_settings(enabled=True), pytest.raises(SSRFProtectionError, match="valid hostname"):
            validate_url_for_ssrf("http://", warn_only=False)

    @pytest.mark.parametrize(
        "url",
        [
            "http://[::1]",  # IPv6 loopback
            "http://[::1]:8080/admin",
            "http://[fc00::1]",  # IPv6 ULA
            "http://[fe80::1]",  # IPv6 link-local
        ],
    )
    def test_ipv6_blocking(self, url):
        """Test that private IPv6 addresses are blocked."""
        with mock_ssrf_settings(enabled=True), pytest.raises(SSRFProtectionError, match="blocked"):
            validate_url_for_ssrf(url, warn_only=False)

    def test_ipv6_public_allowed(self):
        """Test that public IPv6 addresses are allowed."""
        with mock_ssrf_settings(enabled=True):
            # Should not raise
            validate_url_for_ssrf("http://[2001:4860:4860::8888]", warn_only=False)


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_aws_metadata_blocked(self):
        """Test that AWS metadata endpoint is blocked."""
        with mock_ssrf_settings(enabled=True), pytest.raises(SSRFProtectionError):
            validate_url_for_ssrf("http://169.254.169.254/latest/meta-data/iam/security-credentials/", warn_only=False)

    def test_internal_admin_panel_blocked(self):
        """Test that internal admin panels are blocked."""
        with mock_ssrf_settings(enabled=True), pytest.raises(SSRFProtectionError):
            validate_url_for_ssrf("http://192.168.1.1/admin", warn_only=False)

    def test_legitimate_api_allowed(self):
        """Test that legitimate external APIs are allowed."""
        with (
            mock_ssrf_settings(enabled=True),
            patch("lfx.utils.ssrf_protection.resolve_hostname") as mock_resolve,
        ):
            mock_resolve.return_value = ["104.16.132.229"]  # Public IP

            # Should all pass - mocked as public IPs
            validate_url_for_ssrf("https://api.openai.com/v1/chat/completions", warn_only=False)
            validate_url_for_ssrf("https://api.github.com/repos/langflow-ai/langflow", warn_only=False)
            validate_url_for_ssrf("https://www.googleapis.com/auth/cloud-platform", warn_only=False)

    def test_docker_internal_networking_requires_allowlist(self):
        """Test that Docker internal networking requires allowlist configuration."""
        with (
            mock_ssrf_settings(enabled=True),
            patch("lfx.utils.ssrf_protection.resolve_hostname") as mock_resolve,
        ):
            mock_resolve.return_value = ["172.18.0.2"]  # Docker bridge network IP

            # Without allowlist, should be blocked
            with pytest.raises(SSRFProtectionError):
                validate_url_for_ssrf("http://database:5432", warn_only=False)

        # With allowlist, should be allowed
        with (
            mock_ssrf_settings(enabled=True, allowed_hosts=["database", "*.internal.local"]),
            patch("lfx.utils.ssrf_protection.resolve_hostname") as mock_resolve,
        ):
            mock_resolve.return_value = ["172.18.0.2"]  # Docker bridge network IP

            validate_url_for_ssrf("http://database:5432", warn_only=False)
            validate_url_for_ssrf("http://api.internal.local", warn_only=False)
