import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langflow.services.auth.utils import create_super_user
from langflow.services.database.models.user.model import User
from langflow.services.utils import teardown_superuser
from sqlalchemy.exc import IntegrityError

from lfx.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
)

# @patch("langflow.services.deps.get_session")
# @patch("langflow.services.utils.create_super_user")
# @patch("langflow.services.deps.get_settings_service")
# # @patch("langflow.services.utils.verify_password")
# def test_setup_superuser(
#     mock_get_session, mock_create_super_user, mock_get_settings_service
# ):
#     # Test when AUTO_LOGIN is True
#     calls = []
#     mock_settings_service = Mock()
#     mock_settings_service.auth_settings.AUTO_LOGIN = True
#     mock_settings_service.auth_settings.SUPERUSER = DEFAULT_SUPERUSER
#     mock_settings_service.auth_settings.SUPERUSER_PASSWORD = DEFAULT_SUPERUSER_PASSWORD
#     mock_get_settings_service.return_value = mock_settings_service
#     mock_session = Mock()
#     mock_session.query.return_value.filter.return_value.first.return_value = (
#         mock_session
#     )
#     # return value of get_session is a generator
#     mock_get_session.return_value = iter([mock_session, mock_session, mock_session])
#     setup_superuser(mock_settings_service, mock_session)
#     mock_session.query.assert_called_once_with(User)
#     # Set return value of filter to be None
#     mock_session.query.return_value.filter.return_value.first.return_value = None
#     actual_expr = mock_session.query.return_value.filter.call_args[0][0]
#     expected_expr = User.username == DEFAULT_SUPERUSER

#     assert str(actual_expr) == str(expected_expr)
#     create_call = call(
#         db=mock_session, username=DEFAULT_SUPERUSER, password=DEFAULT_SUPERUSER_PASSWORD
#     )
#     calls.append(create_call)
#     # mock_create_super_user.assert_has_calls(calls)
#     assert 1 == mock_create_super_user.call_count

#     def reset_mock_credentials():
#         mock_settings_service.auth_settings.SUPERUSER = DEFAULT_SUPERUSER
#         mock_settings_service.auth_settings.SUPERUSER_PASSWORD = (
#             DEFAULT_SUPERUSER_PASSWORD
#         )

#     ADMIN_USER_NAME = "admin_user"
#     # Test when username and password are default
#     mock_settings_service.auth_settings = Mock()
#     mock_settings_service.auth_settings.AUTO_LOGIN = False
#     mock_settings_service.auth_settings.SUPERUSER = ADMIN_USER_NAME
#     mock_settings_service.auth_settings.SUPERUSER_PASSWORD = "password"
#     mock_settings_service.auth_settings.reset_credentials = Mock(
#         side_effect=reset_mock_credentials
#     )

#     mock_get_settings_service.return_value = mock_settings_service

#     setup_superuser(mock_settings_service, mock_session)
#     mock_session.query.assert_called_with(User)
#     actual_expr = mock_session.query.return_value.filter.call_args[0][0]
#     expected_expr = User.username == ADMIN_USER_NAME

#     assert str(actual_expr) == str(expected_expr)
#     create_call = call(db=mock_session, username=ADMIN_USER_NAME, password="password")
#     calls.append(create_call)
#     # mock_create_super_user.assert_has_calls(calls)
#     assert 2 == mock_create_super_user.call_count
#     # Test that superuser credentials are reset
#     mock_settings_service.auth_settings.reset_credentials.assert_called_once()
#     assert mock_settings_service.auth_settings.SUPERUSER != ADMIN_USER_NAME
#     assert mock_settings_service.auth_settings.SUPERUSER_PASSWORD != "password"

#     # Test when superuser already exists
#     mock_settings_service.auth_settings.AUTO_LOGIN = False
#     mock_settings_service.auth_settings.SUPERUSER = ADMIN_USER_NAME
#     mock_settings_service.auth_settings.SUPERUSER_PASSWORD = "password"
#     mock_user = Mock()
#     mock_user.is_superuser = True
#     mock_session.query.return_value.filter.return_value.first.return_value = mock_user
#     setup_superuser(mock_settings_service, mock_session)
#     mock_session.query.assert_called_with(User)
#     actual_expr = mock_session.query.return_value.filter.call_args[0][0]
#     expected_expr = User.username == ADMIN_USER_NAME

#     assert str(actual_expr) == str(expected_expr)


@patch("langflow.services.deps.get_settings_service")
@patch("langflow.services.deps.get_session")
async def test_teardown_superuser_default_superuser(mock_get_session, mock_get_settings_service):
    mock_settings_service = MagicMock()
    mock_settings_service.auth_settings.AUTO_LOGIN = True
    mock_settings_service.auth_settings.SUPERUSER = DEFAULT_SUPERUSER
    mock_settings_service.auth_settings.SUPERUSER_PASSWORD = DEFAULT_SUPERUSER_PASSWORD
    mock_get_settings_service.return_value = mock_settings_service

    mock_session = MagicMock()
    mock_user = MagicMock()
    mock_user.is_superuser = True
    mock_session.query.return_value.filter.return_value.first.return_value = mock_user
    mock_get_session.return_value = iter([mock_session])

    await teardown_superuser(mock_settings_service, mock_session)

    mock_session.query.assert_not_called()


