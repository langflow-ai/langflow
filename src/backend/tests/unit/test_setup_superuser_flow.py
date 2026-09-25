from datetime import datetime, timezone
from unittest.mock import AsyncMock

import filelock
import pytest
from langflow.services.auth.utils import verify_password
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_auth_service, get_settings_service, session_scope
from langflow.services.utils import SetupSuperuserResult, setup_superuser, teardown_superuser
from lfx.services.settings.constants import (
    DEFAULT_SUPERUSER,
    DEFAULT_SUPERUSER_PASSWORD,
    LEGACY_DEFAULT_SUPERUSER_PASSWORD,
)
from pydantic import SecretStr
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
    monkeypatch.setenv("LANGFLOW_SUPERUSER", DEFAULT_SUPERUSER)
    monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "test-superuser-password")

    get_service_manager().factories.clear()
    get_service_manager().services.clear()

    await initialize_services()

    yield

    await teardown_services()


async def test_server_startup_imports_environment_for_existing_users(initialized_services, monkeypatch):  # noqa: ARG001
    """Startup must import newly configured variables for SSO and password users."""
    from langflow.preload import _STATE, initialize_environment_variables
    from langflow.services.database.models.auth import SSOUserProfile
    from langflow.services.deps import get_variable_service
    from langflow.services.utils import initialize_services

    async with session_scope() as session:
        # Cross the startup sweep's page boundary, including an existing SSO account.
        users = [
            User(username=f"existing-user-{index}", password="unused")  # noqa: S106  # pragma: allowlist secret
            for index in range(101)
        ]
        session.add_all(users)
        await session.flush()
        user_ids = [user.id for user in users]
        session.add(SSOUserProfile(user_id=user_ids[0], sso_provider="external", sso_user_id="existing-subject"))

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "store_environment_variables", True)
    monkeypatch.setattr(settings, "variables_to_get_from_environment", ["NEW_SERVICE_URL"])
    for env_value in ["https://service.example.com", "https://rotated.example.com"]:
        monkeypatch.setenv("NEW_SERVICE_URL", env_value)
        await initialize_services(skip_superuser_setup=True)
        monkeypatch.setattr(_STATE, "environment_variables_initialized", False)
        await initialize_environment_variables()

        async with session_scope() as session:
            for user_id in user_ids:
                value = await get_variable_service().get_variable(user_id, "NEW_SERVICE_URL", "", session)
                assert value.get_secret_value() == env_value


