"""Tests for Keycloak Authentication Utilities.

This module provides tests for the utility functions that handle Keycloak/OpenID
Connect authentication integration with Langflow, including token processing and
user creation/update from Keycloak data.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Response, status
from langflow.services.auth.constants import COOKIE_KEYCLOAK_REFRESH_TOKEN
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.user.model import User
from langflow.services.keycloak import utils
from sqlmodel.ext.asyncio.session import AsyncSession

# ----- Fixtures ----- #


@pytest.fixture(name="fixture_mock_keycloak_service")
def mock_keycloak_service() -> AsyncMock:
    """Create a mock KeycloakService with necessary attributes and methods."""
    mock_service = AsyncMock()
    mock_service.is_enabled = True
    mock_service.admin_role = "admin"

    # Mock settings
    mock_settings_service = MagicMock()
    mock_auth_settings = MagicMock()
    mock_auth_settings.REFRESH_SAME_SITE = "lax"
    mock_auth_settings.REFRESH_SECURE = True
    mock_auth_settings.REFRESH_TOKEN_EXPIRE_SECONDS = 3600
    mock_auth_settings.COOKIE_DOMAIN = None

    mock_settings_service.auth_settings = mock_auth_settings
    mock_service.settings_service = mock_settings_service

    # Mock token methods
    mock_service.get_token.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "token_type": "Bearer",
    }

    mock_service.decode_token.return_value = {
        "preferred_username": "test_user",
        "email": "test@example.com",
        "given_name": "Test",
        "family_name": "User",
        "nonce": "test_nonce",
        "resource_access": {"test_client": {"roles": ["user"]}},
    }

    mock_service.extract_roles = MagicMock(return_value=["user"])

    return mock_service


@pytest.fixture(name="fixture_mock_db_session")
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture(name="fixture_mock_response")
def mock_response() -> MagicMock:
    """Create a mock FastAPI Response object."""
    return MagicMock(spec=Response)


@pytest.fixture(name="fixture_mock_existing_user")
def mock_existing_user() -> User:
    """Create a mock existing user."""
    return User(
        id=1,
        username="test_user",
        email="test@example.com",
        password=get_password_hash("password"),
        is_superuser=False,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=False,
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ----- Test process_keycloak_login Function ----- #


@pytest.mark.asyncio
async def test_process_keycloak_login_success(
    fixture_mock_keycloak_service: AsyncMock,
    fixture_mock_db_session: AsyncMock,
    fixture_mock_response: MagicMock,
    fixture_mock_existing_user: User,
):
    """Test successful Keycloak login processing."""
    # Mock get_user_by_username to return an existing user
    with (
        patch(
            "langflow.services.keycloak.utils.get_user_by_username",
            return_value=fixture_mock_existing_user,
        ),
        patch(
            "langflow.services.keycloak.utils.update_user",
            return_value=fixture_mock_existing_user,
        ),
        patch(
            "langflow.services.keycloak.utils.create_and_set_user_tokens",
            return_value={"access_token": "langflow_token", "token_type": "bearer"},
        ),
    ):
        # Call the function
        result = await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

        # Verify the result
        assert result == {"access_token": "langflow_token", "token_type": "bearer"}

        # Verify token was retrieved from Keycloak
        fixture_mock_keycloak_service.get_token.assert_called_once_with("test_code", "http://localhost/callback")

        # Verify token was decoded
        fixture_mock_keycloak_service.decode_token.assert_called_once_with("test_access_token")

        # Verify cookie was set for refresh token
        fixture_mock_response.set_cookie.assert_called_once_with(
            COOKIE_KEYCLOAK_REFRESH_TOKEN,
            "test_refresh_token",
            httponly=True,
            samesite="lax",
            secure=True,
            expires=3600,
            domain=None,
        )


@pytest.mark.asyncio
async def test_process_keycloak_login_keycloak_disabled(
    fixture_mock_keycloak_service, fixture_mock_db_session, fixture_mock_response
):
    """Test login processing when Keycloak is disabled."""
    # Set Keycloak as disabled
    fixture_mock_keycloak_service.is_enabled = False

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert exc_info.value.detail == "Keycloak is disabled"


@pytest.mark.asyncio
async def test_process_keycloak_login_token_retrieval_failure(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_response: MagicMock
):
    """Test handling of token retrieval failure."""
    # Make get_token raise an exception
    fixture_mock_keycloak_service.get_token.side_effect = Exception("Token retrieval failed")

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Failed to get token from Keycloak" in exc_info.value.detail


@pytest.mark.asyncio
async def test_process_keycloak_login_empty_token_response(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_response: MagicMock
):
    """Test handling of empty token response."""
    # Make get_token return an empty dict
    fixture_mock_keycloak_service.get_token.return_value = {}

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Failed to get token from Keycloak: Empty response"


@pytest.mark.asyncio
async def test_process_keycloak_login_no_access_token(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_response: MagicMock
):
    """Test handling of missing access token in response."""
    # Make get_token return a dict without access_token
    fixture_mock_keycloak_service.get_token.return_value = {"refresh_token": "test_refresh_token"}

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "No access token found in Keycloak response"


@pytest.mark.asyncio
async def test_process_keycloak_login_token_decode_failure(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_response: MagicMock
):
    """Test handling of token decoding failure."""
    # Make decode_token raise an exception
    fixture_mock_keycloak_service.decode_token.side_effect = Exception("Token decoding failed")

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Failed to decode token" in exc_info.value.detail


@pytest.mark.asyncio
async def test_process_keycloak_login_nonce_mismatch(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_response: MagicMock
):
    """Test handling of nonce mismatch."""
    # Make decode_token return a dict with a different nonce
    fixture_mock_keycloak_service.decode_token.return_value = {
        "preferred_username": "test_user",
        "email": "test@example.com",
        "nonce": "different_nonce",
    }

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Nonce mismatch"


@pytest.mark.asyncio
async def test_process_keycloak_login_missing_nonce(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_response: MagicMock
):
    """Test handling of missing nonce in token."""
    # Make decode_token return a dict without a nonce
    fixture_mock_keycloak_service.decode_token.return_value = {
        "preferred_username": "test_user",
        "email": "test@example.com",
    }

    # Expect HTTPException
    with pytest.raises(HTTPException) as exc_info:
        await utils.process_keycloak_login(
            code="test_code",
            client_nonce="test_nonce",
            redirect_uri="http://localhost/callback",
            response=fixture_mock_response,
            db=fixture_mock_db_session,
            keycloak_service=fixture_mock_keycloak_service,
        )

    # Verify exception details
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Nonce mismatch"


# ----- Test get_or_create_user Function ----- #


@pytest.mark.asyncio
async def test_get_or_create_user_existing_user(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_existing_user: User
):
    """Test retrieving an existing user."""
    # Mock token data
    token_data = {
        "preferred_username": "test_user",
        "email": "updated@example.com",
        "given_name": "Test",
        "family_name": "User",
    }

    # Mock get_user_by_username to return an existing user
    with (
        patch(
            "langflow.services.keycloak.utils.get_user_by_username", return_value=fixture_mock_existing_user
        ) as mock_get_user,
        patch("langflow.services.keycloak.utils.update_user") as fixture_mock_update_user,
    ):
        # Call the function
        result = await utils.get_or_create_user(
            db=fixture_mock_db_session, decoded_token=token_data, keycloak_service=fixture_mock_keycloak_service
        )

        # Verify user was retrieved
        mock_get_user.assert_called_once_with(fixture_mock_db_session, "test_user", include_deleted=True)

        # Verify user was updated
        fixture_mock_update_user.assert_called_once()
        user_update = fixture_mock_update_user.call_args[0][1]
        assert user_update.email == "updated@example.com"
        assert user_update.is_keycloak_user is True
        assert user_update.is_active is True

        # Verify result
        assert result == fixture_mock_existing_user


@pytest.mark.asyncio
async def test_get_or_create_user_deleted_user(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock
):
    """Test handling of a deleted user."""
    # Create a deleted user
    deleted_user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        password=get_password_hash("password"),
        is_superuser=False,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=True,  # User is deleted
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Mock token data
    token_data = {"preferred_username": "test_user", "email": "test@example.com"}

    # Mock get_user_by_username to return a deleted user
    with patch("langflow.services.keycloak.utils.get_user_by_username", return_value=deleted_user):
        # Expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await utils.get_or_create_user(
                db=fixture_mock_db_session, decoded_token=token_data, keycloak_service=fixture_mock_keycloak_service
            )

        # Verify exception details
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert exc_info.value.detail == "User was removed"


@pytest.mark.asyncio
async def test_get_or_create_user_new_user(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock
):
    """Test creating a new user when one doesn't exist."""
    # Mock token data
    token_data = {
        "preferred_username": "new_user",
        "email": "new@example.com",
        "given_name": "New",
        "family_name": "User",
    }

    # Mock roles that include admin
    fixture_mock_keycloak_service.extract_roles.return_value = ["user", "admin"]

    # Mock get_user_by_username to return None (user not found)
    # and create_keycloak_user to return a new user
    new_user = User(
        id=2,
        username="new_user",
        email="new@example.com",
        password="hashed_password",  # noqa: S106
        is_superuser=True,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=False,
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("langflow.services.keycloak.utils.get_user_by_username", return_value=None),
        patch("langflow.services.keycloak.utils.create_keycloak_user", return_value=new_user) as mock_create_user,
    ):
        # Call the function
        result = await utils.get_or_create_user(
            db=fixture_mock_db_session, decoded_token=token_data, keycloak_service=fixture_mock_keycloak_service
        )

        # Verify new user was created
        mock_create_user.assert_called_once_with(fixture_mock_db_session, "new_user", "new@example.com", True)  # noqa: FBT003

        # Verify result
        assert result == new_user


