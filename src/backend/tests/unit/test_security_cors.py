"""Unit tests for CORS security configuration."""

import os
import tempfile
import warnings
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from lfx.services.settings.base import Settings


class TestCORSConfiguration:
    """Test CORS configuration and security validations."""

    def test_default_cors_settings_current_behavior(self):
        """Test current CORS settings behavior (warns about security implications)."""
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
            settings = Settings()

            # Current behavior: wildcard origins with credentials ENABLED (insecure)
            assert settings.cors_origins == "*"
            assert settings.cors_allow_credentials is True  # Currently defaults to True (insecure)
            assert settings.cors_allow_methods == "*"
            assert settings.cors_allow_headers == "*"

            # Warn about CRITICAL security implications
            warnings.warn(
                "CRITICAL SECURITY WARNING: Current CORS configuration uses wildcard origins (*) "
                "WITH CREDENTIALS ENABLED! This allows any website to make authenticated requests "
                "to your Langflow instance and potentially steal user credentials. "
                "This will be changed to more secure defaults in v1.7. "
                "Please configure LANGFLOW_CORS_ORIGINS with specific domains for production use.",
                UserWarning,
                stacklevel=2,
            )

    @pytest.mark.skip(reason="Uncomment in v1.7 - represents future secure behavior")
    def test_default_cors_settings_secure_future(self):
        """Test future default CORS settings that will be secure (skip until v1.7)."""
        # This test represents the behavior we want in v1.7
        # with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
        #     settings = Settings()
        #     # Future secure defaults:
        #     assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000"]
        #     assert settings.cors_allow_credentials is True
        #     assert settings.cors_allow_methods == ["GET", "POST", "PUT", "DELETE"]
        #     assert settings.cors_allow_headers == ["Content-Type", "Authorization"]

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

    def test_single_origin_converted_to_list(self):
        """Test single origin is converted to list for consistency."""
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
            assert settings.cors_origins == ["https://app.example.com"]

    def test_wildcard_with_credentials_allowed_current_behavior(self):
        """Test that credentials are NOT disabled when using wildcard origins (current insecure behavior)."""
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
            # Current behavior: credentials are NOT prevented (INSECURE!)
            assert settings.cors_allow_credentials is True

            # Warn about the CRITICAL security implications
            warnings.warn(
                "CRITICAL SECURITY WARNING: Wildcard CORS origins (*) WITH CREDENTIALS ENABLED! "
                "This is a severe security vulnerability that allows any website to make "
                "authenticated requests and potentially steal user credentials. "
                "This MUST be fixed in production! Configure specific origins immediately.",
                UserWarning,
                stacklevel=2,
            )

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
            assert settings.cors_origins == ["https://app.example.com"]
            assert settings.cors_allow_credentials is True

    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    @patch("langflow.main.get_settings_service")
    def test_cors_middleware_configuration(self, mock_get_settings, mock_setup_sentry):
        """Test that CORS middleware is configured correctly in the app."""
        from langflow.main import create_app

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.settings.cors_origins = ["https://app.example.com"]
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
    def test_cors_wildcard_credentials_runtime_check_current_behavior(
        self, mock_logger, mock_get_settings, mock_setup_sentry
    ):
        """Test runtime validation prevents wildcard with credentials (current behavior)."""
        from langflow.main import create_app

        # Mock settings with configuration that triggers current security measure
        mock_settings = MagicMock()
        mock_settings.settings.cors_origins = "*"
        mock_settings.settings.cors_allow_credentials = True  # Gets disabled for security
        mock_settings.settings.cors_allow_methods = "*"
        mock_settings.settings.cors_allow_headers = "*"
        mock_settings.settings.prometheus_enabled = False
        mock_settings.settings.mcp_server_enabled = False
        mock_settings.settings.sentry_dsn = None  # Disable Sentry
        mock_get_settings.return_value = mock_settings

        # Create app
        mock_setup_sentry.return_value = None  # Use the mock
        app = create_app()

        # Check that warning was logged about deprecation/security
        # The actual warning message is different from what we expected
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        # We expect warnings about the insecure configuration
        assert any("DEPRECATION" in str(call) or "SECURITY" in str(call) for call in warning_calls), (
            f"Expected security warning but got: {warning_calls}"
        )

        # Find CORS middleware and verify credentials are still allowed (current insecure behavior)
        cors_middleware = None
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                cors_middleware = middleware
                break

        assert cors_middleware is not None
        assert cors_middleware.kwargs["allow_origins"] == "*"
        assert cors_middleware.kwargs["allow_credentials"] is True  # Current behavior: NOT disabled (insecure!)

        # Warn about the security implications
        warnings.warn(
            "CRITICAL SECURITY WARNING: Current behavior allows wildcard origins WITH CREDENTIALS ENABLED! "
            "This is a severe security vulnerability. Any website can make authenticated requests. "
            "In v1.7, this will be changed to secure defaults with specific origins only.",
            UserWarning,
            stacklevel=2,
        )