async def test_cli_service_initialization_does_not_sweep_users(initialized_services, monkeypatch):  # noqa: ARG001
    """Shared service initialization used by migration commands must not run the sweep."""
    from langflow.services.deps import get_variable_service
    from langflow.services.utils import initialize_services

    sweep = AsyncMock()
    monkeypatch.setattr(get_variable_service(), "initialize_all_user_variables", sweep)
    await initialize_services(skip_superuser_setup=True)
    sweep.assert_not_awaited()


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
        assert verify_password("test-superuser-password", user.password) is True
        assert verify_password(LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value(), user.password) is False


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_auto_login_rotates_legacy_default_password(initialized_services):  # noqa: ARG001
    """AUTO_LOGIN startup rotates old langflow/langflow hashes left by previous releases."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True
    settings.auth_settings.SUPERUSER = DEFAULT_SUPERUSER
    settings.auth_settings.SUPERUSER_PASSWORD = DEFAULT_SUPERUSER_PASSWORD
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if user is None:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=get_auth_service().get_password_hash(legacy_password),
                is_superuser=True,
                is_active=True,
            )
            session.add(user)
            await session.flush()
        else:
            user.password = get_auth_service().get_password_hash(legacy_password)
        user.is_superuser = True
        await session.commit()

    async with session_scope() as session:
        result = await setup_superuser(settings, session)
        assert result == SetupSuperuserResult.AUTO_LOGIN_ALREADY_SATISFIED

    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        assert user is not None
        assert verify_password(legacy_password, user.password) is False


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_rotates_legacy_default_password_when_auto_login_false(
    initialized_services,  # noqa: ARG001
):
    """Authenticated startup rotates old langflow/langflow hashes to the configured password."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = DEFAULT_SUPERUSER
    settings.auth_settings.SUPERUSER_PASSWORD = SecretStr("rotated-production-password")
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()

    async with session_scope() as session:
        stmt = select(User).where(User.username == DEFAULT_SUPERUSER)
        user = (await session.exec(stmt)).first()
        if user is None:
            user = User(
                username=DEFAULT_SUPERUSER,
                password=get_auth_service().get_password_hash(legacy_password),
                is_superuser=True,
                is_active=True,
            )
            session.add(user)
            await session.flush()
        user.password = get_auth_service().get_password_hash(legacy_password)
        user.is_superuser = True
        user.is_active = True
        user.last_login_at = datetime.now(timezone.utc)
        await session.commit()

    async with session_scope() as session:
        result = await setup_superuser(settings, session)
        assert result == SetupSuperuserResult.SUPERUSER_UNCHANGED

    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        assert user is not None
        assert verify_password("rotated-production-password", user.password) is True
        assert verify_password(legacy_password, user.password) is False


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_auto_login_fails_when_username_is_not_superuser(initialized_services):  # noqa: ARG001
    """AUTO_LOGIN setup must not accept an existing non-superuser bootstrap username."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True
    settings.auth_settings.SUPERUSER = "regular-user"
    settings.auth_settings.SUPERUSER_PASSWORD = DEFAULT_SUPERUSER_PASSWORD

    async with session_scope() as session:
        user = User(
            username="regular-user",
            password=get_auth_service().get_password_hash("regular-password"),
            is_superuser=False,
            is_active=True,
        )
        session.add(user)
        await session.commit()

    async with session_scope() as session:
        with pytest.raises(RuntimeError, match="not a superuser"):
            await setup_superuser(settings, session)


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
                password=get_auth_service().get_password_hash("test-superuser-password"),
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
                password=get_auth_service().get_password_hash("test-superuser-password"),
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
async def test_setup_superuser_with_no_configured_credentials_fails_closed(initialized_services):  # noqa: ARG001
    """AUTO_LOGIN=False must not create a superuser from predictable fallback credentials."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = ""
    # Reset password to empty
    settings.auth_settings.SUPERUSER_PASSWORD = ""

    async with session_scope() as session:
        with pytest.raises(ValueError, match="Username and password must be set"):
            await setup_superuser(settings, session)