@pytest.mark.asyncio
async def test_get_or_create_user_with_admin_role(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock, fixture_mock_existing_user: User
):
    """Test retrieving a user with admin role from Keycloak."""
    # Mock token data
    token_data = {"preferred_username": "admin_user", "email": "admin@example.com"}

    # Mock roles that include admin
    fixture_mock_keycloak_service.extract_roles.return_value = ["user", "admin"]

    # Mock get_user_by_username to return an existing user
    with (
        patch("langflow.services.keycloak.utils.get_user_by_username", return_value=fixture_mock_existing_user),
        patch("langflow.services.keycloak.utils.update_user") as mock_update_user,
    ):
        # Call the function
        await utils.get_or_create_user(
            db=fixture_mock_db_session, decoded_token=token_data, keycloak_service=fixture_mock_keycloak_service
        )

        # Verify user was updated with admin role
        mock_update_user.assert_called_once()
        user_update = mock_update_user.call_args[0][1]
        assert user_update.is_superuser is True


@pytest.mark.asyncio
async def test_get_or_create_user_with_generated_username(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock
):
    """Test username generation when preferred_username and email are missing."""
    # Mock token data with only names, no username or email
    token_data = {"given_name": "Test", "family_name": "User"}

    # Mock get_user_by_username to return None (user not found)
    # and create_keycloak_user to return a new user
    new_user = User(
        id=3,
        username="test.user",
        email=None,
        password="hashed_password",  # noqa: S106
        is_superuser=False,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=False,
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("langflow.services.keycloak.utils.get_user_by_username", return_value=None),
        patch("langflow.services.keycloak.utils.create_keycloak_user", return_value=new_user) as mock_create_user,
    ):
        # Call the function
        result = await utils.get_or_create_user(
            db=fixture_mock_db_session, decoded_token=token_data, keycloak_service=fixture_mock_keycloak_service
        )

        # Verify new user was created with generated username
        mock_create_user.assert_called_once()
        assert mock_create_user.call_args[0][0] == fixture_mock_db_session
        assert mock_create_user.call_args[0][1] == "test.user"  # Generated from names

        # Verify result
        assert result == new_user


