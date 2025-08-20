"""Unit tests for CORS security configuration."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from langflow.services.settings.base import Settings


class TestCORSConfiguration:
    """Test CORS configuration and security validations."""

    def test_default_cors_settings(self):
        """Test default CORS settings are secure."""
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
            settings = Settings()
            assert settings.cors_origins == "*"
            assert settings.cors_allow_credentials is False
            assert settings.cors_allow_methods == "*"
            assert settings.cors_allow_headers == "*"

    def test_cors_origins_string_to_list_conversion(self):
        """Test comma-separated origins are converted to list."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_CONFIG_DIR": temp_dir,
                    "LANGFLOW_CORS_ORIGINS": "https://app1.example.com,https://app2.example.com",
                },
            ),
        ):
            settings = Settings()
            assert settings.cors_origins == ["https://app1.example.com", "https://app2.example.com"]

    def test_single_origin_remains_string(self):
        """Test single origin remains as string."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_CONFIG_DIR": temp_dir,
                    "LANGFLOW_CORS_ORIGINS": "https://app.example.com",
                },
            ),
        ):
            settings = Settings()
            assert settings.cors_origins == "https://app.example.com"

    def test_wildcard_with_credentials_prevented(self):
        """Test that credentials are disabled when using wildcard origins."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_CONFIG_DIR": temp_dir,
                    "LANGFLOW_CORS_ORIGINS": "*",
                    "LANGFLOW_CORS_ALLOW_CREDENTIALS": "true",
                },
            ),
        ):
            settings = Settings()
            assert settings.cors_origins == "*"
            # Should be forced to False for security
            assert settings.cors_allow_credentials is False

    def test_specific_origins_allow_credentials(self):
        """Test that credentials work with specific origins."""
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            patch.dict(
                os.environ,
                {
                    "LANGFLOW_CONFIG_DIR": temp_dir,
                    "LANGFLOW_CORS_ORIGINS": "https://app.example.com",
                    "LANGFLOW_CORS_ALLOW_CREDENTIALS": "true",
                },
            ),
        ):
            settings = Settings()
            assert settings.cors_origins == "https://app.example.com"
            assert settings.cors_allow_credentials is True

    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    @patch("langflow.main.get_settings_service")
    def test_cors_middleware_configuration(self, mock_get_settings, mock_setup_sentry):
        """Test that CORS middleware is configured correctly in the app."""
        from langflow.main import create_app

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.settings.cors_origins = "https://app.example.com"
        mock_settings.settings.cors_allow_credentials = True
        mock_settings.settings.cors_allow_methods = ["GET", "POST"]
        mock_settings.settings.cors_allow_headers = ["Content-Type"]
        mock_settings.settings.prometheus_enabled = False
        mock_settings.settings.mcp_server_enabled = False
        mock_settings.settings.sentry_dsn = None  # Disable Sentry
        mock_get_settings.return_value = mock_settings

        # Create app
        mock_setup_sentry.return_value = None  # Use the mock
        app = create_app()

        # Find CORS middleware
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        assert cors_middleware.kwargs["allow_origins"] == ["https://app.example.com"]
        assert cors_middleware.kwargs["allow_credentials"] is True
        assert cors_middleware.kwargs["allow_methods"] == ["GET", "POST"]
        assert cors_middleware.kwargs["allow_headers"] == ["Content-Type"]

    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    @patch("langflow.main.get_settings_service")
    @patch("langflow.main.logger")
    def test_cors_wildcard_credentials_runtime_check(self, mock_logger, mock_get_settings, mock_setup_sentry):
        """Test runtime validation prevents wildcard with credentials."""
        from langflow.main import create_app

        # Mock settings with invalid configuration
        mock_settings = MagicMock()
        mock_settings.settings.cors_origins = "*"
        mock_settings.settings.cors_allow_credentials = True  # Invalid combo
        mock_settings.settings.cors_allow_methods = "*"
        mock_settings.settings.cors_allow_headers = "*"
        mock_settings.settings.prometheus_enabled = False
        mock_settings.settings.mcp_server_enabled = False
        mock_settings.settings.sentry_dsn = None  # Disable Sentry
        mock_get_settings.return_value = mock_settings

        # Create app
        mock_setup_sentry.return_value = None  # Use the mock
        app = create_app()

        # Check that warning was logged
        mock_logger.warning.assert_called_with("SECURITY: Disabling credentials for wildcard CORS origins")

        # Find CORS middleware and verify credentials were disabled
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        assert cors_middleware.kwargs["allow_origins"] == "*"
        assert cors_middleware.kwargs["allow_credentials"] is False  # Should be forced to False


