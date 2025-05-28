from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from langflow.services.database.models.variable.model import VariableUpdate
from langflow.services.deps import get_settings_service
from langflow.services.settings.constants import VARIABLES_TO_GET_FROM_ENVIRONMENT
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
def service():
    settings_service = get_settings_service()
    return DatabaseVariableService(settings_service)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


async def test_initialize_user_variables__create_and_update(service, session: AsyncSession):
    user_id = uuid4()
    field = ""
    good_vars = {k: f"value{i}" for i, k in enumerate(VARIABLES_TO_GET_FROM_ENVIRONMENT)}
    bad_vars = {"VAR1": "value1", "VAR2": "value2", "VAR3": "value3"}
    env_vars = {**good_vars, **bad_vars}

    await service.create_variable(user_id, "OPENAI_API_KEY", "outdate", session=session)
    env_vars["OPENAI_API_KEY"] = "updated_value"

    with patch.dict("os.environ", env_vars, clear=True):
        await service.initialize_user_variables(user_id=user_id, session=session)

    variables = await service.list_variables(user_id, session=session)
    for name in variables:
        value = await service.get_variable(user_id, name, field, session=session)
        assert value == env_vars[name]

    assert all(i in variables for i in good_vars)
    assert all(i not in variables for i in bad_vars)


async def test_initialize_user_variables__not_found_variable(service, session: AsyncSession):
    with patch("langflow.services.variable.service.DatabaseVariableService.create_variable") as m:
        m.side_effect = Exception()
        await service.initialize_user_variables(uuid4(), session=session)
    assert True


async def test_initialize_user_variables__skipping_environment_variable_storage(service, session: AsyncSession):
    service.settings_service.settings.store_environment_variables = False
    await service.initialize_user_variables(uuid4(), session=session)
    assert True


async def test_get_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = ""
    await service.create_variable(user_id, name, value, session=session)

    result = await service.get_variable(user_id, name, field, session=session)

    assert result == value


async def test_get_variable__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    field = ""

    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.get_variable(user_id, name, field, session=session)


async def test_get_variable__typeerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = "session_id"
    type_ = CREDENTIAL_TYPE
    await service.create_variable(user_id, name, value, type_=type_, session=session)

    with pytest.raises(TypeError) as exc:
        await service.get_variable(user_id, name, field, session=session)

    assert name in str(exc.value)
    assert "purpose is to prevent the exposure of value" in str(exc.value)


async def test_list_variables(service, session: AsyncSession):
    user_id = uuid4()
    names = ["name1", "name2", "name3"]
    value = "value"
    for name in names:
        await service.create_variable(user_id, name, value, session=session)

    result = await service.list_variables(user_id, session=session)

    assert all(name in result for name in names)


async def test_list_variables__empty(service, session: AsyncSession):
    result = await service.list_variables(uuid4(), session=session)

    assert not result
    assert isinstance(result, list)


async def test_update_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    old_value = "old_value"
    new_value = "new_value"
    field = ""
    await service.create_variable(user_id, name, old_value, session=session)

    old_recovered = await service.get_variable(user_id, name, field, session=session)
    result = await service.update_variable(user_id, name, new_value, session=session)
    new_recovered = await service.get_variable(user_id, name, field, session=session)

    assert old_value == old_recovered
    assert new_value == new_recovered
    assert result.user_id == user_id
    assert result.name == name
    assert result.value != old_value
    assert result.value != new_value
    assert result.default_fields == []
    assert result.type == CREDENTIAL_TYPE
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)


async def test_update_variable__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"

    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.update_variable(user_id, name, value, session=session)


async def test_update_variable_fields(service, session: AsyncSession):
    user_id = uuid4()
    new_name = new_value = "donkey"
    variable = await service.create_variable(user_id, "old_name", "old_value", session=session)
    saved = variable.model_dump()
    variable = VariableUpdate(**saved)
    variable.name = new_name
    variable.value = new_value
    variable.default_fields = ["new_field"]

    result = await service.update_variable_fields(
        user_id=user_id,
        variable_id=saved.get("id"),
        variable=variable,
        session=session,
    )

    assert result.name == new_name
    assert result.value != new_value
    assert saved.get("id") == result.id
    assert saved.get("user_id") == result.user_id
    assert saved.get("name") != result.name
    assert saved.get("value") != result.value
    assert saved.get("default_fields") != result.default_fields
    assert saved.get("type") == result.type
    assert saved.get("created_at") == result.created_at
    assert saved.get("updated_at") != result.updated_at


async def test_delete_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = ""

    await service.create_variable(user_id, name, value, session=session)
    recovered = await service.get_variable(user_id, name, field, session=session)
    await service.delete_variable(user_id, name, session=session)
    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.get_variable(user_id, name, field, session=session)

    assert recovered == value


async def test_delete_variable__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"

    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.delete_variable(user_id, name, session=session)


async def test_delete_variable_by_id(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = "field"

    saved = await service.create_variable(user_id, name, value, session=session)
    recovered = await service.get_variable(user_id, name, field, session=session)
    await service.delete_variable_by_id(user_id, saved.id, session=session)
    with pytest.raises(ValueError, match=f"{name} variable not found."):
        await service.get_variable(user_id, name, field, session=session)

    assert recovered == value


async def test_delete_variable_by_id__valueerror(service, session: AsyncSession):
    user_id = uuid4()
    variable_id = uuid4()

    with pytest.raises(ValueError, match=f"{variable_id} variable not found."):
        await service.delete_variable_by_id(user_id, variable_id, session=session)


async def test_create_variable(service, session: AsyncSession):
    user_id = uuid4()
    name = "name"
    value = "value"

    result = await service.create_variable(user_id, name, value, session=session)

    assert result.user_id == user_id
    assert result.name == name
    assert result.value != value
    assert result.default_fields == []
    assert result.type == CREDENTIAL_TYPE
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)
