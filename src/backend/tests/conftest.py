import asyncio
import json
import shutil

# we need to import tmpdir
import tempfile
from collections.abc import AsyncGenerator
from contextlib import suppress
from pathlib import Path
from uuid import UUID

import anyio
import orjson
import pytest
from asgi_lifespan import LifespanManager
from blockbuster import blockbuster_ctx
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.main import create_app
from langflow.services.auth.utils import get_password_hash
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow, FlowCreate
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.user.model import User, UserCreate, UserRead
from langflow.services.database.models.vertex_builds.crud import delete_vertex_builds_by_flow_id
from langflow.services.database.utils import session_getter
from langflow.services.deps import get_db_service, session_scope
from loguru import logger
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.pool import StaticPool
from typer.testing import CliRunner

from lfx.components.input_output import ChatInput
from lfx.graph import Graph
from tests.api_keys import get_openai_api_key

load_dotenv()


# TODO: Revert this to True once bb.functions[func].can_block_in("http/client.py", "_safe_read") is fixed
@pytest.fixture(autouse=False)
def blockbuster(request):
    if "benchmark" in request.keywords or "no_blockbuster" in request.keywords:
        yield
    else:
        with blockbuster_ctx() as bb:
            for func in [
                "io.BufferedReader.read",
                "io.BufferedWriter.write",
                "io.TextIOWrapper.read",
                "io.TextIOWrapper.write",
                "os.mkdir",
                "os.stat",
                "os.path.abspath",
            ]:
                bb.functions[func].can_block_in("settings/service.py", "initialize")
            for func in [
                "io.BufferedReader.read",
                "io.TextIOWrapper.read",
            ]:
                bb.functions[func].can_block_in("importlib_metadata/__init__.py", "metadata")
                # bb.functions[func].can_block_in("http/client.py", "_safe_read")

            (
                bb.functions["os.stat"]
                # TODO: make set_class_code async
                .can_block_in("langflow/custom/custom_component/component.py", "set_class_code")
                # TODO: follow discussion in https://github.com/encode/httpx/discussions/3456
                .can_block_in("httpx/_client.py", "_init_transport")
                .can_block_in("rich/traceback.py", "_render_stack")
                .can_block_in("langchain_core/_api/internal.py", "is_caller_internal")
                .can_block_in("langchain_core/runnables/utils.py", "get_function_nonlocals")
                .can_block_in("alembic/versions", "_load_revisions")
                .can_block_in("dotenv/main.py", "find_dotenv")
                .can_block_in("alembic/script/base.py", "_load_revisions")
                .can_block_in("alembic/env.py", "_do_run_migrations")
            )

            for func in ["os.stat", "os.path.abspath", "os.scandir", "os.listdir"]:
                bb.functions[func].can_block_in("alembic/util/pyfiles.py", "load_python_file")
                bb.functions[func].can_block_in("dotenv/main.py", "find_dotenv")
                bb.functions[func].can_block_in("pkgutil.py", "_iter_file_finder_modules")

            for func in ["os.path.abspath", "os.scandir"]:
                bb.functions[func].can_block_in("alembic/script/base.py", "_load_revisions")

            # Add os.stat to alembic/script/base.py _load_revisions
            bb.functions["os.stat"].can_block_in("alembic/script/base.py", "_load_revisions")

            (
                bb.functions["os.path.abspath"]
                .can_block_in("loguru/_better_exceptions.py", {"_get_lib_dirs", "_format_exception"})
                .can_block_in("sqlalchemy/dialects/sqlite/pysqlite.py", "create_connect_args")
                .can_block_in("botocore/__init__.py", "__init__")
            )

            bb.functions["socket.socket.connect"].can_block_in("urllib3/connection.py", "_new_conn")
            bb.functions["ssl.SSLSocket.send"].can_block_in("ssl.py", "sendall")
            bb.functions["ssl.SSLSocket.read"].can_block_in("ssl.py", "recv_into")

            yield bb