class TestRefreshTokenSecurity:
    """Test refresh token security improvements."""

    @pytest.mark.asyncio
    async def test_refresh_token_type_validation(self):
        """Test that refresh token validates token type."""
        from langflow.services.auth.utils import create_refresh_token

        mock_db = MagicMock()

        with patch("langflow.services.auth.utils.jwt.decode") as mock_decode:
            # Test with wrong token type
            mock_decode.return_value = {"sub": "user-123", "type": "access"}  # Wrong type

            with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
                mock_settings.return_value.auth_settings.SECRET_KEY.get_secret_value.return_value = "secret"
                mock_settings.return_value.auth_settings.ALGORITHM = "HS256"

                with pytest.raises(HTTPException) as exc_info:
                    await create_refresh_token("fake-token", mock_db)

                assert exc_info.value.status_code == 401
                assert "Invalid refresh token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_refresh_token_user_active_check(self):
        """Test that inactive users cannot refresh tokens."""
        from langflow.services.auth.utils import create_refresh_token

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.is_active = False  # Inactive user

        with patch("langflow.services.auth.utils.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user-123", "type": "refresh"}  # Correct type

            with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
                mock_settings.return_value.auth_settings.SECRET_KEY.get_secret_value.return_value = "secret"
                mock_settings.return_value.auth_settings.ALGORITHM = "HS256"

                with patch("langflow.services.auth.utils.get_user_by_id") as mock_get_user:
                    mock_get_user.return_value = mock_user

                    with pytest.raises(HTTPException) as exc_info:
                        await create_refresh_token("fake-token", mock_db)

                    assert exc_info.value.status_code == 401
                    assert "inactive" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_refresh_token_valid_flow(self):
        """Test that valid refresh tokens work correctly."""
        from langflow.services.auth.utils import create_refresh_token

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.is_active = True  # Active user
        mock_user.id = "user-123"

        with patch("langflow.services.auth.utils.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user-123", "type": "refresh"}  # Correct type

            with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
                mock_settings.return_value.auth_settings.SECRET_KEY.get_secret_value.return_value = "secret"
                mock_settings.return_value.auth_settings.ALGORITHM = "HS256"
                mock_settings.return_value.auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS = 3600
                mock_settings.return_value.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS = 604800

                with patch("langflow.services.auth.utils.get_user_by_id") as mock_get_user:
                    mock_get_user.return_value = mock_user

                    with patch("langflow.services.auth.utils.create_user_tokens") as mock_create_tokens:
                        expected_access = "new-access-token"
                        expected_refresh = "new-refresh-token"
                        mock_create_tokens.return_value = {
                            "access_token": expected_access,
                            "refresh_token": expected_refresh,
                        }

                        result = await create_refresh_token("fake-token", mock_db)

                        assert result["access_token"] == expected_access
                        assert result["refresh_token"] == expected_refresh
                        mock_create_tokens.assert_called_once_with("user-123", mock_db)

    def test_refresh_token_samesite_setting(self):
        """Test that refresh token uses SameSite=Lax by default."""
        from langflow.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
            auth_settings = AuthSettings(CONFIG_DIR=temp_dir)
            assert auth_settings.REFRESH_SAME_SITE == "lax"
            assert auth_settings.ACCESS_SAME_SITE == "lax"  # Access token should also be lax


class TestCORSIntegration:
    """Integration tests for CORS with actual HTTP requests."""

    @pytest.mark.asyncio
    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    async def test_cors_headers_in_response(self, mock_setup_sentry):
        """Test that CORS headers are properly set in responses."""
        from fastapi.testclient import TestClient

        with patch("langflow.main.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.cors_origins = ["https://app.example.com"]
            mock_settings.settings.cors_allow_credentials = True
            mock_settings.settings.cors_allow_methods = "*"
            mock_settings.settings.cors_allow_headers = "*"
            mock_settings.settings.prometheus_enabled = False
            mock_settings.settings.mcp_server_enabled = False
            mock_settings.settings.sentry_dsn = None  # Disable Sentry
            mock_get_settings.return_value = mock_settings

            from langflow.main import create_app

            mock_setup_sentry.return_value = None  # Use the mock
            app = create_app()
            client = TestClient(app)

            # Make OPTIONS request (CORS preflight)
            response = client.options(
                "/api/v1/version",
                headers={
                    "Origin": "https://app.example.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == "https://app.example.com"
            assert response.headers.get("access-control-allow-credentials") == "true"

    @pytest.mark.asyncio
    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    async def test_cors_blocks_unauthorized_origin(self, mock_setup_sentry):
        """Test that CORS blocks requests from unauthorized origins."""
        from fastapi.testclient import TestClient

        with patch("langflow.main.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.cors_origins = ["https://app.example.com"]
            mock_settings.settings.cors_allow_credentials = True
            mock_settings.settings.cors_allow_methods = "*"
            mock_settings.settings.cors_allow_headers = "*"
            mock_settings.settings.prometheus_enabled = False
            mock_settings.settings.mcp_server_enabled = False
            mock_settings.settings.sentry_dsn = None  # Disable Sentry
            mock_get_settings.return_value = mock_settings

            from langflow.main import create_app

            mock_setup_sentry.return_value = None  # Use the mock
            app = create_app()
            client = TestClient(app)

            # Make OPTIONS request from unauthorized origin
            response = client.options(
                "/api/v1/version",
                headers={
                    "Origin": "https://evil.com",
                    "Access-Control-Request-Method": "GET",
                },
            )

            assert response.status_code == 400  # CORS will block this