import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from langflow.services.auth.service import AuthService
from langflow.services.creation_hooks import ERROR_CODE_HEADER, PreCreationDenied
from langflow.services.database.models.user.model import User
from langflow.services.utils import teardown_superuser
from lfx.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
)
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def auth_service() -> AuthService:
    return AuthService(MagicMock())


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
async def test_create_super_user_race_condition(auth_service: AuthService):
    """Test create_super_user handles race conditions gracefully when multiple workers try to create the same user."""
    # Mock the database session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # Create a mock user that will be "created" by the first worker
    mock_user = MagicMock(spec=User)
    mock_user.username = "testuser"
    mock_user.is_superuser = True

    # Mock get_password_hash to return a fixed value
    mock_get_password_hash = MagicMock(return_value="hashed_password")

    # Set up the race condition scenario:
    # 1. First call to get_user_by_username returns None (user doesn't exist)
    # 2. commit() raises IntegrityError (simulating race condition)
    # 3. After rollback, the case-insensitive lookup returns the existing user
    mock_get_user_by_username = AsyncMock()
    mock_get_user_by_username.return_value = None
    mock_get_user_by_username_case_insensitive = AsyncMock(return_value=mock_user)

    mock_session.commit.side_effect = IntegrityError("statement", "params", Exception("orig"))
    with (
        patch("langflow.services.auth.service.get_user_by_username", mock_get_user_by_username),
        patch(
            "langflow.services.auth.service.get_user_by_username_case_insensitive",
            mock_get_user_by_username_case_insensitive,
        ),
        patch.object(auth_service, "get_password_hash", mock_get_password_hash),
        patch("langflow.services.auth.service.User") as mock_user_class,
    ):
        # Configure the User class mock to return our mock_user when instantiated
        mock_user_class.return_value = mock_user

        result = await auth_service.create_super_user("testuser", "password", mock_session)

    # Verify that the function handled the race condition correctly
    assert result == mock_user
    assert mock_session.add.call_count == 1  # User was added to session
    assert mock_session.commit.call_count == 1  # Commit was attempted once (and failed)
    assert mock_session.rollback.call_count == 1  # Session was rolled back after IntegrityError
    assert mock_get_user_by_username.call_count == 1  # Initial exact lookup
    assert mock_get_user_by_username_case_insensitive.call_count == 1  # Case-insensitive recovery lookup


@pytest.mark.asyncio
async def test_create_super_user_integrity_error_recovers_case_variant_superuser(auth_service: AuthService):
    """A case-insensitive unique-index race returns the committed superuser."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    winner_digest = "winner-hash"
    mock_user = User(username="admin", password=winner_digest, is_active=True, is_superuser=True)
    integrity_error = IntegrityError("statement", "params", Exception("orig"))
    mock_session.commit.side_effect = integrity_error
    exact_lookup = AsyncMock(return_value=None)
    case_insensitive_lookup = AsyncMock(return_value=mock_user)

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=exact_lookup),
        patch("langflow.services.auth.service.get_user_by_username_case_insensitive", new=case_insensitive_lookup),
        patch.object(auth_service, "get_password_hash", return_value="loser-hash"),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock()),
    ):
        result = await auth_service.create_super_user("ADMIN", "new-password", mock_session)

    assert result is mock_user
    assert result.password == winner_digest
    assert result.is_superuser is True
    assert result.is_active is True
    exact_lookup.assert_awaited_once_with(mock_session, "ADMIN")
    case_insensitive_lookup.assert_awaited_once_with(mock_session, "ADMIN")
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_super_user_integrity_error_preserves_regular_account_denial(auth_service: AuthService):
    """A case-insensitive unique-index race never returns a regular account as a superuser."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    regular_digest = "regular-hash"
    regular_user = User(username="admin", password=regular_digest, is_active=True, is_superuser=False)
    integrity_error = IntegrityError("statement", "params", Exception("orig"))
    mock_session.commit.side_effect = integrity_error
    exact_lookup = AsyncMock(return_value=None)
    case_insensitive_lookup = AsyncMock(return_value=regular_user)

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=exact_lookup),
        patch("langflow.services.auth.service.get_user_by_username_case_insensitive", new=case_insensitive_lookup),
        patch.object(auth_service, "get_password_hash", return_value="loser-hash"),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock()),
        pytest.raises(IntegrityError),
    ):
        await auth_service.create_super_user("ADMIN", "new-password", mock_session)

    assert regular_user.is_superuser is False
    assert regular_user.password == regular_digest
    exact_lookup.assert_awaited_once_with(mock_session, "ADMIN")
    case_insensitive_lookup.assert_awaited_once_with(mock_session, "ADMIN")
    mock_session.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_super_user_race_condition_no_user_found(auth_service: AuthService):
    """Test that create_super_user re-raises exception if no user is found after IntegrityError."""
    # Mock the database session
    mock_session = AsyncMock()
    mock_session.add = MagicMock()

    # Mock both lookups to return None (even after rollback)
    mock_get_user_by_username = AsyncMock()
    mock_get_user_by_username.return_value = None
    mock_get_user_by_username_case_insensitive = AsyncMock(return_value=None)

    # Mock other dependencies
    mock_get_password_hash = MagicMock(return_value="hashed_password")
    mock_user = MagicMock(spec=User)

    # Set up scenario where IntegrityError occurs but no user is found afterward
    integrity_error = IntegrityError("statement", "params", Exception("orig"))
    mock_session.commit.side_effect = integrity_error

    with (
        patch("langflow.services.auth.service.get_user_by_username", mock_get_user_by_username),
        patch(
            "langflow.services.auth.service.get_user_by_username_case_insensitive",
            mock_get_user_by_username_case_insensitive,
        ),
        patch.object(auth_service, "get_password_hash", mock_get_password_hash),
        patch("langflow.services.auth.service.User", return_value=mock_user),
        pytest.raises(IntegrityError),
    ):
        await auth_service.create_super_user("testuser", "password", mock_session)

    # Verify rollback was called but exception was re-raised
    assert mock_session.rollback.call_count == 1
    assert mock_get_user_by_username.call_count == 1
    assert mock_get_user_by_username_case_insensitive.call_count == 1


