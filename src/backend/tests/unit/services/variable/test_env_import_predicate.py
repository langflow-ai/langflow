"""A registered plane may exclude accounts from the environment-variable import; OSS imports for everyone."""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.auth.service import AuthService
from langflow.services.deps import get_settings_service
from langflow.services.variable import runtime_policy
from langflow.services.variable.service import DatabaseVariableService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def service(monkeypatch):
    settings_service = get_settings_service()
    monkeypatch.setattr(settings_service.settings, "store_environment_variables", True)
    monkeypatch.setattr(settings_service.settings, "variables_to_get_from_environment", ["OPENAI_API_KEY"])
    monkeypatch.setenv("OPENAI_API_KEY", "environment-key")
    with patch("langflow.services.auth.utils.get_auth_service", return_value=AuthService(settings_service)):
        yield DatabaseVariableService(settings_service)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def _unregister():
    yield
    runtime_policy.register_env_import_predicate(None)


async def _imported(service, session, user_id) -> bool:
    return bool(await service.list_variables(user_id, session))


async def test_nothing_registered_imports_for_everyone(service, session) -> None:
    user_id = uuid4()
    await service.initialize_user_variables(user_id, session)
    assert await _imported(service, session, user_id)


async def test_an_account_the_predicate_refuses_gets_no_rows(service, session) -> None:
    skipped, kept = uuid4(), uuid4()

    async def predicate(user_id) -> bool:
        return user_id != skipped

    runtime_policy.register_env_import_predicate(predicate)
    await service.initialize_user_variables(skipped, session)
    await service.initialize_user_variables(kept, session)
    assert not await _imported(service, session, skipped)
    assert await _imported(service, session, kept)


async def test_the_predicate_is_asked_with_the_user_id_as_a_uuid(service, session) -> None:
    asked = []

    async def predicate(user_id) -> bool:
        asked.append(user_id)
        return True

    runtime_policy.register_env_import_predicate(predicate)
    user_id = uuid4()
    await service.initialize_user_variables(str(user_id), session)
    assert asked == [user_id]


async def test_a_failing_predicate_imports_nothing_rather_than_everything(service, session) -> None:
    async def predicate(_user_id) -> bool:
        msg = "boom"
        raise RuntimeError(msg)

    runtime_policy.register_env_import_predicate(predicate)
    user_id = uuid4()
    await service.initialize_user_variables(user_id, session)
    assert not await _imported(service, session, user_id)


async def test_the_predicate_an_extension_installs_is_in_force_for_the_first_call(service, session) -> None:
    skipped = uuid4()

    async def predicate(user_id) -> bool:
        return user_id != skipped

    def load_extensions() -> None:
        runtime_policy.register_env_import_predicate(predicate)

    with patch("langflow.services.deployment_artifacts.activation.load_activation_extensions", load_extensions):
        await service.initialize_user_variables(skipped, session)
    assert not await _imported(service, session, skipped)
