import filelock
import pytest
from langflow.services.auth.utils import verify_password
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from langflow.services.utils import SetupSuperuserResult, setup_superuser, teardown_superuser
from lfx.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD
from sqlmodel import select

_MOCK_AUTO_LOGIN_LOCK_TIMEOUT_MSG = "mock lock timeout"


@pytest.fixture
async def initialized_services(monkeypatch, tmp_path):
    """Lightweight fixture: initializes DB + services WITHOUT starting the full app.

    Unlike the `client` fixture, this does NOT create a FastAPI app or use
    LifespanManager. This avoids the heavy lifespan startup/shutdown (MCP servers,
    background tasks, streamable HTTP) that causes hangs on CI Linux.
    """
    from langflow.services.utils import initialize_services, teardown_services
    from lfx.services.manager import get_service_manager

    db_path = tmp_path / "test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")

    get_service_manager().factories.clear()
    get_service_manager().services.clear()

    await initialize_services()

    yield

    await teardown_services()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_initialize_services_creates_default_superuser_when_auto_login_true(initialized_services):  # noqa: ARG001
    """Test that setup_superuser creates the default superuser when AUTO_LOGIN=True."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True

    async with session_scope() as session:
        result = await setup_superuser(settings, session)
        assert result in (
            SetupSuperuserResult.AUTO_LOGIN_INITIALIZED,
            SetupSuperuserResult.AUTO_LOGIN_ALREADY_SATISFIED,
        )

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_teardown_superuser_removes_default_if_never_logged(initialized_services):  # noqa: ARG001
    """AUTO_LOGIN=False removes the default superuser when they have never signed in."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    # The initialized_services fixture already called initialize_services(),
    # which created the default superuser. Ensure it exists and has never logged in.
    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if not user:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
                is_superuser=True,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user.last_login_at = None
        user.is_superuser = True
        await session.commit()

    async with session_scope() as session:
        await teardown_superuser(settings, session)

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        assert (await session.exec(stmt)).first() is None


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_teardown_superuser_preserves_logged_in_default(initialized_services):  # noqa: ARG001
    """Test that teardown preserves default superuser if they have logged in."""
    from datetime import datetime, timezone

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False

    # The initialized_services fixture already created the default superuser.
    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if not user:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
                is_superuser=True,
                is_active=True,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

        # Mark user as having logged in
        user.last_login_at = datetime.now(timezone.utc)
        user.is_superuser = True
        await session.commit()

    # Run teardown and verify user is preserved
    async with session_scope() as session:
        await teardown_superuser(settings, session)

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_with_no_configured_credentials(initialized_services):  # noqa: ARG001
    """Test setup_superuser behavior when no superuser credentials are configured."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = ""
    # Reset password to empty
    settings.auth_settings.SUPERUSER_PASSWORD = ""

    async with session_scope() as session:
        # This should create a default superuser since no credentials are provided
        result = await setup_superuser(settings, session)
        assert result == SetupSuperuserResult.SUPERUSER_CREATED

        # Verify default superuser was created
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_with_custom_credentials(initialized_services):  # noqa: ARG001
    """Test setup_superuser behavior with custom superuser credentials."""
    from pydantic import SecretStr

    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = "custom_admin"
    settings.auth_settings.SUPERUSER_PASSWORD = SecretStr("custom_password")

    # Clean DB state to avoid interference from previous tests
    async with session_scope() as session:
        # Ensure default can be removed by teardown (last_login_at must be None)
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        default_user = (await session.exec(stmt)).first()
        if default_user:
            default_user.last_login_at = None
            await session.commit()
            await teardown_superuser(settings, session)

        # Remove any pre-existing custom_admin user
        stmt = select(User).where(User.username == "custom_admin")
        existing_custom = (await session.exec(stmt)).first()
        if existing_custom:
            await session.delete(existing_custom)
            await session.commit()

    async with session_scope() as session:
        assert await setup_superuser(settings, session) == SetupSuperuserResult.SUPERUSER_CREATED

        # Verify custom superuser was created
        stmt = select(User).where(User.username == "custom_admin")
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True
        # Password should be hashed (not equal to the raw) and verify correctly
        assert user.password != "custom_password"  # noqa: S105
        assert verify_password("custom_password", user.password) is True

        # Verify default superuser was not created
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        default_user = (await session.exec(stmt)).first()
        assert default_user is None

        # Settings credentials should be scrubbed after setup
        assert settings.auth_settings.SUPERUSER_PASSWORD.get_secret_value() == ""

    # Cleanup: remove custom_admin to not leak state across tests
    async with session_scope() as session:
        stmt = select(User).where(User.username == "custom_admin")
        created_custom = (await session.exec(stmt)).first()
        if created_custom:
            await session.delete(created_custom)
            await session.commit()


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_auto_login_lock_timeout_raises_when_no_superuser(initialized_services, monkeypatch):  # noqa: ARG001
    """If the AUTO_LOGIN lock times out and no default superuser exists, startup must fail loudly."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True

    # The fixture initializes services with AUTO_LOGIN=false, which creates the default
    # superuser via the credentials-fallback path. Remove it so we exercise the
    # "lock timed out and no superuser exists" branch.
    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if user is not None:
            await session.delete(user)
            await session.commit()

    class _FailingLock:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            msg = _MOCK_AUTO_LOGIN_LOCK_TIMEOUT_MSG
            raise TimeoutError(msg)

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(filelock, "FileLock", _FailingLock)

    async with session_scope() as session:
        with pytest.raises(
            RuntimeError,
            match="AUTO_LOGIN is enabled but the default superuser was not initialized",
        ):
            await setup_superuser(settings, session)


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_auto_login_lock_timeout_ok_when_superuser_exists(initialized_services, monkeypatch):  # noqa: ARG001
    """If the lock times out but the default superuser already exists, setup continues without error."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True

    async with session_scope() as session:
        await get_auth_service().create_super_user(
            DEFAULT_SUPERUSER,
            DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
            db=session,
        )

    class _FailingLock:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            msg = _MOCK_AUTO_LOGIN_LOCK_TIMEOUT_MSG
            raise TimeoutError(msg)

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(filelock, "FileLock", _FailingLock)

    async with session_scope() as session:
        assert (
            await setup_superuser(settings, session) == SetupSuperuserResult.AUTO_LOGIN_LOCK_TIMEOUT_SUPERUSER_PRESENT
        )

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        assert user is not None
        assert user.is_superuser is True