async def test_teardown_superuser_no_default_superuser():
    admin_user_name = "admin_user"
    mock_settings_service = MagicMock()
    mock_settings_service.auth_settings.AUTO_LOGIN = False
    mock_settings_service.auth_settings.SUPERUSER = admin_user_name
    mock_settings_service.auth_settings.SUPERUSER_PASSWORD = "password"  # noqa: S105

    mock_session = AsyncMock(return_value=asyncio.Future())
    mock_user = MagicMock()
    mock_user.is_superuser = False
    mock_user.last_login_at = None

    mock_result = MagicMock()
    mock_result.first.return_value = mock_user
    mock_session.exec.return_value = mock_result

    await teardown_superuser(mock_settings_service, mock_session)

    mock_session.delete.assert_not_awaited()
    mock_session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_super_user_race_condition():
    """Test create_super_user handles race conditions gracefully when multiple workers try to create the same user."""
    # Mock the database session
    mock_session = AsyncMock()

    # Create a mock user that will be "created" by the first worker
    mock_user = MagicMock(spec=User)
    mock_user.username = "testuser"
    mock_user.is_superuser = True

    # Mock get_password_hash to return a fixed value
    mock_get_password_hash = MagicMock(return_value="hashed_password")

    # Set up the race condition scenario:
    # 1. First call to get_user_by_username returns None (user doesn't exist)
    # 2. commit() raises IntegrityError (simulating race condition)
    # 3. After rollback, second call to get_user_by_username returns the existing user
    mock_get_user_by_username = AsyncMock()
    mock_get_user_by_username.side_effect = [None, mock_user]  # None first, then existing user

    mock_session.commit.side_effect = IntegrityError("statement", "params", Exception("orig"))
    with (
        patch("langflow.services.auth.utils.get_user_by_username", mock_get_user_by_username),
        patch("langflow.services.auth.utils.get_password_hash", mock_get_password_hash),
        patch("langflow.services.database.models.user.model.User") as mock_user_class,
    ):
        # Configure the User class mock to return our mock_user when instantiated
        mock_user_class.return_value = mock_user

        result = await create_super_user("testuser", "password", mock_session)

    # Verify that the function handled the race condition correctly
    assert result == mock_user
    assert mock_session.add.call_count == 1  # User was added to session
    assert mock_session.commit.call_count == 1  # Commit was attempted once (and failed)
    assert mock_session.rollback.call_count == 1  # Session was rolled back after IntegrityError
    assert mock_get_user_by_username.call_count == 2  # Called twice: initial check + after rollback


@pytest.mark.asyncio
async def test_create_super_user_race_condition_no_user_found():
    """Test that create_super_user re-raises exception if no user is found after IntegrityError."""
    # Mock the database session
    mock_session = AsyncMock()

    # Mock get_user_by_username to always return None (even after rollback)
    mock_get_user_by_username = AsyncMock()
    mock_get_user_by_username.side_effect = [None, None]  # None for initial check and after rollback

    # Mock other dependencies
    mock_get_password_hash = MagicMock(return_value="hashed_password")
    mock_user = MagicMock(spec=User)

    # Set up scenario where IntegrityError occurs but no user is found afterward
    integrity_error = IntegrityError("statement", "params", Exception("orig"))
    mock_session.commit.side_effect = integrity_error

    with (
        patch("langflow.services.auth.utils.get_user_by_username", mock_get_user_by_username),
        patch("langflow.services.auth.utils.get_password_hash", mock_get_password_hash),
        patch("langflow.services.database.models.user.model.User", return_value=mock_user),
        pytest.raises(IntegrityError),
    ):
        await create_super_user("testuser", "password", mock_session)

    # Verify rollback was called but exception was re-raised
    assert mock_session.rollback.call_count == 1
    assert mock_get_user_by_username.call_count == 2  # Initial + after rollback


@pytest.mark.asyncio
async def test_create_super_user_concurrent_workers():
    """Test multiple concurrent calls to create_super_user with the same username."""
    # This would require a real database to properly test, but we can simulate
    # the behavior with mocks to verify the logic works correctly

    mock_session1 = AsyncMock()
    mock_session2 = AsyncMock()

    # Create mock users
    mock_user = MagicMock(spec=User)
    mock_user.username = "admin"
    mock_user.is_superuser = True

    mock_get_user_by_username = AsyncMock()

    # Worker 1 succeeds, Worker 2 gets IntegrityError then finds existing user
    mock_session1.commit.return_value = None  # Success
    mock_session2.commit.side_effect = IntegrityError("statement", "params", Exception("orig"))  # Race condition

    # get_user_by_username returns None initially, then the created user for worker 2
    mock_get_user_by_username.side_effect = [None, None, mock_user]

    with patch("langflow.services.auth.utils.get_user_by_username", mock_get_user_by_username):
        # Simulate concurrent execution using asyncio.gather
        result1, result2 = await asyncio.gather(
            create_super_user("admin", "password", mock_session1),
            create_super_user("admin", "password", mock_session2),
        )

    # Both workers should end up with a user (worker 1 creates, worker 2 finds existing)
    assert result1 is not None
    assert result2 == mock_user

    # Worker 2 should have rolled back and fetched existing user
    assert mock_session2.rollback.call_count == 1