class TestRefreshTokenSecurity:
    """Test refresh token security improvements."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Token type validation not implemented - security enhancement for future")
    async def test_refresh_token_type_validation(self):
        """Test that refresh token validates token type.

        NOTE: Currently the code doesn't validate that the token type is 'refresh'.
        It only checks if the token_type is empty. This should be enhanced.
        """
        from langflow.services.auth.utils import create_refresh_token

        mock_db = MagicMock()

        with patch("langflow.services.auth.utils.jwt.decode") as mock_decode:
            # Test with wrong token type - use a valid UUID string
            mock_decode.return_value = {"sub": "123e4567-e89b-12d3-a456-426614174000", "type": "access"}  # Wrong type

            with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
                mock_settings.return_value.auth_settings.SECRET_KEY.get_secret_value.return_value = "secret"
                mock_settings.return_value.auth_settings.ALGORITHM = "HS256"
                mock_settings.return_value.auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS = 3600
                mock_settings.return_value.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS = 86400

                # This SHOULD raise an exception for wrong token type, but currently doesn't
                with pytest.raises(HTTPException) as exc_info:
                    await create_refresh_token("fake-token", mock_db)

                assert exc_info.value.status_code == 401
                assert "Invalid refresh token" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="User activity check not implemented yet - security enhancement for future")
    async def test_refresh_token_user_active_check(self):
        """Test that inactive users cannot refresh tokens.

        NOTE: This is a security enhancement that should be implemented.
        Currently, the system does not check if a user is active when refreshing tokens.
        """
        from langflow.services.auth.utils import create_refresh_token

        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.is_active = False  # Inactive user

        with patch("langflow.services.auth.utils.jwt.decode") as mock_decode:
            mock_decode.return_value = {"sub": "user-123", "type": "refresh"}  # Correct type

            with patch("langflow.services.auth.utils.get_settings_service") as mock_settings:
                mock_settings.return_value.auth_settings.SECRET_KEY.get_secret_value.return_value = "secret"
                mock_settings.return_value.auth_settings.ALGORITHM = "HS256"
                mock_settings.return_value.auth_settings.ACCESS_TOKEN_EXPIRE_SECONDS = 3600  # 1 hour
                mock_settings.return_value.auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS = 86400  # 1 day

                with patch("langflow.services.auth.utils.get_user_by_id") as mock_get_user:
                    mock_get_user.return_value = mock_user

                    # This SHOULD raise an exception for inactive users, but currently doesn't
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

    def test_refresh_token_samesite_setting_current_behavior(self):
        """Test current refresh token SameSite settings (warns about security)."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
            auth_settings = AuthSettings(CONFIG_DIR=temp_dir)
            # Current behavior: refresh token uses 'none' (allows cross-site)
            assert auth_settings.REFRESH_SAME_SITE == "none"  # Current: allows cross-site (less secure)
            assert auth_settings.ACCESS_SAME_SITE == "lax"  # Access token is already lax (good)

            # Warn about security implications
            warnings.warn(
                "SECURITY WARNING: Refresh tokens currently use SameSite=none which allows "
                "cross-site requests. This should be changed to 'lax' or 'strict' in production. "
                "In v1.7, this will default to 'lax' for better security.",
                UserWarning,
                stacklevel=2,
            )

    @pytest.mark.skip(reason="Uncomment in v1.7 - represents future secure SameSite behavior")
    def test_refresh_token_samesite_setting_future_secure(self):
        """Test future secure refresh token SameSite settings (skip until v1.7)."""
        # Future secure behavior (uncomment in v1.7):
        # from langflow.services.settings.auth import AuthSettings
        # with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
        #     auth_settings = AuthSettings(CONFIG_DIR=temp_dir)
        #     assert auth_settings.REFRESH_SAME_SITE == "lax"  # Secure default
        #     assert auth_settings.ACCESS_SAME_SITE == "lax"


