import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from langflow.services.auth.utils import get_current_user
from langflow.services.database.models.user.model import User, UserRead


@pytest.fixture
def mock_db():
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_user():
    now = datetime.now(timezone.utc)
    return User(
        id=uuid4(),
        username="langflowrocks",
        password="senhasecreta",
        is_active=True,
        is_superuser=False,
        last_login_at=now,
        profile_image=None,
        store_api_key=None,
        create_at=now,
        updated_at=now,
        optins=None,
    )


@pytest.fixture
def mock_user_read():
    now = datetime.now(timezone.utc)
    return UserRead(
        id=uuid4(),
        username="langflowrocks",
        is_active=True,
        is_superuser=False,
        last_login_at=now,
        profile_image=None,
        store_api_key=None,
        create_at=now,
        updated_at=now,
        optins=None,
    )


class TestGetCurrentUser:
    """Test cases for get_current_user function."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_jwt_returns_user(
        self, mock_db, mock_user
    ):
        """Test that valid JWT token returns User object."""
        token = "valid.jwt.token"
        query_param = None
        header_param = None

        with patch(
            "langflow.services.auth.utils.get_current_user_by_jwt"
        ) as mock_jwt_auth:
            mock_jwt_auth.return_value = mock_user

            result = await get_current_user(token, query_param, header_param, mock_db)

            assert isinstance(result, User)
            assert result == mock_user
            mock_jwt_auth.assert_called_once_with(token, mock_db)

    # Run this to test the new type hint as per LFOSS-1227
    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_api_key_returns_user_read(
        self, mock_db, mock_user_read
    ):
        """Test that valid API key returns UserRead object."""
        token = None
        query_param = "valid-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.return_value = mock_user_read

            result = await get_current_user(token, query_param, header_param, mock_db)

            assert isinstance(result, UserRead)
            assert result == mock_user_read
            mock_api_key_auth.assert_called_once_with(query_param, header_param)

    @pytest.mark.asyncio
    async def test_get_current_user_with_api_key_in_header_returns_user_read(
        self, mock_db, mock_user_read
    ):
        """Test that valid API key in header returns UserRead object."""
        token = None
        query_param = None
        header_param = "valid-api-key-header"

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.return_value = mock_user_read

            result = await get_current_user(token, query_param, header_param, mock_db)

            assert isinstance(result, UserRead)
            assert result == mock_user_read
            mock_api_key_auth.assert_called_once_with(query_param, header_param)

    @pytest.mark.asyncio
    async def test_get_current_user_jwt_takes_precedence_over_api_key(
        self, mock_db, mock_user, mock_user_read
    ):
        """Test that JWT token takes precedence over API key when both are provided."""
        token = "valid.jwt.token"
        query_param = "valid-api-key"
        header_param = "valid-api-key-header"

        with (
            patch(
                "langflow.services.auth.utils.get_current_user_by_jwt"
            ) as mock_jwt_auth,
            patch("langflow.services.auth.utils.api_key_security") as mock_api_key_auth,
        ):
            mock_jwt_auth.return_value = mock_user
            mock_api_key_auth.return_value = mock_user_read

            result = await get_current_user(token, query_param, header_param, mock_db)

            assert isinstance(result, User)
            assert result == mock_user
            mock_jwt_auth.assert_called_once_with(token, mock_db)
            mock_api_key_auth.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_jwt_propagates_error(self, mock_db):
        """Test that invalid JWT token propagates the JWT error."""
        token = "invalid.jwt.token"
        query_param = "valid-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.get_current_user_by_jwt"
        ) as mock_jwt_auth:
            mock_jwt_auth.side_effect = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            )

            # JWT exception should be propagated, not caught
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid token" in exc_info.value.detail
            mock_jwt_auth.assert_called_once_with(token, mock_db)

    @pytest.mark.asyncio
    async def test_get_current_user_with_no_credentials_raises_forbidden(self, mock_db):
        """Test that no credentials raises 403 Forbidden."""
        token = None
        query_param = None
        header_param = None

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Invalid or missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_api_key_raises_forbidden(
        self, mock_db
    ):
        """Test that invalid API key raises 403 Forbidden."""
        token = None
        query_param = "invalid-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.return_value = None

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Invalid or missing API key" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_api_key_security_raises_exception(self, mock_db):
        """Test that api_key_security exceptions are propagated."""
        token = None
        query_param = "some-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.side_effect = HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key validation failed",
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "API key validation failed" in exc_info.value.detail

    # Run this to test the new type hint as per LFOSS-1227
    @pytest.mark.asyncio
    async def test_get_current_user_empty_string_token_uses_api_key(
        self, mock_db, mock_user_read
    ):
        """Test that empty string token falls back to API key authentication."""
        token = ""
        query_param = "valid-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.return_value = mock_user_read

            result = await get_current_user(token, query_param, header_param, mock_db)

            assert isinstance(result, UserRead)
            assert result == mock_user_read
            mock_api_key_auth.assert_called_once_with(query_param, header_param)

    @pytest.mark.asyncio
    async def test_get_current_user_whitespace_token_causes_jwt_error(self, mock_db):
        """Test that whitespace-only token causes JWT validation error."""
        token = "   "
        query_param = "valid-api-key"
        header_param = None

        # Whitespace token will be treated as a JWT token and fail validation
        with patch(
            "langflow.services.auth.utils.get_current_user_by_jwt"
        ) as mock_jwt_auth:
            # The JWT library will raise a ValueError for malformed tokens
            mock_jwt_auth.side_effect = ValueError(
                "not enough values to unpack (expected 2, got 1)"
            )

            with pytest.raises(ValueError) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert "not enough values to unpack" in str(exc_info.value)
            mock_jwt_auth.assert_called_once_with(token, mock_db)

    # Run this to test the new type hint as per LFOSS-1227
    @pytest.mark.asyncio
    async def test_get_current_user_both_api_key_params_provided(
        self, mock_db, mock_user_read
    ):
        """Test that when both query and header API keys are provided, both are passed to api_key_security."""
        token = None
        query_param = "query-api-key"
        header_param = "header-api-key"

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.return_value = mock_user_read

            result = await get_current_user(token, query_param, header_param, mock_db)

            assert isinstance(result, UserRead)
            assert result == mock_user_read
            mock_api_key_auth.assert_called_once_with(query_param, header_param)

    @pytest.mark.asyncio
    async def test_get_current_user_jwt_server_error_propagated(self, mock_db):
        """Test that JWT server errors are propagated."""
        token = "some.jwt.token"
        query_param = "valid-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.get_current_user_by_jwt"
        ) as mock_jwt_auth:
            mock_jwt_auth.side_effect = HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database connection failed",
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database connection failed" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_api_key_server_error_propagated(self, mock_db):
        """Test that API key server errors are propagated."""
        token = None
        query_param = "some-api-key"
        header_param = None

        with patch(
            "langflow.services.auth.utils.api_key_security"
        ) as mock_api_key_auth:
            mock_api_key_auth.side_effect = HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="API key service unavailable",
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "API key service unavailable" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_jwt_token_error(self, mock_db):
        """Test that malformed JWT tokens cause appropriate errors."""
        token = "not.a.valid.jwt.format.token"
        query_param = None
        header_param = None

        with patch(
            "langflow.services.auth.utils.get_current_user_by_jwt"
        ) as mock_jwt_auth:
            # Simulate JWT library error for malformed token
            mock_jwt_auth.side_effect = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT format"
            )

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(token, query_param, header_param, mock_db)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid JWT format" in exc_info.value.detail
            mock_jwt_auth.assert_called_once_with(token, mock_db)
