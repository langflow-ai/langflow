"""Tests for API key validation with different sources (db and env).

This module tests the check_key function behavior when:
- API_KEY_SOURCE='db' (default): Validates against database-stored API keys
- API_KEY_SOURCE='env': Validates against LANGFLOW_API_KEY environment variable
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.crud import (
    _check_key_from_db,
    _check_key_from_env,
    check_key,
)
from langflow.services.database.models.user.model import User


@pytest.fixture
def mock_user():
    """Create a mock active user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "testuser"
    user.is_active = True
    user.is_superuser = False
    return user


@pytest.fixture
def mock_superuser():
    """Create a mock active superuser."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "langflow"
    user.is_active = True
    user.is_superuser = True
    return user


@pytest.fixture
def mock_inactive_user():
    """Create a mock inactive user."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.username = "inactive"
    user.is_active = False
    user.is_superuser = False
    return user


@pytest.fixture
def mock_session():
    """Create a mock async database session."""
    return AsyncMock()


@pytest.fixture
def mock_settings_service_db():
    """Create a mock settings service with API_KEY_SOURCE='db'."""
    settings_service = MagicMock()
    settings_service.auth_settings.API_KEY_SOURCE = "db"
    settings_service.auth_settings.SUPERUSER = "langflow"
    settings_service.settings.disable_track_apikey_usage = False
    return settings_service


@pytest.fixture
def mock_settings_service_env():
    """Create a mock settings service with API_KEY_SOURCE='env'."""
    settings_service = MagicMock()
    settings_service.auth_settings.API_KEY_SOURCE = "env"
    settings_service.auth_settings.SUPERUSER = "langflow"
    settings_service.settings.disable_track_apikey_usage = False
    return settings_service


# ============================================================================
# check_key routing tests
# ============================================================================


class TestCheckKeyRouting:
    """Tests for check_key routing based on API_KEY_SOURCE setting."""

    @pytest.mark.asyncio
    async def test_check_key_routes_to_db_by_default(self, mock_session, mock_settings_service_db):
        """check_key should route to _check_key_from_db when API_KEY_SOURCE='db'."""
        with (
            patch(
                "langflow.services.database.models.api_key.crud.get_settings_service",
                return_value=mock_settings_service_db,
            ),
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_db",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_env",
                new_callable=AsyncMock,
            ) as mock_env_check,
        ):
            mock_db_check.return_value = None

            await check_key(mock_session, "sk-test-key")

            mock_db_check.assert_called_once()
            mock_env_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_check_key_routes_to_env_when_configured_and_succeeds(self, mock_session, mock_settings_service_env):
        """check_key should route to _check_key_from_env when API_KEY_SOURCE='env' and env succeeds."""
        mock_user = MagicMock(spec=User)
        with (
            patch(
                "langflow.services.database.models.api_key.crud.get_settings_service",
                return_value=mock_settings_service_env,
            ),
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_db",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_env",
                new_callable=AsyncMock,
            ) as mock_env_check,
        ):
            mock_env_check.return_value = mock_user

            result = await check_key(mock_session, "sk-test-key")

            mock_env_check.assert_called_once()
            mock_db_check.assert_not_called()
            assert result == mock_user

    @pytest.mark.asyncio
    async def test_check_key_falls_back_to_db_when_env_fails(self, mock_session, mock_settings_service_env):
        """check_key should fallback to _check_key_from_db when API_KEY_SOURCE='env' but env validation fails."""
        mock_user = MagicMock(spec=User)
        with (
            patch(
                "langflow.services.database.models.api_key.crud.get_settings_service",
                return_value=mock_settings_service_env,
            ),
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_db",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_env",
                new_callable=AsyncMock,
            ) as mock_env_check,
        ):
            mock_env_check.return_value = None  # env validation fails
            mock_db_check.return_value = mock_user  # db has the key

            result = await check_key(mock_session, "sk-test-key")

            mock_env_check.assert_called_once()
            mock_db_check.assert_called_once()  # Should fallback to db
            assert result == mock_user

    @pytest.mark.asyncio
    async def test_check_key_returns_none_when_both_env_and_db_fail(self, mock_session, mock_settings_service_env):
        """check_key should return None when both env and db validation fail."""
        with (
            patch(
                "langflow.services.database.models.api_key.crud.get_settings_service",
                return_value=mock_settings_service_env,
            ),
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_db",
                new_callable=AsyncMock,
            ) as mock_db_check,
            patch(
                "langflow.services.database.models.api_key.crud._check_key_from_env",
                new_callable=AsyncMock,
            ) as mock_env_check,
        ):
            mock_env_check.return_value = None  # env validation fails
            mock_db_check.return_value = None  # db validation also fails

            result = await check_key(mock_session, "sk-test-key")

            mock_env_check.assert_called_once()
            mock_db_check.assert_called_once()
            assert result is None


