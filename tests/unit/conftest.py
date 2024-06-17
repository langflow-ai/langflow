import json
import os.path
import shutil

# we need to import tmpdir
import tempfile
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import TYPE_CHECKING, AsyncGenerator

import orjson
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from httpx import AsyncClient
from langflow.graph.graph.base import Graph
from langflow.initial_setup.setup import STARTER_FOLDER_NAME
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User, UserCreate
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from typer.testing import CliRunner

if TYPE_CHECKING:
    from langflow.services.database.service import DatabaseService


load_dotenv()


def pytest_configure(config):
    config.addinivalue_line("markers", "noclient: don't create a client for this test")
    data_path = Path(__file__).parent.absolute() / "data"

    pytest.BASIC_EXAMPLE_PATH = data_path / "basic_example.json"
    pytest.COMPLEX_EXAMPLE_PATH = data_path / "complex_example.json"
    pytest.OPENAPI_EXAMPLE_PATH = data_path / "Openapi.json"
    pytest.GROUPED_CHAT_EXAMPLE_PATH = data_path / "grouped_chat.json"
    pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH = data_path / "one_group_chat.json"
    pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH = data_path / "vector_store_grouped.json"

    pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY = data_path / "BasicChatwithPromptandHistory.json"
    pytest.CHAT_INPUT = data_path / "ChatInputTest.json"
    pytest.TWO_OUTPUTS = data_path / "TwoOutputsTest.json"
    pytest.VECTOR_STORE_PATH = data_path / "Vector_store.json"
    pytest.CODE_WITH_SYNTAX_ERROR = """
def get_text():
    retun "Hello World"
    """

    # validate that all the paths are correct and the files exist
    for path in [
        pytest.BASIC_EXAMPLE_PATH,
        pytest.COMPLEX_EXAMPLE_PATH,
        pytest.OPENAPI_EXAMPLE_PATH,
        pytest.GROUPED_CHAT_EXAMPLE_PATH,
        pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH,
        pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH,
        pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY,
        pytest.CHAT_INPUT,
        pytest.TWO_OUTPUTS,
        pytest.VECTOR_STORE_PATH,
    ]:
        assert path.exists(), f"File {path} does not exist. Available files: {list(data_path.iterdir())}"


@pytest.fixture(autouse=True)
def check_openai_api_key_in_environment_variables():
    import os

    assert os.environ.get("OPENAI_API_KEY") is not None, "OPENAI_API_KEY is not set in environment variables"


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


@pytest.fixture(name="load_flows_dir")
def load_flows_dir():
    tempdir = tempfile.TemporaryDirectory()
    yield tempdir.name


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
def client_fixture(session: Session, monkeypatch, request, load_flows_dir):
    # Set the database url to a test database
    if "noclient" in request.keywords:
        yield
    else:
        db_dir = tempfile.mkdtemp()
        db_path = Path(db_dir) / "test.db"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
        if "load_flows" in request.keywords:
            shutil.copyfile(
                pytest.BASIC_EXAMPLE_PATH, os.path.join(load_flows_dir, "c54f9130-f2fa-4a3e-b22a-3856d946351b.json")
            )
            monkeypatch.setenv("LANGFLOW_LOAD_FLOWS_PATH", load_flows_dir)
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")

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
    response = client.post("/api/v1/users", json=user_data.dict())
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
        if active_user := session.exec(select(User).where(User.username == user.username)).first():
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
    flow_data = FlowCreate(name="test_flow", data=loaded_json.get("data"), user_id=active_user.id)

    flow = Flow.model_validate(flow_data)
    with session_getter(get_db_service()) as session:
        session.add(flow)
        session.commit()
        session.refresh(flow)

    return flow


@pytest.fixture
def json_chat_input():
    with open(pytest.CHAT_INPUT, "r") as f:
        return f.read()


@pytest.fixture
def json_two_outputs():
    with open(pytest.TWO_OUTPUTS, "r") as f:
        return f.read()


@pytest.fixture
def added_flow_with_prompt_and_history(client, json_flow_with_prompt_and_history, logged_in_headers):
    flow = orjson.loads(json_flow_with_prompt_and_history)
    data = flow["data"]
    flow = FlowCreate(name="Basic Chat", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    return response.json()


@pytest.fixture
def added_flow_chat_input(client, json_chat_input, logged_in_headers):
    flow = orjson.loads(json_chat_input)
    data = flow["data"]
    flow = FlowCreate(name="Chat Input", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    return response.json()


@pytest.fixture
def added_flow_two_outputs(client, json_two_outputs, logged_in_headers):
    flow = orjson.loads(json_two_outputs)
    data = flow["data"]
    flow = FlowCreate(name="Two Outputs", description="description", data=data)
    response = client.post("api/v1/flows/", json=flow.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    return response.json()


@pytest.fixture
def added_vector_store(client, json_vector_store, logged_in_headers):
    vector_store = orjson.loads(json_vector_store)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Vector Store", description="description", data=data)
    response = client.post("api/v1/flows/", json=vector_store.dict(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == vector_store.name
    assert response.json()["data"] == vector_store.data
    return response.json()


@pytest.fixture
def created_api_key(active_user):
    hashed = get_password_hash("random_key")
    api_key = ApiKey(
        name="test_api_key",
        user_id=active_user.id,
        api_key="random_key",
        hashed_api_key=hashed,
    )
    db_manager = get_db_service()
    with session_getter(db_manager) as session:
        if existing_api_key := session.exec(select(ApiKey).where(ApiKey.api_key == api_key.api_key)).first():
            return existing_api_key
        session.add(api_key)
        session.commit()
        session.refresh(api_key)
    return api_key


@pytest.fixture(name="starter_project")
def get_starter_project(active_user):
    # once the client is created, we can get the starter project
    with session_getter(get_db_service()) as session:
        flow = session.exec(
            select(Flow)
            .where(Flow.folder.has(Folder.name == STARTER_FOLDER_NAME))
            .where(Flow.name == "Basic Prompting (Hello, World)")
        ).first()
        if not flow:
            raise ValueError("No starter project found")

        new_flow_create = FlowCreate(
            name=flow.name,
            description=flow.description,
            data=flow.data,
            user_id=active_user.id,
        )
        new_flow = Flow.model_validate(new_flow_create, from_attributes=True)
        session.add(new_flow)
        session.commit()
        session.refresh(new_flow)
        new_flow_dict = new_flow.model_dump()
    return new_flow_dict