@pytest.mark.asyncio
async def test_get_or_create_user_with_random_username(
    fixture_mock_keycloak_service: AsyncMock, fixture_mock_db_session: AsyncMock
):
    """Test random username generation when no identifying information is available."""
    # Mock token data with no identifying information
    token_data: dict[str, Any] = {}

    # Mock get_user_by_username to return None (user not found)
    # and create_keycloak_user to return a new user
    new_user = User(
        id=4,
        username="user_12345678",  # This would be random in reality
        email=None,
        password="hashed_password",  # noqa: S106
        is_superuser=False,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=False,
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("langflow.services.keycloak.utils.get_user_by_username", return_value=None),
        patch("langflow.services.keycloak.utils.create_keycloak_user", return_value=new_user) as mock_create_user,
        patch("uuid.uuid4") as mock_uuid,
    ):
        # Mock UUID to return a predictable value
        mock_uuid.return_value.hex = "1234567890abcdef"

        # Call the function
        result = await utils.get_or_create_user(
            db=fixture_mock_db_session, decoded_token=token_data, keycloak_service=fixture_mock_keycloak_service
        )

        # Verify new user was created with random username
        mock_create_user.assert_called_once()
        assert mock_create_user.call_args[0][0] == fixture_mock_db_session
        assert mock_create_user.call_args[0][1].startswith("user_")

        # Verify result
        assert result == new_user


