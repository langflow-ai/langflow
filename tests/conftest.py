import json
from pathlib import Path
from typing import AsyncGenerator
from langflow.api.v1.flows import get_session

from langflow.graph.graph.base import Graph
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlmodel import SQLModel, Session, create_engine
from sqlmodel.pool import StaticPool


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
@pytest.fixture(scope="module")
def client():
    from langflow.main import create_app

    app = create_app()

    with TestClient(app) as client:
        yield client


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


@pytest.fixture(name="session")  #
def session_fixture():  #
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")  #
def client_fixture(session: Session):  #
    def get_session_override():  #
        return session

    from langflow.main import create_app

    app = create_app()

    app.dependency_overrides[get_session] = get_session_override  #

    yield TestClient(app)
    app.dependency_overrides.clear()  #