def pytest_configure(config):
    config.addinivalue_line("markers", "noclient: don't create a client for this test")
    config.addinivalue_line("markers", "load_flows: load the flows for this test")
    config.addinivalue_line("markers", "api_key_required: run only if the api key is set in the environment variables")
    data_path = Path(__file__).parent.absolute() / "data"

    pytest.BASIC_EXAMPLE_PATH = data_path / "basic_example.json"
    pytest.COMPLEX_EXAMPLE_PATH = data_path / "complex_example.json"
    pytest.OPENAPI_EXAMPLE_PATH = data_path / "Openapi.json"
    pytest.GROUPED_CHAT_EXAMPLE_PATH = data_path / "grouped_chat.json"
    pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH = data_path / "one_group_chat.json"
    pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH = data_path / "vector_store_grouped.json"
    pytest.WEBHOOK_TEST = data_path / "WebhookTest.json"

    pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY = data_path / "BasicChatwithPromptandHistory.json"
    pytest.CHAT_INPUT = data_path / "ChatInputTest.json"
    pytest.TWO_OUTPUTS = data_path / "TwoOutputsTest.json"
    pytest.VECTOR_STORE_PATH = data_path / "Vector_store.json"
    pytest.SIMPLE_API_TEST = data_path / "SimpleAPITest.json"
    pytest.MEMORY_CHATBOT_NO_LLM = data_path / "MemoryChatbotNoLLM.json"
    pytest.ENV_VARIABLE_TEST = data_path / "env_variable_test.json"
    pytest.LOOP_TEST = data_path / "LoopTest.json"
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
        pytest.MEMORY_CHATBOT_NO_LLM,
        pytest.LOOP_TEST,
    ]:
        assert path.exists(), f"File {path} does not exist. Available files: {list(data_path.iterdir())}"


async def delete_transactions_by_flow_id(db: AsyncSession, flow_id: UUID):
    if not flow_id:
        return
    stmt = select(TransactionTable).where(TransactionTable.flow_id == flow_id)
    transactions = await db.exec(stmt)
    for transaction in transactions:
        await db.delete(transaction)


async def _delete_transactions_and_vertex_builds(session, flows: list[Flow]):
    flow_ids = [flow.id for flow in flows]
    for flow_id in flow_ids:
        if not flow_id:
            continue
        try:
            await delete_vertex_builds_by_flow_id(session, flow_id)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error deleting vertex builds for flow {flow_id}: {e}")
        try:
            await delete_transactions_by_flow_id(session, flow_id)
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error deleting transactions for flow {flow_id}: {e}")


@pytest.fixture
def caplog(caplog: pytest.LogCaptureFixture):
    handler_id = logger.add(
        caplog.handler,
        format="{message}",
        level=0,
        filter=lambda record: record["level"].no >= caplog.handler.level,
        enqueue=False,  # Set to 'True' if your test is spawning child processes.
    )
    yield caplog
    logger.remove(handler_id)


@pytest.fixture
async def async_client() -> AsyncGenerator:
    app = create_app()
    async with AsyncClient(app=app, base_url="http://testserver", http2=True) as client:
        yield client


@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    SQLModel.metadata.drop_all(engine)  # Add this line to clean up tables


@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)


class Config:
    broker_url = "redis://localhost:6379/0"
    result_backend = "redis://localhost:6379/0"


@pytest.fixture(name="load_flows_dir")
def load_flows_dir():
    with tempfile.TemporaryDirectory() as tempdir:
        yield tempdir


@pytest.fixture(name="distributed_env")
def _setup_env(monkeypatch):
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
def distributed_client_fixture(
    session: Session,  # noqa: ARG001
    monkeypatch,
    distributed_env,  # noqa: ARG001
):
    # Here we load the .env from ../deploy/.env
    from langflow.core import celery_app

    db_dir = tempfile.mkdtemp()
    try:
        db_path = Path(db_dir) / "test.db"
        monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
        monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
        # monkeypatch langflow.services.task.manager.USE_CELERY to True
        # monkeypatch.setattr(manager, "USE_CELERY", True)
        monkeypatch.setattr(celery_app, "celery_app", celery_app.make_celery("langflow", Config))

        # def get_session_override():
        #     return session

        app = create_app()

        # app.dependency_overrides[get_session] = get_session_override
        with TestClient(app) as client:
            yield client
    finally:
        shutil.rmtree(db_dir)  # Clean up the temporary directory
    app.dependency_overrides.clear()
    monkeypatch.undo()