# ----- Test create_keycloak_user Function ----- #


@pytest.mark.asyncio
async def test_create_keycloak_user(fixture_mock_db_session: AsyncMock):
    """Test creating a new user from Keycloak data."""
    # Mock the create_new_user function
    new_user = User(
        id=5,
        username="keycloak_user",
        email="keycloak@example.com",
        password="hashed_password",  # noqa: S106
        is_superuser=True,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=False,
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    with (
        patch("langflow.services.keycloak.utils.create_new_user", return_value=new_user) as mock_create_new_user,
        patch("langflow.services.keycloak.utils.get_password_hash", return_value="hashed_password"),
    ):
        # Call the function
        result = await utils.create_keycloak_user(
            db=fixture_mock_db_session, username="keycloak_user", email="keycloak@example.com", is_admin=True
        )

        # Verify user was created with correct attributes
        mock_create_new_user.assert_called_once()
        created_user = mock_create_new_user.call_args[0][1]
        assert created_user.username == "keycloak_user"
        assert created_user.email == "keycloak@example.com"
        assert created_user.is_superuser is True
        assert created_user.is_active is True
        assert created_user.is_keycloak_user is True
        assert created_user.is_deleted is False

        # Verify result
        assert result == new_user


@pytest.mark.asyncio
async def test_create_keycloak_user_exception(fixture_mock_db_session: AsyncMock):
    """Test handling of exceptions during user creation."""
    # Mock an exception during User creation
    with patch("langflow.services.keycloak.utils.User", side_effect=Exception("Database error")):
        # Expect HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await utils.create_keycloak_user(
                db=fixture_mock_db_session, username="error_user", email="error@example.com", is_admin=False
            )

        # Verify exception details
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert exc_info.value.detail == "Failed to create user in database"


# ----- Test create_new_user Function ----- #


@pytest.mark.asyncio
async def test_create_new_user(fixture_mock_db_session: AsyncMock):
    """Test adding a new user to the database."""
    # Create a user object
    user = User(
        username="new_db_user",
        email="new_db@example.com",
        password="hashed_password",  # noqa: S106
        is_superuser=False,
        is_active=True,
        is_keycloak_user=True,
        is_deleted=False,
        create_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    # Call the function
    result = await utils.create_new_user(fixture_mock_db_session, user)

    # Verify database operations
    fixture_mock_db_session.add.assert_called_once_with(user)
    fixture_mock_db_session.commit.assert_called_once()
    fixture_mock_db_session.refresh.assert_called_once_with(user)

    # Verify result
    assert result == user