@pytest.mark.parametrize("username", [DEFAULT_SUPERUSER, "custom_admin"])
@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_rejects_legacy_default_password_when_auto_login_false(
    initialized_services,  # noqa: ARG001
    username,
):
    """Authenticated startup must not create a superuser with the legacy default password."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = False
    settings.auth_settings.SUPERUSER = username
    settings.auth_settings.SUPERUSER_PASSWORD = LEGACY_DEFAULT_SUPERUSER_PASSWORD

    async with session_scope() as session:
        with pytest.raises(ValueError, match="legacy default password"):
            await setup_superuser(settings, session)

    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == username))).first()
        assert user is None


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_auto_login_ignores_configured_legacy_default_password(
    initialized_services,  # noqa: ARG001
):
    """AUTO_LOGIN startup must not persist langflow/langflow even when env config provides it."""
    settings = get_settings_service()
    settings.auth_settings.AUTO_LOGIN = True
    settings.auth_settings.SUPERUSER = DEFAULT_SUPERUSER
    settings.auth_settings.SUPERUSER_PASSWORD = LEGACY_DEFAULT_SUPERUSER_PASSWORD
    legacy_password = LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value()

    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        assert user is not None
        user.password = get_auth_service().get_password_hash(legacy_password)
        user.is_superuser = True
        user.is_active = True
        await session.commit()

    async with session_scope() as session:
        assert await setup_superuser(settings, session) == SetupSuperuserResult.AUTO_LOGIN_ALREADY_SATISFIED

    async with session_scope() as session:
        user = (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()
        assert user is not None
        assert user.is_superuser is True
        assert verify_password(legacy_password, user.password) is False


@pytest.mark.asyncio
@pytest.mark.timeout(30)
async def test_setup_superuser_with_custom_credentials(initialized_services):  # noqa: ARG001
    """Test setup_superuser behavior with custom superuser credentials."""
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
            "test-superuser-password",
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


# ---------------------------------------------------------------------------
# A default superuser that owns work must survive AUTO_LOGIN being turned off.
# Found adopting an existing database into a deployment with AUTO_LOGIN off: the
# delete cascaded on Postgres and took every flow and project the user owned.
# ---------------------------------------------------------------------------


@pytest.fixture(params=["sqlite", "postgres"])
async def services_on(request, monkeypatch, tmp_path):
    """Services on SQLite, and on Postgres when LANGFLOW_TEST_DATABASE_URI is set."""
    import os
    import uuid as uuid_module

    import sqlalchemy as sa
    from langflow.services.utils import initialize_services, teardown_services
    from lfx.services.manager import get_service_manager

    base = os.environ.get("LANGFLOW_TEST_DATABASE_URI")
    if request.param == "postgres" and not base:
        pytest.skip("LANGFLOW_TEST_DATABASE_URI not set")

    admin_engine = None
    db_name = None
    started = False
    try:
        if request.param == "sqlite":
            url = f"sqlite:///{tmp_path / 'test.db'}"
        else:
            admin_url = sa.engine.make_url(base).set(drivername="postgresql+psycopg")
            db_name = f"lf_su_{uuid_module.uuid4().hex[:10]}"
            admin_engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
            with admin_engine.connect() as conn:
                conn.execute(sa.text(f'CREATE DATABASE "{db_name}"'))
            url = admin_url.set(database=db_name).render_as_string(hide_password=False)

        monkeypatch.setenv("LANGFLOW_DATABASE_URL", url)
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
        monkeypatch.setenv("LANGFLOW_SUPERUSER", "admin")
        monkeypatch.setenv("LANGFLOW_SUPERUSER_PASSWORD", "admin-password")
        get_service_manager().factories.clear()
        get_service_manager().services.clear()
        started = True
        await initialize_services()
        yield request.param
    finally:
        # The database goes even when teardown fails, or the next run inherits it.
        try:
            if started:
                await teardown_services()
        finally:
            if admin_engine is not None:
                with admin_engine.connect() as conn:
                    conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)'))
                admin_engine.dispose()


async def _default_superuser_owning_work(
    *,
    owns_work: bool = True,
    logged_in: bool = False,
    password: str = "old-password",  # noqa: S107  # pragma: allowlist secret
):
    """The account an AUTO_LOGIN instance leaves behind, as it looks after a migration."""
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.variable.model import Variable

    async with session_scope() as session:
        user = User(
            username=DEFAULT_SUPERUSER,
            password=get_auth_service().get_password_hash(password),
            is_superuser=True,
            is_active=True,
            last_login_at=datetime.now(timezone.utc) if logged_in else None,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        if owns_work:
            folder = Folder(name="team work", user_id=user.id)
            session.add(folder)
            await session.commit()
            await session.refresh(folder)
            session.add(Flow(name="the flow that matters", user_id=user.id, folder_id=folder.id, data={}))
            session.add(Variable(name="MY_KEY", value="encrypted", type="Credential", user_id=user.id))
            await session.commit()
        return user.id


async def _work_owned_by(user_id) -> tuple[int, int, int]:
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.folder.model import Folder
    from langflow.services.database.models.variable.model import Variable

    async with session_scope() as session:
        flows = len((await session.exec(select(Flow).where(Flow.user_id == user_id))).all())
        folders = len((await session.exec(select(Folder).where(Folder.user_id == user_id))).all())
        variables = len((await session.exec(select(Variable).where(Variable.user_id == user_id))).all())
    return flows, folders, variables


async def _default_superuser():
    async with session_scope() as session:
        return (await session.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).first()


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_default_superuser_that_owns_work_is_kept_and_locked(services_on):  # noqa: ARG001
    """Another superuser is configured, so the old account keeps its data and loses its default password."""
    user_id = await _default_superuser_owning_work(password=LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value())

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    kept = await _default_superuser()
    assert kept is not None
    assert kept.id == user_id
    assert await _work_owned_by(user_id) == (1, 1, 1)
    for guess in ("", LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value(), "admin-password"):
        assert not verify_password(guess, kept.password)
    assert kept.is_active is False


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_kept_default_superuser_api_keys_stop_working(services_on):  # noqa: ARG001
    """Anyone could mint keys as this account while AUTO_LOGIN was on; they must not outlive it."""
    from langflow.services.database.models.api_key.crud import check_key, create_api_key
    from langflow.services.database.models.api_key.model import ApiKeyCreate

    user_id = await _default_superuser_owning_work(password=LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value())
    async with session_scope() as session:
        key = (await create_api_key(session, ApiKeyCreate(name="minted under auto login"), user_id)).api_key
    assert (await check_key(key)).id == user_id

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    assert await check_key(key) is None
    assert await _work_owned_by(user_id) == (1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_an_auto_login_account_with_a_generated_password_is_retired(services_on):  # noqa: ARG001
    """AUTO_LOGIN gives the account a random password, so a default-password check never sees it."""
    from secrets import token_urlsafe

    from langflow.services.database.models.api_key.crud import check_key, create_api_key
    from langflow.services.database.models.api_key.model import ApiKeyCreate

    user_id = await _default_superuser_owning_work(password=token_urlsafe(32))
    async with session_scope() as session:
        key = (await create_api_key(session, ApiKeyCreate(name="minted under auto login"), user_id)).api_key

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    assert await check_key(key) is None
    assert (await _default_superuser()).is_active is False
    assert await _work_owned_by(user_id) == (1, 1, 1)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_claiming_a_retired_default_superuser_reactivates_it(services_on, monkeypatch):  # noqa: ARG001
    """Retired by an earlier teardown, then named in LANGFLOW_SUPERUSER: the operator must be able to sign in."""
    user_id = await _default_superuser_owning_work(password=LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value())
    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)
    assert (await _default_superuser()).is_active is False

    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER", DEFAULT_SUPERUSER)
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER_PASSWORD", SecretStr("claimed-password"))
    async with session_scope() as session:
        await setup_superuser(settings, session)

    kept = await _default_superuser()
    assert kept.id == user_id
    assert kept.is_active is True
    assert verify_password("claimed-password", kept.password)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_an_admin_reactivation_survives_the_next_teardown(services_on):  # noqa: ARG001
    """An admin turns the retired account back on; a restart must not turn it off again."""
    user_id = await _default_superuser_owning_work(password=LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value())
    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    async with session_scope() as session:
        user = await session.get(User, user_id)
        user.is_active = True
        session.add(user)

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    assert (await _default_superuser()).is_active is True


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_a_password_an_admin_set_survives_the_next_teardown(services_on):  # noqa: ARG001
    """An admin resets the locked account; a restart before its first sign-in must not undo that."""
    user_id = await _default_superuser_owning_work(password=LEGACY_DEFAULT_SUPERUSER_PASSWORD.get_secret_value())
    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    async with session_scope() as session:
        user = await session.get(User, user_id)
        user.password = get_auth_service().get_password_hash("set-by-an-admin")
        session.add(user)

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    assert verify_password("set-by-an-admin", (await _default_superuser()).password)


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_configured_default_superuser_is_claimed_with_its_data(services_on, monkeypatch):  # noqa: ARG001
    """LANGFLOW_SUPERUSER names the default account: the operator gets it, with the configured password."""
    settings = get_settings_service()
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER", DEFAULT_SUPERUSER)
    monkeypatch.setattr(settings.auth_settings, "SUPERUSER_PASSWORD", SecretStr("claimed-password"))
    user_id = await _default_superuser_owning_work()

    async with session_scope() as session:
        await setup_superuser(settings, session)

    kept = await _default_superuser()
    assert kept.id == user_id
    assert verify_password("claimed-password", kept.password)
    assert await _work_owned_by(user_id) == (1, 1, 1)
    assert kept.is_active is True


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_default_superuser_that_owns_nothing_is_still_removed(services_on):  # noqa: ARG001
    await _default_superuser_owning_work(owns_work=False)

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    assert await _default_superuser() is None


@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_default_superuser_that_signed_in_is_untouched(services_on):  # noqa: ARG001
    user_id = await _default_superuser_owning_work(logged_in=True)

    async with session_scope() as session:
        await teardown_superuser(get_settings_service(), session)

    kept = await _default_superuser()
    assert kept.id == user_id
    assert verify_password("old-password", kept.password)
    assert await _work_owned_by(user_id) == (1, 1, 1)