# ============================================================================
# _check_key_from_db tests
# ============================================================================


class TestCheckKeyFromDb:
    """Tests for database-based API key validation."""

    @pytest.mark.asyncio
    async def test_valid_key_returns_user(self, mock_session, mock_user, mock_settings_service_db):
        """Valid API key should return the associated user."""
        api_key_id = uuid4()
        user_id = mock_user.id

        mock_result = MagicMock()
        mock_result.all.return_value = [(api_key_id, "sk-valid-key", user_id)]

        mock_session.exec = AsyncMock(return_value=mock_result)

        mock_session.get = AsyncMock(return_value=mock_user)

        result = await _check_key_from_db(mock_session, "sk-valid-key", mock_settings_service_db)

        assert result == mock_user
        mock_session.get.assert_called_once_with(User, user_id)

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self, mock_session, mock_settings_service_db):
        """Invalid API key should return None."""
        mock_result = MagicMock()
        mock_result.all.return_value = []  # No keys in DB
        mock_session.exec = AsyncMock(return_value=mock_result)

        result = await _check_key_from_db(mock_session, "sk-invalid-key", mock_settings_service_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_usage_tracking_increments(self, mock_session, mock_user, mock_settings_service_db):
        """API key usage should be tracked when not disabled."""
        api_key_id = uuid4()
        user_id = mock_user.id

        mock_result = MagicMock()
        mock_result.all.return_value = [(api_key_id, "sk-valid-key", user_id)]
        mock_session.exec = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=mock_user)

        await _check_key_from_db(mock_session, "sk-valid-key", mock_settings_service_db)

        # Verify exec was called twice (select + update)
        assert mock_session.exec.call_count == 2

    @pytest.mark.asyncio
    async def test_usage_tracking_disabled(self, mock_session, mock_user, mock_settings_service_db):
        """API key usage should not be tracked when disabled."""
        mock_settings_service_db.settings.disable_track_apikey_usage = True

        api_key_id = uuid4()
        user_id = mock_user.id

        mock_result = MagicMock()
        mock_result.all.return_value = [(api_key_id, "sk-valid-key", user_id)]
        mock_session.exec = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=mock_user)

        await _check_key_from_db(mock_session, "sk-valid-key", mock_settings_service_db)

        # Verify exec was called only once (select, no update)
        assert mock_session.exec.call_count == 1

    @pytest.mark.asyncio
    async def test_empty_key_returns_none(self, mock_session, mock_settings_service_db):
        """Empty API key should return None."""
        mock_result = MagicMock()
        mock_result.all.return_value = []  # No keys match
        mock_session.exec = AsyncMock(return_value=mock_result)

        result = await _check_key_from_db(mock_session, "", mock_settings_service_db)

        assert result is None


# ============================================================================
# _check_key_from_env tests
# ============================================================================


