"""Tests for login endpoint rate limiting functionality."""

from __future__ import annotations

from unittest.mock import Mock

import pytest


@pytest.fixture
def enable_rate_limiting(monkeypatch):
    """Enable rate limiting for tests that need to verify rate limit behavior."""
    monkeypatch.setenv("LANGFLOW_RATE_LIMIT_ENABLED", "true")


@pytest.fixture
def limiter_snapshot():
    """Fixture to snapshot and restore the global limiter singleton."""
    import langflow.services.rate_limit.service as rate_limit_module

    original_limiter = rate_limit_module._limiter
    # Force recreation of limiter for each test to ensure clean state
    rate_limit_module._limiter = None
    yield
    rate_limit_module._limiter = original_limiter


class TestRateLimitService:
    """Test suite for rate limit service configuration."""

    def test_rate_limiter_is_configured(self, enable_rate_limiting):  # noqa: ARG002
        """Test that rate limiter singleton is properly configured."""
        from langflow.services.rate_limit import get_rate_limiter

        limiter = get_rate_limiter()

        assert limiter is not None
        assert limiter.enabled is True
        assert limiter._storage_uri == "memory://"  # Default storage
        assert limiter._swallow_errors is False  # Raise exceptions on rate limit

    def test_rate_limiter_is_singleton(self, enable_rate_limiting):  # noqa: ARG002
        """Test that get_rate_limiter returns the same instance."""
        from langflow.services.rate_limit import get_rate_limiter

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2

    def test_rate_limit_string_default(self, enable_rate_limiting):  # noqa: ARG002
        """Test that default rate limit string is correct."""
        from langflow.services.rate_limit.service import get_rate_limit_string

        rate_limit = get_rate_limit_string()

        assert rate_limit == "5/minute"

    def test_rate_limiter_uses_remote_address_by_default(self, enable_rate_limiting):  # noqa: ARG002
        """Test that rate limiter uses get_remote_address when trust_proxy is false."""
        from langflow.services.rate_limit import get_rate_limiter
        from slowapi.util import get_remote_address

        limiter = get_rate_limiter()

        # Default should use get_remote_address (not trust proxy)
        assert limiter._key_func == get_remote_address

    def test_rate_limiter_uses_client_ip_when_trust_proxy_enabled(
        self,
        enable_rate_limiting,  # noqa: ARG002
        limiter_snapshot,  # noqa: ARG002
        monkeypatch,
    ):
        """Test that rate limiter uses get_client_ip when trust_proxy is true."""
        # Mock settings to enable trust_proxy
        from unittest.mock import MagicMock

        from langflow.services.rate_limit.service import get_client_ip

        mock_settings = MagicMock()
        mock_settings.rate_limit_trust_proxy = True
        mock_settings.rate_limit_storage_uri = "memory://"

        mock_settings_service = MagicMock()
        mock_settings_service.settings = mock_settings

        monkeypatch.setattr("langflow.services.rate_limit.service.get_settings_service", lambda: mock_settings_service)

        from langflow.services.rate_limit import get_rate_limiter

        limiter = get_rate_limiter()

        # Should use get_client_ip when trust_proxy is enabled
        assert limiter._key_func == get_client_ip