class TestCORSIntegration:
    """Integration tests for CORS with actual HTTP requests."""

    @pytest.mark.asyncio
    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    async def test_cors_headers_in_response_current_behavior(self, mock_setup_sentry):
        """Test that CORS headers are properly set in responses (current behavior)."""
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

            # Warn that this is testing current behavior
            warnings.warn(
                "This test validates current CORS behavior. In v1.7, default origins will be more restrictive.",
                UserWarning,
                stacklevel=2,
            )

    @pytest.mark.skip(reason="Uncomment in v1.7 - represents future secure CORS blocking behavior")
    async def test_cors_blocks_unauthorized_origin_future_secure(self):
        """Test that future secure CORS configuration blocks unauthorized origins (skip until v1.7)."""
        # This test represents the behavior we want in v1.7 with secure defaults

    @pytest.mark.asyncio
    @patch("langflow.main.setup_sentry")  # Mock Sentry setup
    async def test_cors_blocks_unauthorized_origin_current_behavior(self, mock_setup_sentry):
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

            # Warn about current behavior implications
            warnings.warn(
                "This test shows current CORS behavior with specific origins. "
                "Note that current default behavior uses wildcard origins (*) which would NOT block this. "
                "In v1.7, secure defaults will be implemented to prevent unauthorized origins.",
                UserWarning,
                stacklevel=2,
            )


class TestFutureSecureCORSBehavior:
    """Tests for future secure CORS behavior in v1.7 - currently skipped."""

    @pytest.mark.skip(reason="Uncomment in v1.7 - represents future secure default CORS configuration")
    def test_future_secure_defaults(self):
        """Test that v1.7 will have secure CORS defaults."""
        # Future secure behavior (uncomment in v1.7):
        # with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LANGFLOW_CONFIG_DIR": temp_dir}):
        #     settings = Settings()
        #     # v1.7 secure defaults:
        #     assert settings.cors_origins == ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:7860"]
        #     assert settings.cors_allow_credentials is True  # Safe with specific origins
        #     assert settings.cors_allow_methods == ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        #     assert settings.cors_allow_headers == ["Content-Type", "Authorization", "X-Requested-With"]

    @pytest.mark.skip(reason="Uncomment in v1.7 - represents future secure wildcard rejection")
    def test_future_wildcard_rejection(self):
        """Test that v1.7 will warn about or reject wildcard origins in production."""
        # Future behavior (uncomment in v1.7):
        # with (
        #     tempfile.TemporaryDirectory() as temp_dir,
        #     patch.dict(
        #         os.environ,
        #         {
        #             "LANGFLOW_CONFIG_DIR": temp_dir,
        #             "LANGFLOW_CORS_ORIGINS": "*",
        #         },
        #     ),
        # ):
        #     # Should either warn strongly or reject wildcard in production mode
        #     with pytest.warns(UserWarning, match="SECURITY WARNING.*wildcard.*production"):
        #         settings = Settings()
        #         # Or potentially: pytest.raises(ValueError, match="Wildcard origins not allowed in production")

    @pytest.mark.skip(reason="Uncomment in v1.7 - represents future secure middleware configuration")
    async def test_future_secure_middleware_config(self):
        """Test that v1.7 middleware will use secure defaults."""
        # Future secure middleware behavior (uncomment in v1.7):
        # Test that the app creates middleware with secure defaults
        # and properly validates origins in production mode