class TestCheckKeyFromEnv:
    """Tests for environment variable-based API key validation."""

    @pytest.mark.asyncio
    async def test_valid_key_returns_superuser(
        self, mock_session, mock_superuser, mock_settings_service_env, monkeypatch
    ):
        """Valid API key matching env var should return the superuser."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-test-env-key")

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = mock_superuser

            result = await _check_key_from_env(mock_session, "sk-test-env-key", mock_settings_service_env)

            assert result == mock_superuser
            mock_get_user.assert_called_once_with(mock_session, "langflow")

    @pytest.mark.asyncio
    async def test_invalid_key_returns_none(self, mock_session, mock_settings_service_env, monkeypatch):
        """Invalid API key not matching env var should return None."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-test-env-key")

        result = await _check_key_from_env(mock_session, "sk-wrong-key", mock_settings_service_env)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_env_api_key_configured_returns_none(self, mock_session, mock_settings_service_env, monkeypatch):
        """When LANGFLOW_API_KEY is not set, should return None."""
        monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)

        result = await _check_key_from_env(mock_session, "sk-any-key", mock_settings_service_env)

        assert result is None

    @pytest.mark.asyncio
    async def test_empty_env_api_key_returns_none(self, mock_session, mock_settings_service_env, monkeypatch):
        """When LANGFLOW_API_KEY is empty string, should return None."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "")

        result = await _check_key_from_env(mock_session, "sk-any-key", mock_settings_service_env)

        assert result is None

    @pytest.mark.asyncio
    async def test_superuser_not_found_returns_none(self, mock_session, mock_settings_service_env, monkeypatch):
        """When superuser doesn't exist in database, should return None."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-test-env-key")

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = None

            result = await _check_key_from_env(mock_session, "sk-test-env-key", mock_settings_service_env)

            assert result is None

    @pytest.mark.asyncio
    async def test_superuser_inactive_returns_none(
        self, mock_session, mock_inactive_user, mock_settings_service_env, monkeypatch
    ):
        """When superuser is inactive, should return None."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-test-env-key")

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = mock_inactive_user

            result = await _check_key_from_env(mock_session, "sk-test-env-key", mock_settings_service_env)

            assert result is None

    @pytest.mark.asyncio
    async def test_case_sensitive_key_comparison(self, mock_session, mock_settings_service_env, monkeypatch):
        """API key comparison should be case-sensitive."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-Test-Key")

        # Different case should not match
        result = await _check_key_from_env(mock_session, "sk-test-key", mock_settings_service_env)
        assert result is None

        result = await _check_key_from_env(mock_session, "SK-TEST-KEY", mock_settings_service_env)
        assert result is None

    @pytest.mark.asyncio
    async def test_whitespace_in_key_not_trimmed(self, mock_session, mock_settings_service_env, monkeypatch):
        """Whitespace in API key should not be trimmed."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-test-key")

        # Key with leading/trailing whitespace should not match
        result = await _check_key_from_env(mock_session, " sk-test-key", mock_settings_service_env)
        assert result is None

        result = await _check_key_from_env(mock_session, "sk-test-key ", mock_settings_service_env)
        assert result is None

    @pytest.mark.asyncio
    async def test_special_characters_in_key(
        self, mock_session, mock_superuser, mock_settings_service_env, monkeypatch
    ):
        """API key with special characters should work correctly."""
        special_key = "sk-test!@#$%^&*()_+-=[]{}|;':\",./<>?"
        monkeypatch.setenv("LANGFLOW_API_KEY", special_key)

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = mock_superuser

            result = await _check_key_from_env(mock_session, special_key, mock_settings_service_env)

            assert result == mock_superuser

    @pytest.mark.asyncio
    async def test_unicode_in_key(self, mock_session, mock_superuser, mock_settings_service_env, monkeypatch):
        """API key with unicode characters should work correctly."""
        unicode_key = "sk-тест-キー-密钥"
        monkeypatch.setenv("LANGFLOW_API_KEY", unicode_key)

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = mock_superuser

            result = await _check_key_from_env(mock_session, unicode_key, mock_settings_service_env)

            assert result == mock_superuser

    @pytest.mark.asyncio
    async def test_very_long_key(self, mock_session, mock_superuser, mock_settings_service_env, monkeypatch):
        """Very long API key should work correctly."""
        long_key = "sk-" + "a" * 1000
        monkeypatch.setenv("LANGFLOW_API_KEY", long_key)

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = mock_superuser

            result = await _check_key_from_env(mock_session, long_key, mock_settings_service_env)

            assert result == mock_superuser


# ============================================================================
# Edge cases and error handling
# ============================================================================


class TestCheckKeyEdgeCases:
    """Edge cases and error handling tests."""

    @pytest.mark.asyncio
    async def test_none_api_key_raises_or_returns_none(self, mock_session, mock_settings_service_db):
        """Passing None as API key should be handled gracefully."""
        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_session.exec.return_value = mock_result

        # Should not raise, just return None
        result = await _check_key_from_db(mock_session, None, mock_settings_service_db)
        assert result is None

    @pytest.mark.asyncio
    async def test_custom_superuser_name(self, mock_session, mock_superuser, mock_settings_service_env, monkeypatch):
        """Should use custom superuser name from settings."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-test-env-key")
        mock_settings_service_env.auth_settings.SUPERUSER = "admin"
        mock_superuser.username = "admin"

        with patch(
            "langflow.services.database.models.user.crud.get_user_by_username",
            new_callable=AsyncMock,
        ) as mock_get_user:
            mock_get_user.return_value = mock_superuser

            result = await _check_key_from_env(mock_session, "sk-test-env-key", mock_settings_service_env)

            mock_get_user.assert_called_once_with(mock_session, "admin")
            assert result == mock_superuser


