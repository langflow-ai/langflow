from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlmodel import Session, SQLModel, create_engine

from langflow.services.database.models.variable.model import VariableUpdate
from langflow.services.deps import get_settings_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService


@pytest.fixture
def service():
    settings_service = get_settings_service()
    return DatabaseVariableService(settings_service)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.skip(reason="Temporarily disabled")
def test_initialize_user_variables__donkey(service, session):
    user_id = uuid4()
    name = "OPENAI_API_KEY"
    value = "donkey"
    service.initialize_user_variables(user_id, session=session)
    result = service.create_variable(user_id, "OPENAI_API_KEY", "donkey", session=session)
    new_service = DatabaseVariableService(get_settings_service())
    new_service.initialize_user_variables(user_id, session=session)

    result = new_service.get_variable(user_id, name, "", session=session)

    assert result != value


def test_initialize_user_variables__not_found_variable(service, session):
    with patch("langflow.services.variable.service.DatabaseVariableService.create_variable") as m:
        m.side_effect = Exception()
        service.initialize_user_variables(uuid4(), session=session)

    assert True


def test_initialize_user_variables__skipping_environment_variable_storage(service, session):
    service.settings_service.settings.store_environment_variables = False
    service.initialize_user_variables(uuid4(), session=session)
    assert True


def test_get_variable(service, session):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = ""
    service.create_variable(user_id, name, value, session=session)

    result = service.get_variable(user_id, name, field, session=session)

    assert result == value


def test_get_variable__ValueError(service, session):
    user_id = uuid4()
    name = "name"
    field = ""

    with pytest.raises(ValueError) as exc:
        service.get_variable(user_id, name, field, session)

    assert name in str(exc.value)
    assert "variable not found" in str(exc.value)


def test_get_variable__TypeError(service, session):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = "session_id"
    _type = CREDENTIAL_TYPE
    service.create_variable(user_id, name, value, _type=_type, session=session)

    with pytest.raises(TypeError) as exc:
        service.get_variable(user_id, name, field, session)

    assert name in str(exc.value)
    assert "purpose is to prevent the exposure of value" in str(exc.value)


def test_list_variables(service, session):
    user_id = uuid4()
    names = ["name1", "name2", "name3"]
    value = "value"
    for name in names:
        service.create_variable(user_id, name, value, session=session)

    result = service.list_variables(user_id, session=session)

    assert all(name in result for name in names)


def test_list_variables__empty(service, session):
    result = service.list_variables(uuid4(), session=session)

    assert not result
    assert isinstance(result, list)


def test_update_variable(service, session):
    user_id = uuid4()
    name = "name"
    old_value = "old_value"
    new_value = "new_value"
    field = ""
    service.create_variable(user_id, name, old_value, session=session)

    old_recovered = service.get_variable(user_id, name, field, session=session)
    result = service.update_variable(user_id, name, new_value, session=session)
    new_recovered = service.get_variable(user_id, name, field, session=session)

    assert old_value == old_recovered
    assert new_value == new_recovered
    assert result.user_id == user_id
    assert result.name == name
    assert result.value != old_value
    assert result.value != new_value
    assert result.default_fields == []
    assert result.type == GENERIC_TYPE
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)


def test_update_variable__ValueError(service, session):
    user_id = uuid4()
    name = "name"
    value = "value"

    with pytest.raises(ValueError) as exc:
        service.update_variable(user_id, name, value, session=session)

    assert name in str(exc.value)
    assert "variable not found" in str(exc.value)


def test_update_variable_fields(service, session):
    user_id = uuid4()
    new_name = new_value = "donkey"
    variable = service.create_variable(user_id, "old_name", "old_value", session=session)
    saved = variable.model_dump()
    variable = VariableUpdate(**saved)
    variable.name = new_name
    variable.value = new_value
    variable.default_fields = ["new_field"]

    result = service.update_variable_fields(
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


def test_delete_variable(service, session):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = ""

    service.create_variable(user_id, name, value, session=session)
    recovered = service.get_variable(user_id, name, field, session=session)
    service.delete_variable(user_id, name, session=session)
    with pytest.raises(ValueError) as exc:
        service.get_variable(user_id, name, field, session)

    assert recovered == value
    assert name in str(exc.value)
    assert "variable not found" in str(exc.value)


def test_delete_variable__ValueError(service, session):
    user_id = uuid4()
    name = "name"

    with pytest.raises(ValueError) as exc:
        service.delete_variable(user_id, name, session=session)

    assert name in str(exc.value)
    assert "variable not found" in str(exc.value)


def test_delete_varaible_by_id(service, session):
    user_id = uuid4()
    name = "name"
    value = "value"
    field = "field"

    saved = service.create_variable(user_id, name, value, session=session)
    recovered = service.get_variable(user_id, name, field, session=session)
    service.delete_variable_by_id(user_id, saved.id, session=session)
    with pytest.raises(ValueError) as exc:
        service.get_variable(user_id, name, field, session)

    assert recovered == value
    assert name in str(exc.value)
    assert "variable not found" in str(exc.value)


def test_delete_variable_by_id__ValueError(service, session):
    user_id = uuid4()
    variable_id = uuid4()

    with pytest.raises(ValueError) as exc:
        service.delete_variable_by_id(user_id, variable_id, session=session)

    assert str(variable_id) in str(exc.value)
    assert "variable not found" in str(exc.value)


def test_create_variable(service, session):
    user_id = uuid4()
    name = "name"
    value = "value"

    result = service.create_variable(user_id, name, value, session=session)

    assert result.user_id == user_id
    assert result.name == name
    assert result.value != value
    assert result.default_fields == []
    assert result.type == GENERIC_TYPE
    assert isinstance(result.created_at, datetime)
    assert isinstance(result.updated_at, datetime)