class TestIPExtraction:
    """Test suite for IP address extraction logic."""

    def test_get_client_ip_from_x_forwarded_for_single(self):
        """Test IP extraction from X-Forwarded-For with single IP."""
        from langflow.services.rate_limit.service import get_client_ip

        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.1"}
        request.client = Mock(host="127.0.0.1")

        ip = get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_from_x_forwarded_for_chain_uses_rightmost(self):
        """Test IP extraction from X-Forwarded-For uses rightmost IP (trusted proxy)."""
        from langflow.services.rate_limit.service import get_client_ip

        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.1, 198.51.100.1, 192.0.2.1"}
        request.client = Mock(host="127.0.0.1")

        ip = get_client_ip(request)

        # Should use rightmost IP (the trusted proxy before us)
        assert ip == "192.0.2.1"

    def test_get_client_ip_from_x_forwarded_for_with_spaces(self):
        """Test IP extraction handles spaces in X-Forwarded-For."""
        from langflow.services.rate_limit.service import get_client_ip

        request = Mock()
        request.headers = {"X-Forwarded-For": "  203.0.113.1  ,  198.51.100.1  "}
        request.client = Mock(host="127.0.0.1")

        ip = get_client_ip(request)

        # Should use rightmost IP, stripped of whitespace
        assert ip == "198.51.100.1"

    def test_get_client_ip_from_direct_connection(self):
        """Test IP extraction from direct client connection (no proxy)."""
        from langflow.services.rate_limit.service import get_client_ip

        request = Mock()
        request.headers = {}
        request.client = Mock(host="192.168.1.100")

        ip = get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_get_client_ip_fallback_to_unknown(self):
        """Test IP extraction returns 'unknown' when no client info available."""
        from langflow.services.rate_limit.service import get_client_ip

        request = Mock()
        request.headers = {}
        request.client = None

        ip = get_client_ip(request)

        assert ip == "unknown"

    def test_get_client_ip_prefers_x_forwarded_for(self):
        """Test that X-Forwarded-For takes precedence over direct client IP."""
        from langflow.services.rate_limit.service import get_client_ip

        request = Mock()
        request.headers = {"X-Forwarded-For": "203.0.113.1"}
        request.client = Mock(host="127.0.0.1")

        ip = get_client_ip(request)

        # Should use X-Forwarded-For, not client.host
        assert ip == "203.0.113.1"
        assert ip != "127.0.0.1"


class TestRateLimitIntegration:
    """Integration tests verifying rate limiting is applied to login endpoint."""

    def test_rate_limit_enforcement_returns_429(self, enable_rate_limiting, limiter_snapshot, active_user):  # noqa: ARG002
        """Test that exceeding rate limit returns 429 status code.

        Uses TestClient (synchronous) instead of AsyncClient to properly test SlowAPI rate limiting.
        Requires limiter_snapshot fixture to ensure clean state and avoid interference from other tests.
        """
        from fastapi.testclient import TestClient
        from langflow.main import create_app

        # Create a fresh app instance for this test
        app = create_app()
        sync_client = TestClient(app)

        # Make 5 requests (the default limit)
        status_codes = []
        for i in range(5):
            response = sync_client.post(
                "/api/v1/login",
                data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
            )
            status_codes.append(response.status_code)
            assert response.status_code == 200, f"Request {i + 1} should succeed, got {response.status_code}"

        # 6th request should be rate limited
        response = sync_client.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
        )
        status_codes.append(response.status_code)

        assert response.status_code == 429, f"Expected 429, got {response.status_code}. All codes: {status_codes}"
        response_detail = response.json()["detail"].lower()
        assert "too many requests" in response_detail or "rate limit" in response_detail

    @pytest.mark.asyncio
    async def test_login_endpoint_has_rate_limiter_applied(self, enable_rate_limiting):  # noqa: ARG002
        """Test that the login endpoint has rate limiting applied via app.state.limiter."""
        from langflow.api.v1.login import get_limiter_from_app, login_to_get_access_token
        from langflow.main import create_app

        # Create app to ensure limiter is attached to app.state
        app = create_app()

        # Verify limiter is attached to app.state
        assert hasattr(app.state, "limiter")
        assert app.state.limiter is not None
        assert app.state.limiter.enabled is True

        # Verify the endpoint function exists
        assert login_to_get_access_token is not None
        # Verify get_limiter_from_app helper exists
        assert get_limiter_from_app is not None

    @pytest.mark.asyncio
    async def test_successful_login_within_reasonable_limit(self, enable_rate_limiting, client, active_user):  # noqa: ARG002
        """Test that a single login request succeeds (well within any rate limit)."""
        response = await client.post(
            "/api/v1/login",
            data={"username": active_user.username, "password": "testpassword"},  # pragma: allowlist secret
            headers={"X-Forwarded-For": "10.0.0.1"},  # Unique IP to avoid conflicts
        )

        assert response.status_code == 200
        assert "access_token" in response.json()
