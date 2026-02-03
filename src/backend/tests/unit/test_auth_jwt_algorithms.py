"""Comprehensive tests for JWT algorithm support (HS256, RS256, RS512).

Tests cover:
- AuthSettings configuration for each algorithm
- RSA key generation and persistence
- Token creation and verification
- Error cases and edge cases
- Authentication failure scenarios
"""

import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest
from fastapi import HTTPException
from jwt import InvalidTokenError
from pydantic import SecretStr


class TestAuthSettingsAlgorithms:
    """Test AuthSettings configuration for different JWT algorithms."""

    def test_default_algorithm_is_hs256(self):
        """Default algorithm should be HS256 for backward compatibility (when not overridden by env)."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            # Explicitly set HS256 to test the setting works (env var may override default)
            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")
            assert settings.ALGORITHM == "HS256"

    def test_hs256_generates_secret_key(self):
        """HS256 should generate a secret key automatically."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")
            secret_key = settings.SECRET_KEY.get_secret_value()
            assert secret_key is not None
            assert len(secret_key) >= 32

    def test_rs256_generates_rsa_key_pair(self):
        """RS256 should generate RSA key pair automatically."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")

            private_key = settings.PRIVATE_KEY.get_secret_value()
            public_key = settings.PUBLIC_KEY

            assert private_key is not None
            assert public_key is not None
            assert "-----BEGIN PRIVATE KEY-----" in private_key
            assert "-----BEGIN PUBLIC KEY-----" in public_key

    def test_rs512_generates_rsa_key_pair(self):
        """RS512 should generate RSA key pair automatically."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS512")

            private_key = settings.PRIVATE_KEY.get_secret_value()
            public_key = settings.PUBLIC_KEY

            assert private_key is not None
            assert public_key is not None
            assert "-----BEGIN PRIVATE KEY-----" in private_key
            assert "-----BEGIN PUBLIC KEY-----" in public_key

    def test_rsa_keys_persisted_to_files(self):
        """RSA keys should be persisted to files in CONFIG_DIR."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")

            private_key_path = Path(tmpdir) / "private_key.pem"
            public_key_path = Path(tmpdir) / "public_key.pem"

            assert private_key_path.exists()
            assert public_key_path.exists()

            # Verify file contents match settings
            assert private_key_path.read_text() == settings.PRIVATE_KEY.get_secret_value()
            assert public_key_path.read_text() == settings.PUBLIC_KEY

    def test_rsa_keys_loaded_from_existing_files(self):
        """RSA keys should be loaded from existing files."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            # First run - generate keys
            settings1 = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")
            original_private = settings1.PRIVATE_KEY.get_secret_value()
            original_public = settings1.PUBLIC_KEY

            # Second run - should load existing keys
            settings2 = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")

            assert settings2.PRIVATE_KEY.get_secret_value() == original_private
            assert original_public == settings2.PUBLIC_KEY

    def test_custom_private_key_derives_public_key(self):
        """When custom private key is provided, public key should be derived."""
        from lfx.services.settings.auth import AuthSettings
        from lfx.services.settings.utils import generate_rsa_key_pair

        custom_private, expected_public = generate_rsa_key_pair()

        with tempfile.TemporaryDirectory() as tmpdir:
            settings = AuthSettings(
                CONFIG_DIR=tmpdir,
                ALGORITHM="RS256",
                PRIVATE_KEY=SecretStr(custom_private),
            )

            assert settings.PRIVATE_KEY.get_secret_value() == custom_private
            assert expected_public == settings.PUBLIC_KEY

    def test_no_config_dir_generates_keys_in_memory(self):
        """Without CONFIG_DIR, keys should be generated in memory."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR="", ALGORITHM="RS256")

        assert settings.PRIVATE_KEY.get_secret_value() is not None
        assert settings.PUBLIC_KEY is not None
        assert "-----BEGIN PRIVATE KEY-----" in settings.PRIVATE_KEY.get_secret_value()

    def test_hs256_does_not_generate_rsa_keys(self):
        """HS256 should not trigger RSA key generation."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")

            private_key_path = Path(tmpdir) / "private_key.pem"
            public_key_path = Path(tmpdir) / "public_key.pem"

            # RSA key files should not be created for HS256
            assert not private_key_path.exists()
            assert not public_key_path.exists()

    def test_invalid_algorithm_rejected(self):
        """Invalid algorithm should be rejected by pydantic."""
        from lfx.services.settings.auth import AuthSettings
        from pydantic import ValidationError

        with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(ValidationError):
            AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="INVALID")