@pytest.mark.asyncio
async def test_create_super_user_concurrent_workers(auth_service: AuthService):
    """Test multiple concurrent calls to create_super_user with the same username."""
    # This would require a real database to properly test, but we can simulate
    # the behavior with mocks to verify the logic works correctly

    mock_session1 = AsyncMock()
    mock_session2 = AsyncMock()
    mock_session1.add = MagicMock()
    mock_session2.add = MagicMock()

    # Create mock users
    mock_user = MagicMock(spec=User)
    mock_user.username = "admin"
    mock_user.is_superuser = True

    mock_get_user_by_username = AsyncMock(side_effect=[None, None])
    mock_get_user_by_username_case_insensitive = AsyncMock(return_value=mock_user)

    # Worker 1 succeeds, Worker 2 gets IntegrityError then finds existing user
    mock_session1.commit.return_value = None  # Success
    mock_session2.commit.side_effect = IntegrityError("statement", "params", Exception("orig"))  # Race condition

    with (
        patch("langflow.services.auth.service.get_user_by_username", mock_get_user_by_username),
        patch(
            "langflow.services.auth.service.get_user_by_username_case_insensitive",
            mock_get_user_by_username_case_insensitive,
        ),
        patch.object(auth_service, "get_password_hash", return_value="hashed_password"),
    ):
        # Simulate concurrent execution using asyncio.gather
        result1, result2 = await asyncio.gather(
            auth_service.create_super_user("admin", "password", mock_session1),
            auth_service.create_super_user("admin", "password", mock_session2),
        )

    # Both workers should end up with a user (worker 1 creates, worker 2 finds existing)
    assert result1 is not None
    assert result2 == mock_user

    # Worker 2 should have rolled back and fetched existing user
    assert mock_session2.rollback.call_count == 1
    assert mock_get_user_by_username_case_insensitive.await_count == 1