def get_graph(type_="basic"):
    """Get a graph from a json file."""
    if type_ == "basic":
        path = pytest.BASIC_EXAMPLE_PATH
    elif type_ == "complex":
        path = pytest.COMPLEX_EXAMPLE_PATH
    elif type_ == "openapi":
        path = pytest.OPENAPI_EXAMPLE_PATH

    with path.open(encoding="utf-8") as f:
        flow_graph = json.load(f)
    data_graph = flow_graph["data"]
    nodes = data_graph["nodes"]
    edges = data_graph["edges"]
    graph = Graph()
    graph.add_nodes_and_edges(nodes, edges)
    return graph


@pytest.fixture
def basic_graph_data():
    with pytest.BASIC_EXAMPLE_PATH.open(encoding="utf-8") as f:
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
    return pytest.BASIC_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def grouped_chat_json_flow():
    return pytest.GROUPED_CHAT_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def one_grouped_chat_json_flow():
    return pytest.ONE_GROUPED_CHAT_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def vector_store_grouped_json_flow():
    return pytest.VECTOR_STORE_GROUPED_EXAMPLE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def json_flow_with_prompt_and_history():
    return pytest.BASIC_CHAT_WITH_PROMPT_AND_HISTORY.read_text(encoding="utf-8")


@pytest.fixture
def json_simple_api_test():
    return pytest.SIMPLE_API_TEST.read_text(encoding="utf-8")


@pytest.fixture
def json_vector_store():
    return pytest.VECTOR_STORE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def json_webhook_test():
    return pytest.WEBHOOK_TEST.read_text(encoding="utf-8")


@pytest.fixture
def json_memory_chatbot_no_llm():
    return pytest.MEMORY_CHATBOT_NO_LLM.read_text(encoding="utf-8")


@pytest.fixture
def json_loop_test():
    return pytest.LOOP_TEST.read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def deactivate_tracing(monkeypatch):
    monkeypatch.setenv("LANGFLOW_DEACTIVATE_TRACING", "true")
    yield
    monkeypatch.undo()


@pytest.fixture
def use_noop_session(monkeypatch):
    monkeypatch.setenv("LANGFLOW_USE_NOOP_DATABASE", "1")
    # Optionally patch the Settings object if needed
    # from langflow.services.settings.base import Settings
    # monkeypatch.setattr(Settings, "use_noop_database", True)
    yield
    monkeypatch.undo()


@pytest.fixture(name="client")
async def client_fixture(
    session: Session,  # noqa: ARG001
    monkeypatch,
    request,
    load_flows_dir,
):
    # Set the database url to a test database
    if "noclient" in request.keywords:
        yield
    else:

        def init_app():
            db_dir = tempfile.mkdtemp()
            db_path = Path(db_dir) / "test.db"
            monkeypatch.setenv("LANGFLOW_DATABASE_URL", f"sqlite:///{db_path}")
            monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "false")
            if "load_flows" in request.keywords:
                shutil.copyfile(
                    pytest.BASIC_EXAMPLE_PATH, Path(load_flows_dir) / "c54f9130-f2fa-4a3e-b22a-3856d946351b.json"
                )
                monkeypatch.setenv("LANGFLOW_LOAD_FLOWS_PATH", load_flows_dir)
                monkeypatch.setenv("LANGFLOW_AUTO_LOGIN", "true")
            # Clear the services cache
            from langflow.services.manager import service_manager

            service_manager.factories.clear()
            service_manager.services.clear()  # Clear the services cache
            app = create_app()
            db_service = get_db_service()
            db_service.database_url = f"sqlite:///{db_path}"
            db_service.reload_engine()
            return app, db_path

        app, db_path = await asyncio.to_thread(init_app)
        # app.dependency_overrides[get_session] = get_session_override
        async with (
            LifespanManager(app, startup_timeout=None, shutdown_timeout=None) as manager,
            AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://testserver/", http2=True) as client,
        ):
            yield client
        # app.dependency_overrides.clear()
        monkeypatch.undo()
        # clear the temp db
        with suppress(FileNotFoundError):
            await anyio.Path(db_path).unlink()


