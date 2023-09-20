from contextlib import contextmanager
import json
from pathlib import Path
from typing import AsyncGenerator, TYPE_CHECKING

from langflow.graph.graph.base import Graph
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.flow.flow import Flow
from langflow.services.database.models.user.user import User, UserCreate
from langflow.services.database.utils import session_getter
from langflow.services.getters import get_db_manager
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool
from typer.testing import CliRunner

# we need to import tmpdir
import tempfile

if TYPE_CHECKING:
    from langflow.services.database.manager import DatabaseManager


def pytest_configure():
    pytest.BASIC_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "basic_example.json"
    )
    pytest.COMPLEX_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "complex_example.json"
    )
    pytest.OPENAPI_EXAMPLE_PATH = (
        Path(__file__).parent.absolute() / "data" / "Openapi.json"
    )

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


# Create client fixture for FastAPI
# @pytest.fixture(scope="module", autouse=True)
# def client():
#     from langflow.main import create_app

#     app = create_app()

#     with TestClient(app) as client:
#         yield client


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


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client", autouse=True)
def client_fixture(session: Session, monkeypatch):
    # Set the database url to a test database
    db_dir = tempfile.mkdtemp()
    db_path = Path(db_dir) / "test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
    # monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", 1)

    def get_session_override():
        return session

    from langflow.main import create_app

    app = create_app()

    # app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    # app.dependency_overrides.clear()
    monkeypatch.undo()
    # clear the temp db
    db_path.unlink()


# @contextmanager
# def session_getter():
#     try:
#         session = Session(engine)
#         yield session
#     except Exception as e:
#         print("Session rollback because of exception:", e)
#         session.rollback()
#         raise
#     finally:
#         session.close()


# create a fixture for session_getter above
@pytest.fixture(name="session_getter")
def session_getter_fixture(client):
    @contextmanager
    def blank_session_getter(db_manager: "DatabaseManager"):
        with Session(db_manager.engine) as session:
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
    db_manager = get_db_manager()
    with session_getter(db_manager) as session:
        user = User(
            username="activeuser",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
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
    from langflow.services.database.models.flow.flow import FlowCreate

    loaded_json = json.loads(json_flow)
    flow_data = FlowCreate(
        name="test_flow", data=loaded_json.get("data"), user_id=active_user.id
    )
    flow = Flow(**flow_data.dict())
    with session_getter(get_db_manager()) as session:
        session.add(flow)
        session.commit()
        session.refresh(flow)

    return flow