@pytest.mark.asyncio
async def test_create_super_user_recovers_committed_superuser_after_pre_creation_denial(auth_service: AuthService):
    """A capacity denial after another worker commits returns that unchanged superuser."""
    original_digest = "existing-hash"
    existing_user = User(
        username="admin",
        password=original_digest,
        is_superuser=True,
        is_active=True,
    )
    denial = PreCreationDenied(
        "Your plan includes 1 builder.",
        details={"resource": "builders", "limit": 1, "current": 1, "tier": "essentials"},
    )
    session = AsyncMock()
    exact_lookup = AsyncMock(return_value=None)
    case_insensitive_lookup = AsyncMock(return_value=existing_user)

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=exact_lookup),
        patch("langflow.services.auth.service.get_user_by_username_case_insensitive", new=case_insensitive_lookup),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock(side_effect=denial)),
    ):
        result = await auth_service.create_super_user("ADMIN", "new-password", session)

    assert result is existing_user
    assert result.password == original_digest
    assert result.is_superuser is True
    assert result.is_active is True
    exact_lookup.assert_awaited_once_with(session, "ADMIN")
    case_insensitive_lookup.assert_awaited_once_with(session, "ADMIN")
    session.rollback.assert_awaited_once()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_super_user_recovers_committed_superuser_after_canonical_http_denial(auth_service: AuthService):
    """A canonical tier HTTP denial follows the same committed-user recovery path."""
    original_digest = "existing-hash"
    existing_user = User(
        username="admin",
        password=original_digest,
        is_superuser=True,
        is_active=True,
    )
    denial = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error_code": "tier_limit_reached", "message": "capacity reached"},
        headers={ERROR_CODE_HEADER: "tier_limit_reached"},
    )
    session = AsyncMock()
    exact_lookup = AsyncMock(return_value=None)
    case_insensitive_lookup = AsyncMock(return_value=existing_user)

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=exact_lookup),
        patch("langflow.services.auth.service.get_user_by_username_case_insensitive", new=case_insensitive_lookup),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock(side_effect=denial)),
    ):
        result = await auth_service.create_super_user("admin", "new-password", session)

    assert result is existing_user
    assert result.password == original_digest
    assert result.is_superuser is True
    assert result.is_active is True
    exact_lookup.assert_awaited_once_with(session, "admin")
    case_insensitive_lookup.assert_awaited_once_with(session, "admin")
    session.rollback.assert_awaited_once()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_super_user_preserves_denial_when_no_user_committed(auth_service: AuthService):
    """A denial remains a denial when the competing worker did not commit a user."""
    denial = PreCreationDenied(
        "Your plan includes 1 builder.",
        details={"resource": "builders", "limit": 1, "current": 1, "tier": "essentials"},
    )
    session = AsyncMock()
    exact_lookup = AsyncMock(return_value=None)
    case_insensitive_lookup = AsyncMock(return_value=None)

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=exact_lookup),
        patch("langflow.services.auth.service.get_user_by_username_case_insensitive", new=case_insensitive_lookup),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock(side_effect=denial)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await auth_service.create_super_user("admin", "password", session)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == denial.to_detail()
    assert exc_info.value.headers == {ERROR_CODE_HEADER: "tier_limit_reached"}
    exact_lookup.assert_awaited_once_with(session, "admin")
    case_insensitive_lookup.assert_awaited_once_with(session, "admin")
    session.rollback.assert_awaited_once()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_super_user_preserves_arbitrary_http_denial(auth_service: AuthService):
    """An unrelated HTTP denial is not converted into an existing-user success."""
    denial = HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="permission denied")
    session = AsyncMock()
    lookup = AsyncMock(side_effect=[None])

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=lookup),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock(side_effect=denial)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await auth_service.create_super_user("admin", "password", session)

    assert exc_info.value is denial
    lookup.assert_awaited_once()
    session.rollback.assert_awaited_once()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_super_user_preserves_denial_for_committed_non_superuser(auth_service: AuthService):
    """A same-name regular user cannot be returned as a configured superuser."""
    original_digest = "existing-hash"
    existing_user = User(
        username="admin",
        password=original_digest,
        is_superuser=False,
        is_active=True,
    )
    denial = PreCreationDenied("capacity reached", details={"resource": "builders"})
    session = AsyncMock()
    exact_lookup = AsyncMock(return_value=None)
    case_insensitive_lookup = AsyncMock(return_value=existing_user)

    with (
        patch("langflow.services.auth.service.get_user_by_username", new=exact_lookup),
        patch("langflow.services.auth.service.get_user_by_username_case_insensitive", new=case_insensitive_lookup),
        patch("langflow.services.auth.service.admit_user_creation", new=AsyncMock(side_effect=denial)),
        pytest.raises(HTTPException) as exc_info,
    ):
        await auth_service.create_super_user("admin", "password", session)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert existing_user.is_superuser is False
    assert existing_user.password == original_digest
    exact_lookup.assert_awaited_once_with(session, "admin")
    case_insensitive_lookup.assert_awaited_once_with(session, "admin")
    session.rollback.assert_awaited_once()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_super_user_restart_is_idempotent_after_recovered_race(auth_service: AuthService):
    """A retry sees the committed superuser without rewriting its credentials."""
    original_digest = "existing-hash"
    existing_user = User(
        username="admin",
        password=original_digest,
        is_superuser=True,
        is_active=True,
    )
    session = AsyncMock()
    lookup = AsyncMock(return_value=existing_user)

    with patch("langflow.services.auth.service.get_user_by_username", new=lookup):
        result = await auth_service.create_super_user("admin", "new-password", session)

    assert result is existing_user
    assert result.password == original_digest
    assert result.is_superuser is True
    assert result.is_active is True
    lookup.assert_awaited_once()
    session.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_or_create_super_user_matches_existing_username_case_insensitively(async_session):
    """A configured "Admin" must resolve to an existing "admin", not attempt a create.

    ix_user_username_lower rejects the insert, so an exact-match lookup would
    surface a raw IntegrityError instead of the credential checks below it.
    """
    from langflow.services.utils import get_or_create_super_user

    async_session.add(User(username="admin", password="hashed", is_active=True))  # noqa: S106 # pragma: allowlist secret
    await async_session.commit()
    auth = MagicMock()
    auth.verify_password.return_value = False

    with (
        patch("langflow.services.utils.get_auth_service", return_value=auth),
        pytest.raises(ValueError, match="Incorrect superuser credentials"),
    ):
        await get_or_create_super_user(async_session, "Admin", "password", is_default=False)
    auth.create_super_user.assert_not_called()
