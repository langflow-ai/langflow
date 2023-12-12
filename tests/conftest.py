import json

# we need to import tmpdir
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import orjson
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
from typer.testing import CliRunner

from langflow.graph.graph.base import Graph
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.user.model import User, UserCreate
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


def pytest_configure():
    pytest.BASIC_EXAMPLE_PATH = Path(__file__).parent.absolute() / "data" / "basic_example.json"
    pytest.COMPLEX_EXAMPLE_PATH = Path(__file__).parent.absolute() / "data" / "complex_example.json"
    pytest.OPENAPI_EXAMPLE_PATH = Path(__file__).parent.absolute() / "data" / "Openapi.json"
    pytest.GROUPED_CHAT_EXAMPLE_PATH = Path(__file__).parent.absolute() / "data" / "grouped_chat.json"
    pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH = Path(__file__).parent.absolute() / "data" / "one_group_chat.json"
    pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH = Path(__file__).parent.absolute() / "data" / "vector_store_grouped.json"

    pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY = (
        Path(__file__).parent.absolute() / "data" / "BasicChatwithPromptandHistory.json"
    )
    pytest.VECTOR_STORE_PATH = Path(__file__).parent.absolute() / "data" / "Vector_store.json"
    pytest.CODE_WITH_SYNTAX_ERROR = """
def get_text():
    retun "Hello World"
    """


@pytest.fixture()
async def async_client() -> AsyncGenerator:
    from langflow.main import create_app

    app = create_app()
    async with AsyncClient(app=app, base_url="http://testserver") as client:
        yield client


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


class Config:
    broker_url = "redis://localhost:6379/0"
    result_backend = "redis://localhost:6379/0"


@pytest.fixture(name="distributed_env")
def setup_env(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CACHE_TYPE", "redis")
    monkeypatch.setenv("LANGFLOW_REDIS_HOST", "result_backend")
    monkeypatch.setenv("LANGFLOW_REDIS_PORT", "6379")
    monkeypatch.setenv("LANGFLOW_REDIS_DB", "0")
    monkeypatch.setenv("LANGFLOW_REDIS_EXPIRE", "3600")
    monkeypatch.setenv("LANGFLOW_REDIS_PASSWORD", "")
    monkeypatch.setenv("FLOWER_UNAUTHENTICATED_API", "True")
    monkeypatch.setenv("BROKER_URL", "redis://result_backend:6379/0")
    monkeypatch.setenv("RESULT_BACKEND", "redis://result_backend:6379/0")
    monkeypatch.setenv("C_FORCE_ROOT", "true")


@pytest.fixture(name="distributed_client")
def distributed_client_fixture(session: Session, monkeypatch, distributed_env):
    # Here we load the .env from ../deploy/.env
    from langflow.core import celery_app

    db_dir = tempfile.mkdtemp()
    db_path = Path(db_dir) / "test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
    # monkeypatch langflow.services.task.manager.USE_CELERY to True
    # monkeypatch.setattr(manager, "USE_CELERY", True)
    monkeypatch.setattr(celery_app, "celery_app", celery_app.make_celery("langflow", Config))

    # def get_session_override():
    #     return session

    from langflow.main import create_app

    app = create_app()

    # app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    monkeypatch.undo()


def get_graph(_type="basic"):
    """Get a graph from a json file"""

    if _type == "basic":
        path = pytest.BASIC_EXAMPLE_PATH
    elif _type == "complex":
        path = pytest.COMPLEX_EXAMPLE_PATH
    elif _type == "openapi":
        path = pytest.OPENAPI_EXAMPLE_PATH

    with open(path, "r") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    return Graph(nodes, edges)


@pytest.fixture
def basic_graph_data():
    with open(pytest.BASIC_EXAMPLE_PATH, "r") as f:
        return json.load(f)


@pytest.fixture
def basic_graph():
    return get_graph()


@pytest.fixture
def complex_graph():
    return get_graph("complex")


@pytest.fixture
def openapi_graph():
    return get_graph("openapi")


@pytest.fixture
def json_flow():
    with open(pytest.BASIC_EXAMPLE_PATH, "r") as f:
        return f.read()


@pytest.fixture
def grouped_chat_json_flow():
    with open(pytest.GROUPED_CHAT_EXAMPLE_PATH, "r") as f:
        return f.read()


@pytest.fixture
def one_grouped_chat_json_flow():
    with open(pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH, "r") as f:
        return f.read()


@pytest.fixture
def vector_store_grouped_json_flow():
    with open(pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH, "r") as f:
        return f.read()


@pytest.fixture
def json_flow_with_prompt_and_history():
    with open(pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY, "r") as f:
        return f.read()


@pytest.fixture
def json_vector_store():
    with open(pytest.VECTOR_STORE_PATH, "r") as f:
        return f.read()


@pytest.fixture(name="client", autouse=True)
def client_fixture(session: Session, monkeypatch):
    # Set the database url to a test database
    db_dir = tempfile.mkdtemp()
    db_path = Path(db_dir) / "test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")

    from langflow.main import create_app

    app = create_app()

    # app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    # app.dependency_overrides.clear()
    monkeypatch.undo()
    # clear the temp db
    with suppress(FileNotFoundError):
        db_path.unlink()


# create a fixture for session_getter above
@pytest.fixture(name="session_getter")
def session_getter_fixture(client):
    @contextmanager
    def blank_session_getter(db_service: "DatabaseService"):
        with Session(db_service.engine) as session:
            yield session

    yield blank_session_getter


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def test_user(client):
    user_data = UserCreate(
        username="testuser",
        password="testpassword",
    )
    response = client.post("/api/v1/users", json=user_data.model_dump())
    assert response.status_code == 201
    return response.json()


@pytest.fixture(scope="function")
def active_user(client):
    db_manager = get_db_service()
    with session_getter(db_manager) as session:
        user = User(
            username="activeuser",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        # check if user exists
        if active_user := session.query(User).filter(User.username == user.username).first():
            return active_user
        session.add(user)
        session.commit()
        session.refresh(user)
    return user


@pytest.fixture
def logged_in_headers(client, active_user):
    login_data = {"username": active_user.username, "password": "testpassword"}
    response = client.post("/api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
def flow(client, json_flow: str, active_user):
    from langflow.services.database.models.flow.model import FlowCreate

    loaded_json = json.loads(json_flow)
    flow_data = FlowCreate(
        name="test_flow",
        data=loaded_json.get("data"),
        user_id=active_user.id,
        description="description",
    )
    flow = Flow.model_validate(flow_data.model_dump())
    with session_getter(get_db_service()) as session:
        session.add(flow)
        session.commit()
        session.refresh(flow)

    return flow


@pytest.fixture
def added_flow(client, json_flow_with_prompt_and_history, logged_in_headers):
    flow = orjson.loads(json_flow_with_prompt_and_history)
    data = flow["data"]
    flow = FlowCreate(name="Basic Chat", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    return response.json()


@pytest.fixture
def added_vector_store(client, json_vector_store, logged_in_headers):
    vector_store = orjson.loads(json_vector_store)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Vector Store", description="description", data=data)
    response = client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == vector_store.name
    assert response.json()["data"] == vector_store.data
    return response.json()


@pytest.fixture
def test_component_code():
    path = Path(__file__).parent.absolute() / "data" / "component.py"
    # load the content as a string
    with open(path, "r") as f:
        return f.read()


@pytest.fixture
def test_component_with_templatefield_code():
    path = Path(__file__).parent.absolute() / "data" / "component_with_templatefield.py"
    # load the content as a string
    with open(path, "r") as f:
        return f.read()