@pytest.fixture
def runner(tmp_path):
    env = {"LANGFLOW_DATABASE_URL": f"sqlite:///{tmp_path}/test.db"}
    return CliRunner(env=env)


@pytest.fixture
async def test_user(client):
    user_data = UserCreate(
        username="testuser",
        password="testpassword",  # noqa: S106
    )
    response = await client.post("api/v1/users/", json=user_data.model_dump())
    assert response.status_code == 201
    user = response.json()
    yield user
    # Clean up
    await client.delete(f"/api/v1/users/{user['id']}")


@pytest.fixture
async def active_user(client):  # noqa: ARG001
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        user = User(
            username="activeuser",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=False,
        )
        stmt = select(User).where(User.username == user.username)
        if active_user := (await session.exec(stmt)).first():
            user = active_user
        else:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)
    yield user
    # Clean up
    # Now cleanup transactions, vertex_build
    try:
        async with db_manager.with_session() as session:
            user = await session.get(User, user.id, options=[selectinload(User.flows)])
            await _delete_transactions_and_vertex_builds(session, user.flows)
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error deleting transactions and vertex builds for user: {e}")

    try:
        async with db_manager.with_session() as session:
            user = await session.get(User, user.id)
            await session.delete(user)
            await session.commit()
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Error deleting user: {e}")


