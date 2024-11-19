import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from langflow.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
)
from langflow.services.utils import teardown_superuser

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