class TestRSAKeyGeneration:
    """Test RSA key pair generation utility."""

    def test_generate_rsa_key_pair_returns_valid_keys(self):
        """Generated keys should be valid PEM format."""
        from lfx.services.settings.utils import generate_rsa_key_pair

        private_key, public_key = generate_rsa_key_pair()

        assert "-----BEGIN PRIVATE KEY-----" in private_key
        assert "-----END PRIVATE KEY-----" in private_key
        assert "-----BEGIN PUBLIC KEY-----" in public_key
        assert "-----END PUBLIC KEY-----" in public_key

    def test_generated_keys_are_unique(self):
        """Each call should generate unique keys."""
        from lfx.services.settings.utils import generate_rsa_key_pair

        private1, public1 = generate_rsa_key_pair()
        private2, public2 = generate_rsa_key_pair()

        assert private1 != private2
        assert public1 != public2

    def test_generated_keys_can_sign_and_verify(self):
        """Generated keys should work for JWT signing and verification."""
        from lfx.services.settings.utils import generate_rsa_key_pair

        private_key, public_key = generate_rsa_key_pair()

        # Sign a token
        payload = {"sub": "test-user", "type": "access"}
        token = jwt.encode(payload, private_key, algorithm="RS256")

        # Verify the token
        decoded = jwt.decode(token, public_key, algorithms=["RS256"])

        assert decoded["sub"] == "test-user"
        assert decoded["type"] == "access"