@pytest.fixture
async def logged_in_headers(client, active_user):
    login_data = {"username": active_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
async def active_super_user(client):  # noqa: ARG001
    db_manager = get_db_service()
    async with db_manager.with_session() as session:
        user = User(
            username="activeuser",
            password=get_password_hash("testpassword"),
            is_active=True,
            is_superuser=True,
        )
        stmt = select(User).where(User.username == user.username)
        if active_user := (await session.exec(stmt)).first():
            user = active_user
        else:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        user = UserRead.model_validate(user, from_attributes=True)
    yield user
    # Clean up
    # Now cleanup transactions, vertex_build
    async with db_manager.with_session() as session:
        user = await session.get(User, user.id, options=[selectinload(User.flows)])
        await _delete_transactions_and_vertex_builds(session, user.flows)
        await session.delete(user)

        await session.commit()


@pytest.fixture
async def logged_in_headers_super_user(client, active_super_user):
    login_data = {"username": active_super_user.username, "password": "testpassword"}
    response = await client.post("api/v1/login", data=login_data)
    assert response.status_code == 200
    tokens = response.json()
    a_token = tokens["access_token"]
    return {"Authorization": f"Bearer {a_token}"}


@pytest.fixture
async def flow(
    client,  # noqa: ARG001
    json_flow: str,
    active_user,
):
    loaded_json = json.loads(json_flow)
    flow_data = FlowCreate(name="test_flow", data=loaded_json.get("data"), user_id=active_user.id)

    flow = Flow.model_validate(flow_data)
    async with session_getter(get_db_service()) as session:
        session.add(flow)
        await session.commit()
        await session.refresh(flow)
        yield flow
        # Clean up
        await session.delete(flow)
        await session.commit()


@pytest.fixture
def json_chat_input():
    return pytest.CHAT_INPUT.read_text(encoding="utf-8")


@pytest.fixture
def json_two_outputs():
    return pytest.TWO_OUTPUTS.read_text(encoding="utf-8")


@pytest.fixture
async def added_flow_webhook_test(client, json_webhook_test, logged_in_headers):
    flow = orjson.loads(json_webhook_test)
    data = flow["data"]
    flow = FlowCreate(name="Basic Chat", description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def added_flow_chat_input(client, json_chat_input, logged_in_headers):
    flow = orjson.loads(json_chat_input)
    data = flow["data"]
    flow = FlowCreate(name="Chat Input", description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def added_flow_two_outputs(client, json_two_outputs, logged_in_headers):
    flow = orjson.loads(json_two_outputs)
    data = flow["data"]
    flow = FlowCreate(name="Two Outputs", description="description", data=data)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == flow.name
    assert response.json()["data"] == flow.data
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def added_vector_store(client, json_vector_store, logged_in_headers):
    vector_store = orjson.loads(json_vector_store)
    data = vector_store["data"]
    vector_store = FlowCreate(name="Vector Store", description="description", data=data)
    response = await client.post("api/v1/flows/", json=vector_store.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == vector_store.name
    assert response.json()["data"] == vector_store.data
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def added_webhook_test(client, json_webhook_test, logged_in_headers):
    webhook_test = orjson.loads(json_webhook_test)
    data = webhook_test["data"]
    webhook_test = FlowCreate(
        name="Webhook Test", description="description", data=data, endpoint_name=webhook_test["endpoint_name"]
    )
    response = await client.post("api/v1/flows/", json=webhook_test.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    assert response.json()["name"] == webhook_test.name
    assert response.json()["data"] == webhook_test.data
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def flow_component(client: AsyncClient, logged_in_headers):
    chat_input = ChatInput()
    graph = Graph(start=chat_input, end=chat_input)
    graph_dict = graph.dump(name="Chat Input Component")
    flow = FlowCreate(**graph_dict)
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture
async def created_api_key(active_user):
    hashed = get_password_hash("random_key")
    api_key = ApiKey(
        name="test_api_key",
        user_id=active_user.id,
        api_key="random_key",
        hashed_api_key=hashed,
    )
    db_manager = get_db_service()
    async with session_getter(db_manager) as session:
        stmt = select(ApiKey).where(ApiKey.api_key == api_key.api_key)
        if existing_api_key := (await session.exec(stmt)).first():
            yield existing_api_key
            return
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)
        yield api_key
        # Clean up
        await session.delete(api_key)
        await session.commit()


@pytest.fixture(name="simple_api_test")
async def get_simple_api_test(client, logged_in_headers, json_simple_api_test):
    # Once the client is created, we can get the starter project
    # Just create a new flow with the simple api test
    flow = orjson.loads(json_simple_api_test)
    data = flow["data"]
    flow = FlowCreate(name="Simple API Test", data=data, description="Simple API Test")
    response = await client.post("api/v1/flows/", json=flow.model_dump(), headers=logged_in_headers)
    assert response.status_code == 201
    yield response.json()
    await client.delete(f"api/v1/flows/{response.json()['id']}", headers=logged_in_headers)


@pytest.fixture(name="starter_project")
async def get_starter_project(client, active_user):  # noqa: ARG001
    # once the client is created, we can get the starter project
    async with session_scope() as session:
        stmt = (
            select(Flow)
            .where(Flow.folder.has(Folder.name == STARTER_FOLDER_NAME))
            .where(Flow.name == "Basic Prompting")
        )
        flow = (await session.exec(stmt)).first()
        if not flow:
            msg = "No starter project found"
            raise ValueError(msg)

        # ensure openai api key is set
        openai_api_key = get_openai_api_key()
        data_as_json = json.dumps(flow.data)
        data_as_json = data_as_json.replace("OPENAI_API_KEY", openai_api_key)
        # also replace `"load_from_db": true` with `"load_from_db": false`
        if '"load_from_db": true' in data_as_json:
            data_as_json = data_as_json.replace('"load_from_db": true', '"load_from_db": false')
        if '"load_from_db": true' in data_as_json:
            msg = "load_from_db should be false"
            raise ValueError(msg)
        flow.data = json.loads(data_as_json)

        new_flow_create = FlowCreate(
            name=flow.name,
            description=flow.description,
            data=flow.data,
            user_id=active_user.id,
        )
        new_flow = Flow.model_validate(new_flow_create, from_attributes=True)
        session.add(new_flow)
        await session.commit()
        await session.refresh(new_flow)
        new_flow_dict = new_flow.model_dump()
        yield new_flow_dict
        # Clean up
        await session.delete(new_flow)
        await session.commit()
