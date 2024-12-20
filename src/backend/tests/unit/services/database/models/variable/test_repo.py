import pytest
from uuid import uuid4

from sqlmodel import SQLModel, Session, create_engine

from langflow.services.database.models.variable.model import Variable
from langflow.services.database.models.variable.repo import VariableRepository


@pytest.fixture
def client():
    pass


@pytest.fixture
def repo():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        return VariableRepository(session)


def test_add(repo):
    user_id = uuid4()
    name = "test"
    value = "test"
    _type = "test"
    default_fields = ["test"]
    variable = Variable(user_id=user_id, name=name, value=value, type=_type, default_fields=["test"])

    result = repo.add(variable)

    assert result.id is not None
    assert result.user_id == user_id
    assert result.name == name
    assert result.value == value
    assert result.type == _type
    assert result.default_fields == default_fields


def test_get(repo):
    user_id = uuid4()
    name = "test"
    value = "test"
    _type = "test"
    default_fields = ["test"]
    variable = Variable(user_id=user_id, name=name, value=value, type=_type, default_fields=["test"])
    saved = repo.add(variable)

    result = repo.get(saved.id)

    assert result == saved


def test_list(repo):
    user_id = uuid4()
    name = "test"
    value = "test"
    _type = "test"
    default_fields = ["test"]
    quantity = 10
    for index, i in enumerate(range(quantity)):
        variable = Variable(user_id=user_id, name=name, value=f"value_{index}", type=_type, default_fields=["test"])
        repo.add(variable)

    result = repo.list()

    assert len(result) == quantity


def test_update(repo):
    user_id = uuid4()
    name = "test"
    value = "test"
    _type = "test"
    default_fields = ["test"]
    variable = Variable(user_id=user_id, name=name, value=value, type=_type, default_fields=["test"])
    saved = repo.add(variable)
    saved.name = "test_updated"
    saved.value = "test_updated"
    saved.type = "test_updated"
    saved.default_fields = ["test_updated"]

    repo.update(saved)
    result = repo.get(saved.id)

    assert result.id == saved.id
    assert result.user_id == saved.user_id
    assert result.name == saved.name
    assert result.value == saved.value
    assert result.type == saved.type
    assert result.default_fields == saved.default_fields


def test_delete(repo):
    user_id = uuid4()
    name = "test"
    value = "test"
    _type = "test"
    default_fields = ["test"]
    variable = Variable(user_id=user_id, name=name, value=value, type=_type, default_fields=["test"])
    saved = repo.add(variable)

    repo.delete(saved.id)
    result = repo.get(saved.id)

    assert result is None