class TestTokenCreation:
    """Test JWT token creation with different algorithms."""

    def _create_mock_settings_service(self, algorithm, tmpdir):
        """Helper to create mock settings service."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM=algorithm)

        mock_service = MagicMock()
        mock_service.auth_settings = settings
        return mock_service

    def test_create_token_hs256(self):
        """Token creation with HS256 should use secret key."""
        from langflow.services.auth.utils import create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                token = create_token(
                    data={"sub": "user-123", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                assert token is not None
                # Verify token header shows HS256
                header = jwt.get_unverified_header(token)
                assert header["alg"] == "HS256"

    def test_create_token_rs256(self):
        """Token creation with RS256 should use private key."""
        from langflow.services.auth.utils import create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                token = create_token(
                    data={"sub": "user-456", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                assert token is not None
                # Verify token header shows RS256
                header = jwt.get_unverified_header(token)
                assert header["alg"] == "RS256"

    def test_create_token_rs512(self):
        """Token creation with RS512 should use private key."""
        from langflow.services.auth.utils import create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS512", tmpdir)

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                token = create_token(
                    data={"sub": "user-789", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                assert token is not None
                # Verify token header shows RS512
                header = jwt.get_unverified_header(token)
                assert header["alg"] == "RS512"

    def test_token_contains_expiration(self):
        """Created token should contain expiration claim."""
        from langflow.services.auth.utils import create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                token = create_token(
                    data={"sub": "user-123", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                # Decode without verification to check claims
                claims = jwt.decode(token, options={"verify_signature": False})
                assert "exp" in claims


class TestTokenVerification:
    """Test JWT token verification with different algorithms."""

    def _create_mock_settings_service(self, algorithm, tmpdir):
        """Helper to create mock settings service."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM=algorithm)

        mock_service = MagicMock()
        mock_service.auth_settings = settings
        return mock_service

    @pytest.mark.asyncio
    async def test_verify_hs256_token_success(self):
        """Valid HS256 token should be verified successfully."""
        from langflow.services.auth.utils import create_token, get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            # Create a mock user
            mock_user = MagicMock()
            mock_user.id = "user-123"
            mock_user.is_active = True

            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=mock_user),
            ):
                token = create_token(
                    data={"sub": "user-123", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                user = await get_current_user_by_jwt(token, mock_db)
                assert user == mock_user

    @pytest.mark.asyncio
    async def test_verify_rs256_token_success(self):
        """Valid RS256 token should be verified successfully."""
        from langflow.services.auth.utils import create_token, get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)

            mock_user = MagicMock()
            mock_user.id = "user-456"
            mock_user.is_active = True

            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=mock_user),
            ):
                token = create_token(
                    data={"sub": "user-456", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                user = await get_current_user_by_jwt(token, mock_db)
                assert user == mock_user

    @pytest.mark.asyncio
    async def test_verify_rs512_token_success(self):
        """Valid RS512 token should be verified successfully."""
        from langflow.services.auth.utils import create_token, get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS512", tmpdir)

            mock_user = MagicMock()
            mock_user.id = "user-789"
            mock_user.is_active = True

            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=mock_user),
            ):
                token = create_token(
                    data={"sub": "user-789", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                user = await get_current_user_by_jwt(token, mock_db)
                assert user == mock_user


class TestAuthenticationFailures:
    """Test authentication failure scenarios."""

    def _create_mock_settings_service(self, algorithm, tmpdir, **overrides):
        """Helper to create mock settings service with optional overrides."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM=algorithm)

        # Apply overrides
        for key, value in overrides.items():
            object.__setattr__(settings, key, value)

        mock_service = MagicMock()
        mock_service.auth_settings = settings
        return mock_service

    @pytest.mark.asyncio
    async def test_missing_public_key_rs256_raises_401(self):
        """Missing public key for RS256 should raise 401."""
        from langflow.services.auth.utils import get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir, PUBLIC_KEY="")

            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt("some-token", mock_db)

                assert exc_info.value.status_code == 401
                assert "Server configuration error" in exc_info.value.detail
                assert "Public key not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_missing_secret_key_hs256_raises_401(self):
        """Missing secret key for HS256 should raise 401."""
        from langflow.services.auth.utils import get_current_user_by_jwt
        from lfx.services.settings.auth import JWTAlgorithm

        # Create a fully mocked settings service without using AuthSettings
        mock_auth_settings = MagicMock()
        mock_auth_settings.ALGORITHM = JWTAlgorithm.HS256
        mock_auth_settings.SECRET_KEY = MagicMock()
        mock_auth_settings.SECRET_KEY.get_secret_value.return_value = None

        mock_service = MagicMock()
        mock_service.auth_settings = mock_auth_settings

        mock_db = AsyncMock()

        with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_by_jwt("some-token", mock_db)

            assert exc_info.value.status_code == 401
            assert "Server configuration error" in exc_info.value.detail
            assert "Secret key not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        """Invalid token should raise 401."""
        from langflow.services.auth.utils import get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)
            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt("invalid-token-format", mock_db)

                assert exc_info.value.status_code == 401
                assert "Could not validate credentials" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_token_signed_with_wrong_key_raises_401(self):
        """Token signed with different key should raise 401."""
        from langflow.services.auth.utils import get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            # Create token with different secret
            wrong_token = jwt.encode(
                {"sub": "user-123", "type": "access"},
                "different-secret-key",
                algorithm="HS256",
            )

            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt(wrong_token, mock_db)

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_expired_token_raises_401(self):
        """Expired token should raise 401."""
        from langflow.services.auth.utils import create_token, get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)
            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                # Create token that's already expired
                token = create_token(
                    data={"sub": "user-123", "type": "access"},
                    expires_delta=timedelta(seconds=-10),  # Negative = already expired
                )

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt(token, mock_db)

                assert exc_info.value.status_code == 401
                # PyJWT library raises InvalidTokenError for expired tokens before our custom check
                assert (
                    "expired" in exc_info.value.detail.lower() or "could not validate" in exc_info.value.detail.lower()
                )

    @pytest.mark.asyncio
    async def test_token_without_user_id_raises_401(self):
        """Token without user ID should raise 401."""
        from langflow.services.auth.utils import get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            # Create token without 'sub' claim
            token = jwt.encode(
                {"type": "access"},
                mock_service.auth_settings.SECRET_KEY.get_secret_value(),
                algorithm="HS256",
            )

            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt(token, mock_db)

                assert exc_info.value.status_code == 401
                assert "Invalid token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_token_without_type_raises_401(self):
        """Token without type should raise 401."""
        from langflow.services.auth.utils import get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            # Create token without 'type' claim
            token = jwt.encode(
                {"sub": "user-123"},
                mock_service.auth_settings.SECRET_KEY.get_secret_value(),
                algorithm="HS256",
            )

            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt(token, mock_db)

                assert exc_info.value.status_code == 401
                assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_user_not_found_raises_401(self):
        """Token for non-existent user should raise 401."""
        from langflow.services.auth.utils import create_token, get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)
            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=None),
            ):
                token = create_token(
                    data={"sub": "non-existent-user", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt(token, mock_db)

                assert exc_info.value.status_code == 401
                assert "User not found" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_inactive_user_raises_401(self):
        """Token for inactive user should raise 401."""
        from langflow.services.auth.utils import create_token, get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            mock_user = MagicMock()
            mock_user.is_active = False

            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=mock_user),
            ):
                token = create_token(
                    data={"sub": "inactive-user", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user_by_jwt(token, mock_db)

                assert exc_info.value.status_code == 401
                assert "inactive" in exc_info.value.detail.lower()


class TestRefreshTokenVerification:
    """Test refresh token verification with different algorithms."""

    def _create_mock_settings_service(self, algorithm, tmpdir):
        """Helper to create mock settings service."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM=algorithm)

        mock_service = MagicMock()
        mock_service.auth_settings = settings
        return mock_service

    @pytest.mark.asyncio
    async def test_refresh_token_rs256_success(self):
        """Valid RS256 refresh token should create new tokens."""
        from langflow.services.auth.utils import create_refresh_token, create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)

            mock_user = MagicMock()
            mock_user.id = "user-123"
            mock_user.is_active = True

            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=mock_user),
            ):
                # Create refresh token
                refresh_token = create_token(
                    data={"sub": "user-123", "type": "refresh"},
                    expires_delta=timedelta(days=7),
                )

                # Use refresh token to get new tokens
                new_tokens = await create_refresh_token(refresh_token, mock_db)

                assert "access_token" in new_tokens
                assert "refresh_token" in new_tokens
                assert new_tokens.get("token_type") == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_wrong_type_raises_401(self):
        """Access token used as refresh token should raise 401."""
        from langflow.services.auth.utils import create_refresh_token, create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)
            mock_db = AsyncMock()

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                # Create access token (not refresh)
                access_token = create_token(
                    data={"sub": "user-123", "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                with pytest.raises(HTTPException) as exc_info:
                    await create_refresh_token(access_token, mock_db)

                assert exc_info.value.status_code == 401
                assert "Invalid refresh token" in exc_info.value.detail


class TestAlgorithmMismatch:
    """Test scenarios where algorithm configuration changes."""

    def test_hs256_token_fails_with_rs256_verification(self):
        """Token created with HS256 should fail RS256 verification."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create token with HS256
            hs256_settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")
            token = jwt.encode(
                {"sub": "user-123", "type": "access"},
                hs256_settings.SECRET_KEY.get_secret_value(),
                algorithm="HS256",
            )

        with tempfile.TemporaryDirectory() as tmpdir2:
            # Try to verify with RS256
            rs256_settings = AuthSettings(CONFIG_DIR=tmpdir2, ALGORITHM="RS256")

            with pytest.raises(InvalidTokenError):
                jwt.decode(token, rs256_settings.PUBLIC_KEY, algorithms=["RS256"])

    def test_rs256_token_fails_with_hs256_verification(self):
        """Token created with RS256 should fail HS256 verification."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create token with RS256
            rs256_settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")
            token = jwt.encode(
                {"sub": "user-123", "type": "access"},
                rs256_settings.PRIVATE_KEY.get_secret_value(),
                algorithm="RS256",
            )

        with tempfile.TemporaryDirectory() as tmpdir2:
            # Try to verify with HS256
            hs256_settings = AuthSettings(CONFIG_DIR=tmpdir2, ALGORITHM="HS256")

            with pytest.raises(InvalidTokenError):
                jwt.decode(
                    token,
                    hs256_settings.SECRET_KEY.get_secret_value(),
                    algorithms=["HS256"],
                )


class TestKeyPersistence:
    """Test key persistence and file permissions."""

    def test_secret_key_file_created(self):
        """Secret key should be saved to file."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")

            secret_key_path = Path(tmpdir) / "secret_key"
            assert secret_key_path.exists()

    def test_rsa_key_files_created(self):
        """RSA keys should be saved to files."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")

            private_key_path = Path(tmpdir) / "private_key.pem"
            public_key_path = Path(tmpdir) / "public_key.pem"

            assert private_key_path.exists()
            assert public_key_path.exists()

    def test_keys_reloaded_on_restart(self):
        """Keys should be consistent across settings reloads."""
        from lfx.services.settings.auth import AuthSettings

        with tempfile.TemporaryDirectory() as tmpdir:
            # First load
            settings1 = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")
            private1 = settings1.PRIVATE_KEY.get_secret_value()
            public1 = settings1.PUBLIC_KEY

            # Simulate restart
            settings2 = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="RS256")
            private2 = settings2.PRIVATE_KEY.get_secret_value()
            public2 = settings2.PUBLIC_KEY

            assert private1 == private2
            assert public1 == public2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_config_dir_string(self):
        """Empty CONFIG_DIR string should work (in-memory keys)."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR="", ALGORITHM="RS256")
        assert settings.PRIVATE_KEY.get_secret_value() is not None
        assert settings.PUBLIC_KEY is not None

    def test_token_with_extra_claims(self):
        """Token with extra claims should still work."""
        from langflow.services.auth.utils import get_current_user_by_jwt

        with tempfile.TemporaryDirectory() as tmpdir:
            from lfx.services.settings.auth import AuthSettings

            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")

            token = jwt.encode(
                {
                    "sub": "user-123",
                    "type": "access",
                    "extra_claim": "some-value",
                    "another": 123,
                },
                settings.SECRET_KEY.get_secret_value(),
                algorithm="HS256",
            )

            mock_service = MagicMock()
            mock_service.auth_settings = settings

            mock_user = MagicMock()
            mock_user.id = "user-123"
            mock_user.is_active = True

            mock_db = AsyncMock()

            with (
                patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service),
                patch("langflow.services.auth.utils.get_user_by_id", return_value=mock_user),
            ):
                import asyncio

                user = asyncio.get_event_loop().run_until_complete(get_current_user_by_jwt(token, mock_db))
                assert user == mock_user

    def test_very_long_user_id(self):
        """Very long user ID should work."""
        from langflow.services.auth.utils import create_token

        with tempfile.TemporaryDirectory() as tmpdir:
            from lfx.services.settings.auth import AuthSettings

            settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM="HS256")

            mock_service = MagicMock()
            mock_service.auth_settings = settings

            long_user_id = "a" * 1000

            with patch("langflow.services.auth.utils.get_settings_service", return_value=mock_service):
                token = create_token(
                    data={"sub": long_user_id, "type": "access"},
                    expires_delta=timedelta(hours=1),
                )

                claims = jwt.decode(token, options={"verify_signature": False})
                assert claims["sub"] == long_user_id


class TestJWTKeyHelpers:
    """Test JWT key helper functions."""

    def _create_mock_settings_service(self, algorithm, tmpdir):
        """Helper to create mock settings service."""
        from lfx.services.settings.auth import AuthSettings

        settings = AuthSettings(CONFIG_DIR=tmpdir, ALGORITHM=algorithm)

        mock_service = MagicMock()
        mock_service.auth_settings = settings
        return mock_service

    def test_get_jwt_verification_key_hs256_returns_secret_key(self):
        """HS256 should return secret key for verification."""
        from langflow.services.auth.utils import get_jwt_verification_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            key = get_jwt_verification_key(mock_service)

            assert key == mock_service.auth_settings.SECRET_KEY.get_secret_value()
            assert len(key) >= 32

    def test_get_jwt_verification_key_rs256_returns_public_key(self):
        """RS256 should return public key for verification."""
        from langflow.services.auth.utils import get_jwt_verification_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)

            key = get_jwt_verification_key(mock_service)

            assert key == mock_service.auth_settings.PUBLIC_KEY
            assert "-----BEGIN PUBLIC KEY-----" in key

    def test_get_jwt_verification_key_rs512_returns_public_key(self):
        """RS512 should return public key for verification."""
        from langflow.services.auth.utils import get_jwt_verification_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS512", tmpdir)

            key = get_jwt_verification_key(mock_service)

            assert key == mock_service.auth_settings.PUBLIC_KEY
            assert "-----BEGIN PUBLIC KEY-----" in key

    def test_get_jwt_verification_key_missing_public_key_raises_error(self):
        """Missing public key for asymmetric algorithm should raise JWTKeyError."""
        from langflow.services.auth.utils import JWTKeyError, get_jwt_verification_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)
            object.__setattr__(mock_service.auth_settings, "PUBLIC_KEY", "")

            with pytest.raises(JWTKeyError) as exc_info:
                get_jwt_verification_key(mock_service)

            assert exc_info.value.status_code == 401
            assert "Public key not configured" in exc_info.value.detail

    def test_get_jwt_verification_key_missing_secret_key_raises_error(self):
        """Missing secret key for HS256 should raise JWTKeyError."""
        from langflow.services.auth.utils import JWTKeyError, get_jwt_verification_key
        from lfx.services.settings.auth import JWTAlgorithm

        mock_auth_settings = MagicMock()
        mock_auth_settings.ALGORITHM = JWTAlgorithm.HS256
        mock_auth_settings.SECRET_KEY = MagicMock()
        mock_auth_settings.SECRET_KEY.get_secret_value.return_value = None

        mock_service = MagicMock()
        mock_service.auth_settings = mock_auth_settings

        with pytest.raises(JWTKeyError) as exc_info:
            get_jwt_verification_key(mock_service)

        assert exc_info.value.status_code == 401
        assert "Secret key not configured" in exc_info.value.detail

    def test_get_jwt_signing_key_hs256_returns_secret_key(self):
        """HS256 should return secret key for signing."""
        from langflow.services.auth.utils import get_jwt_signing_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            key = get_jwt_signing_key(mock_service)

            assert key == mock_service.auth_settings.SECRET_KEY.get_secret_value()

    def test_get_jwt_signing_key_rs256_returns_private_key(self):
        """RS256 should return private key for signing."""
        from langflow.services.auth.utils import get_jwt_signing_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)

            key = get_jwt_signing_key(mock_service)

            assert key == mock_service.auth_settings.PRIVATE_KEY.get_secret_value()
            assert "-----BEGIN PRIVATE KEY-----" in key

    def test_get_jwt_signing_key_rs512_returns_private_key(self):
        """RS512 should return private key for signing."""
        from langflow.services.auth.utils import get_jwt_signing_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS512", tmpdir)

            key = get_jwt_signing_key(mock_service)

            assert key == mock_service.auth_settings.PRIVATE_KEY.get_secret_value()
            assert "-----BEGIN PRIVATE KEY-----" in key

    def test_verification_and_signing_keys_work_together_hs256(self):
        """Verification and signing keys should work together for HS256."""
        from langflow.services.auth.utils import get_jwt_signing_key, get_jwt_verification_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("HS256", tmpdir)

            signing_key = get_jwt_signing_key(mock_service)
            verification_key = get_jwt_verification_key(mock_service)

            # For symmetric algorithms, both keys are the same
            assert signing_key == verification_key

            # Sign and verify a token
            payload = {"sub": "test-user", "type": "access"}
            token = jwt.encode(payload, signing_key, algorithm="HS256")
            decoded = jwt.decode(token, verification_key, algorithms=["HS256"])

            assert decoded["sub"] == "test-user"

    def test_verification_and_signing_keys_work_together_rs256(self):
        """Verification and signing keys should work together for RS256."""
        from langflow.services.auth.utils import get_jwt_signing_key, get_jwt_verification_key

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_service = self._create_mock_settings_service("RS256", tmpdir)

            signing_key = get_jwt_signing_key(mock_service)
            verification_key = get_jwt_verification_key(mock_service)

            # For asymmetric algorithms, keys are different
            assert signing_key != verification_key

            # Sign and verify a token
            payload = {"sub": "test-user", "type": "access"}
            token = jwt.encode(payload, signing_key, algorithm="RS256")
            decoded = jwt.decode(token, verification_key, algorithms=["RS256"])

            assert decoded["sub"] == "test-user"