# ============================================================================
# Integration-style tests (with real settings mocking)
# ============================================================================


class TestCheckKeyIntegration:
    """Integration-style tests for the complete check_key flow."""

    @pytest.mark.asyncio
    async def test_full_flow_db_mode_valid_key(self, mock_session, mock_user):
        """Full flow test: db mode with valid key."""
        api_key_id = uuid4()
        user_id = mock_user.id

        mock_result = MagicMock()
        mock_result.all.return_value = [(api_key_id, "sk-valid-key", user_id)]
        mock_session.exec = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=mock_user)

        mock_settings = MagicMock()
        mock_settings.auth_settings.API_KEY_SOURCE = "db"
        mock_settings.settings.disable_track_apikey_usage = False

        with patch(
            "langflow.services.database.models.api_key.crud.get_settings_service",
            return_value=mock_settings,
        ):
            result = await check_key(mock_session, "sk-valid-key")

            assert result == mock_user
            mock_session.get.assert_called_once_with(User, user_id)

    @pytest.mark.asyncio
    async def test_full_flow_env_mode_valid_key(self, mock_session, mock_superuser, monkeypatch):
        """Full flow test: env mode with valid key."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-env-secret")

        mock_settings = MagicMock()
        mock_settings.auth_settings.API_KEY_SOURCE = "env"
        mock_settings.auth_settings.SUPERUSER = "langflow"

        with (
            patch(
                "langflow.services.database.models.api_key.crud.get_settings_service",
                return_value=mock_settings,
            ),
            patch(
                "langflow.services.database.models.user.crud.get_user_by_username",
                new_callable=AsyncMock,
            ) as mock_get_user,
        ):
            mock_get_user.return_value = mock_superuser

            result = await check_key(mock_session, "sk-env-secret")

            assert result == mock_superuser

    @pytest.mark.asyncio
    async def test_full_flow_env_mode_invalid_key_falls_back_to_db(self, mock_session, mock_user, monkeypatch):
        """Full flow test: env mode with invalid key falls back to db."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-correct-key")

        # Setup mock for db fallback
        api_key_id = uuid4()
        user_id = mock_user.id

        monkeypatch.setattr(
            "langflow.services.database.models.api_key.crud.auth_utils.decrypt_api_key",
            lambda v, _settings_service=None: "sk-wrong-key" if v == "sk-wrong-key" else v,
        )

        mock_result = MagicMock()
        mock_result.all.return_value = [(api_key_id, "sk-wrong-key", user_id)]
        mock_session.exec = AsyncMock(return_value=mock_result)
        mock_session.get = AsyncMock(return_value=mock_user)

        mock_settings = MagicMock()
        mock_settings.auth_settings.API_KEY_SOURCE = "env"
        mock_settings.auth_settings.SUPERUSER = "langflow"
        mock_settings.settings.disable_track_apikey_usage = False

        with patch(
            "langflow.services.database.models.api_key.crud.get_settings_service",
            return_value=mock_settings,
        ):
            # Key doesn't match env, but exists in db
            result = await check_key(mock_session, "sk-wrong-key")

            # Should return user from db fallback
            assert result == mock_user

    @pytest.mark.asyncio
    async def test_full_flow_env_mode_invalid_key_not_in_db(self, mock_session, monkeypatch):
        """Full flow test: env mode with invalid key that's also not in db returns None."""
        monkeypatch.setenv("LANGFLOW_API_KEY", "sk-correct-key")

        # Setup mock for db - key not found
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.exec = AsyncMock(return_value=mock_result)

        mock_settings = MagicMock()
        mock_settings.auth_settings.API_KEY_SOURCE = "env"
        mock_settings.auth_settings.SUPERUSER = "langflow"
        mock_settings.settings.disable_track_apikey_usage = False

        with patch(
            "langflow.services.database.models.api_key.crud.get_settings_service",
            return_value=mock_settings,
        ):
            # Key doesn't match env AND not in db
            result = await check_key(mock_session, "sk-wrong-key")

            # Should return None since both failed
            assert result is None
