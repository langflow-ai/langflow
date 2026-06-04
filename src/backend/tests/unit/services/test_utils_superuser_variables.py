from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import filelock
import pytest
from langflow.initial_setup import setup as initial_setup
from langflow.services import utils as service_utils
from langflow.services.database.models import User, Variable
from langflow.services.variable import service as variable_service_module
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService
from lfx.services.settings.constants import DEFAULT_SUPERUSER, DEFAULT_SUPERUSER_PASSWORD
from pydantic import SecretStr
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture(name="db_engine")
def db_engine_fixture():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk(dbapi_connection, connection_record):  # noqa: ARG001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture(name="db")
async def db_fixture(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
    async with db_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await db_engine.dispose()


class _FakeAuthService:
    def verify_password(self, password: str, hashed_password: str) -> bool:
        return password == hashed_password

    async def create_super_user(self, username: str, password: str, db: AsyncSession) -> User:
        super_user = User(username=username, password=password, is_superuser=True, is_active=True)
        db.add(super_user)
        await db.flush()
        await db.refresh(super_user)
        return super_user


@pytest.fixture
def settings_service(monkeypatch):
    auth_settings = SimpleNamespace(
        AUTO_LOGIN=False,
        SUPERUSER="configured-admin",
        SUPERUSER_PASSWORD=SecretStr("configured-password"),
        reset_credentials=lambda: None,
    )
    settings = SimpleNamespace(
        agentic_experience=False,
        store_environment_variables=True,
        variables_to_get_from_environment=["BOOTSTRAP_API_KEY"],
    )
    settings_service = SimpleNamespace(auth_settings=auth_settings, settings=settings)

    variable_service = DatabaseVariableService(settings_service)

    monkeypatch.setattr(service_utils, "get_auth_service", lambda: _FakeAuthService())
    monkeypatch.setattr("langflow.services.deps.get_variable_service", lambda: variable_service)
    monkeypatch.setattr(
        variable_service_module.auth_utils,
        "encrypt_api_key",
        lambda value, _settings_service=None: f"encrypted:{value}",
    )
    monkeypatch.setattr(
        variable_service_module.auth_utils,
        "decrypt_api_key",
        lambda value, _settings_service=None: value.removeprefix("encrypted:"),
    )
    return settings_service


async def _get_variable(db: AsyncSession, user_id, name: str) -> Variable:
    return (await db.exec(select(Variable).where(Variable.user_id == user_id, Variable.name == name))).one()


@pytest.mark.asyncio
async def test_auto_login_false_fresh_superuser_gets_env_variables_during_setup(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "env-secret")

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.SUPERUSER_CREATED
    super_user = (await db.exec(select(User).where(User.username == "configured-admin"))).one()
    variable = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert variable.type == CREDENTIAL_TYPE
    assert variable.value == "encrypted:env-secret"


@pytest.mark.asyncio
async def test_auto_login_false_setup_does_not_overwrite_user_modified_env_variable(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "new-env-secret")
    super_user = User(
        username="configured-admin",
        password="configured-password",  # noqa: S106
        is_superuser=True,
        is_active=True,
    )
    db.add(super_user)
    await db.flush()
    await db.refresh(super_user)

    created_at = datetime.now(timezone.utc) - timedelta(days=1)
    variable = Variable(
        user_id=super_user.id,
        name="BOOTSTRAP_API_KEY",
        value="encrypted:user-secret",
        type=CREDENTIAL_TYPE,
        default_fields=[],
        created_at=created_at,
        updated_at=created_at + timedelta(hours=1),
    )
    db.add(variable)
    await db.flush()

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.SUPERUSER_UNCHANGED
    preserved = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert preserved.value == "encrypted:user-secret"


@pytest.mark.asyncio
async def test_auto_login_false_existing_superuser_gets_missing_env_variable(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "env-secret")
    super_user = User(
        username="configured-admin",
        password="configured-password",  # noqa: S106
        is_superuser=True,
        is_active=True,
    )
    db.add(super_user)
    await db.flush()
    await db.refresh(super_user)

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.SUPERUSER_UNCHANGED
    variable = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert variable.value == "encrypted:env-secret"


@pytest.mark.asyncio
async def test_auto_login_false_variable_initialization_failure_does_not_fail_superuser_setup(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    class FailingVariableService:
        async def initialize_user_variables(self, *_, **__) -> None:
            msg = "variable bootstrap failed"
            raise RuntimeError(msg)

    monkeypatch.setattr("langflow.services.deps.get_variable_service", lambda: FailingVariableService())

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.SUPERUSER_CREATED
    super_user = (await db.exec(select(User).where(User.username == "configured-admin"))).one()
    assert super_user.is_superuser is True


@pytest.mark.asyncio
async def test_auto_login_false_variable_initialization_db_failure_rolls_back_only_variables(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    class FailingAfterFlushVariableService:
        async def initialize_user_variables(self, user_id, session: AsyncSession) -> None:
            session.add(
                Variable(
                    user_id=user_id,
                    name="BOOTSTRAP_API_KEY",
                    value="encrypted:partial",
                    type=CREDENTIAL_TYPE,
                    default_fields=[],
                )
            )
            await session.flush()
            msg = "variable bootstrap failed after flush"
            raise RuntimeError(msg)

    monkeypatch.setattr("langflow.services.deps.get_variable_service", lambda: FailingAfterFlushVariableService())

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.SUPERUSER_CREATED
    super_user = (await db.exec(select(User).where(User.username == "configured-admin"))).one()
    assert super_user.is_superuser is True
    variables = (
        await db.exec(select(Variable).where(Variable.user_id == super_user.id, Variable.name == "BOOTSTRAP_API_KEY"))
    ).all()
    assert variables == []


@pytest.mark.asyncio
async def test_auto_login_true_fresh_default_superuser_gets_env_variables_during_setup(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "env-secret")
    settings_service.auth_settings.AUTO_LOGIN = True

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.AUTO_LOGIN_INITIALIZED
    super_user = (await db.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).one()
    variable = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert variable.value == "encrypted:env-secret"


@pytest.mark.asyncio
async def test_initialize_auto_login_default_superuser_gets_env_variables(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "env-secret")
    settings_service.auth_settings.AUTO_LOGIN = True

    @asynccontextmanager
    async def test_session_scope():
        yield db

    monkeypatch.setattr(initial_setup, "session_scope", test_session_scope)
    monkeypatch.setattr(initial_setup, "get_settings_service", lambda: settings_service)
    monkeypatch.setattr(initial_setup, "get_auth_service", lambda: _FakeAuthService())

    await initial_setup.initialize_auto_login_default_superuser()

    super_user = (await db.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).one()
    variable = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert variable.value == "encrypted:env-secret"


@pytest.mark.asyncio
async def test_auto_login_true_fresh_variable_initialization_db_failure_keeps_superuser(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    class FailingAfterFlushVariableService:
        async def initialize_user_variables(self, user_id, session: AsyncSession) -> None:
            session.add(
                Variable(
                    user_id=user_id,
                    name="BOOTSTRAP_API_KEY",
                    value="encrypted:partial",
                    type=CREDENTIAL_TYPE,
                    default_fields=[],
                )
            )
            await session.flush()
            msg = "variable bootstrap failed after flush"
            raise RuntimeError(msg)

    settings_service.auth_settings.AUTO_LOGIN = True
    monkeypatch.setattr("langflow.services.deps.get_variable_service", lambda: FailingAfterFlushVariableService())

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.AUTO_LOGIN_INITIALIZED
    super_user = (await db.exec(select(User).where(User.username == DEFAULT_SUPERUSER))).one()
    assert super_user.is_superuser is True
    variables = (
        await db.exec(select(Variable).where(Variable.user_id == super_user.id, Variable.name == "BOOTSTRAP_API_KEY"))
    ).all()
    assert variables == []


@pytest.mark.asyncio
async def test_auto_login_true_existing_default_superuser_gets_missing_env_variable(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "env-secret")
    settings_service.auth_settings.AUTO_LOGIN = True
    super_user = User(
        username=DEFAULT_SUPERUSER,
        password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
        is_superuser=True,
        is_active=True,
    )
    db.add(super_user)
    await db.flush()
    await db.refresh(super_user)

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.AUTO_LOGIN_ALREADY_SATISFIED
    variable = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert variable.value == "encrypted:env-secret"


@pytest.mark.asyncio
async def test_auto_login_lock_timeout_existing_default_superuser_gets_missing_env_variable(
    db: AsyncSession,
    monkeypatch,
    settings_service,
) -> None:
    monkeypatch.setenv("BOOTSTRAP_API_KEY", "env-secret")
    settings_service.auth_settings.AUTO_LOGIN = True
    super_user = User(
        username=DEFAULT_SUPERUSER,
        password=DEFAULT_SUPERUSER_PASSWORD.get_secret_value(),
        is_superuser=True,
        is_active=True,
    )
    db.add(super_user)
    await db.flush()
    await db.refresh(super_user)

    class FailingLock:
        def __init__(self, *_, **__) -> None:
            pass

        def __enter__(self):
            msg = "mock lock timeout"
            raise TimeoutError(msg)

        def __exit__(self, *_) -> bool:
            return False

    monkeypatch.setattr(filelock, "FileLock", FailingLock)

    result = await service_utils.setup_superuser(settings_service, db)

    assert result == service_utils.SetupSuperuserResult.AUTO_LOGIN_LOCK_TIMEOUT_SUPERUSER_PRESENT
    variable = await _get_variable(db, super_user.id, "BOOTSTRAP_API_KEY")
    assert variable.value == "encrypted:env-secret"
