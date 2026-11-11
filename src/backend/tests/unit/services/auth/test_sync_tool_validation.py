"""Synchronous tool checks use database connections owned by their event loop."""

import os
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.tools import StructuredTool, ToolException
from langflow.services.auth.service import AuthService
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from langflow.services.database.service import DatabaseService
from lfx.base.tools.component_tool import ComponentStructuredTool, _build_output_function
from lfx.base.tools.policy_tool import PolicyCheckedTool
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import Output
from lfx.services.auth.service import AuthService as LFXAuthService
from sqlalchemy import event, text
from sqlalchemy.engine import Engine
from sqlmodel import SQLModel


@pytest.fixture(params=["file", "memory", "postgres"])
async def validation_db(request, tmp_path, monkeypatch):
    kind = request.param
    if kind == "postgres":
        url = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not url:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
        connect_args = {"server_settings": {"application_name": "runtime-tool-validation"}}
    else:
        url = "sqlite+aiosqlite:///:memory:" if kind == "memory" else f"sqlite+aiosqlite:///{tmp_path / 'tool.db'}"
        connect_args = {"check_same_thread": False, "timeout": 2}
    pool_settings = {} if kind == "memory" else {"pool_size": 1, "max_overflow": 0, "pool_timeout": 0.2}
    settings = SimpleNamespace(
        database_url=url,
        database_connection_retry=False,
        db_connection_settings=pool_settings,
        db_driver_connection_settings=connect_args,
        model_fields_set=set(),
        sqlite_pragmas={"busy_timeout": 2000},
        use_noop_database=False,
        alembic_log_file="alembic.log",
        alembic_log_to_stdout=True,
    )
    database = DatabaseService(SimpleNamespace(settings=settings))
    async with database.engine.begin() as connection:
        await connection.run_sync(
            lambda connection: SQLModel.metadata.create_all(
                connection, tables=[User.__table__, Folder.__table__, Flow.__table__]
            )
        )
    user_id, flow_id = uuid4(), uuid4()
    row = {"tags": ["perform"], "name": "perform", "status": True, "approval_actions": []}
    node = {
        "id": "counter",
        "data": {"type": "Counter", "node": {"tool_mode": True, "template": {"tools_metadata": {"value": [row]}}}},
    }
    async with database._with_session() as session:
        session.add(User(id=user_id, username=f"runner-{user_id}", password="", is_active=True))
        session.add(Flow(id=flow_id, name="sync tool", user_id=user_id, data={"nodes": [node], "edges": []}))
        await session.commit()

    @asynccontextmanager
    async def scope():
        async with database._with_session() as session:
            yield session

    auth = AuthService(SimpleNamespace())
    monkeypatch.setattr("langflow.services.auth.service.session_scope", scope)
    monkeypatch.setattr("langflow.services.auth.service.get_db_service", lambda: database, raising=False)
    monkeypatch.setattr("lfx.services.deps.get_auth_service", lambda: auth)
    try:
        yield database, auth, user_id, flow_id, node, kind
    finally:
        await database.engine.dispose()
        event.remove(Engine, "connect", database.on_connection)


@pytest.mark.parametrize("tool_kind", ["generated", "structured", "external"])
@pytest.mark.parametrize("delegated", [False, True])
async def test_sync_tool_checks_do_not_borrow_the_async_pool(validation_db, tool_kind, delegated, monkeypatch):
    database, auth, user_id, flow_id, node, kind = validation_db
    effects = []
    checks = []

    class DelegatingAuthService(LFXAuthService):
        async def validate_execution_user(self, user_id, **kwargs):
            checks.append("lifecycle")
            await auth.validate_execution_user(user_id, **kwargs)

        async def validate_tool_call(self, **kwargs):
            checks.append("approval")
            await auth.validate_tool_call(**kwargs)

    if delegated:
        facade = DelegatingAuthService()
        monkeypatch.setattr("lfx.services.deps.get_auth_service", lambda: facade)

    class Counter(Component):
        outputs = [Output(name="result", display_name="Result", method="perform")]

        def perform(self) -> str:
            effects.append("called")
            return "ok"

    component = Counter(_id="counter")
    component.set_vertex(SimpleNamespace(graph=Graph(flow_id=str(flow_id), user_id=str(user_id))))
    checker = ComponentStructuredTool(
        source_component=component,
        name="perform",
        description="Count a call",
        func=lambda: effects.append("called") or "ok",
        args_schema={"type": "object", "properties": {}},
        tags=["perform"],
        metadata={"approval_actions": []},
    )
    checker.capture_policy()
    if tool_kind == "generated":
        call = _build_output_function(component, component.perform)
    elif tool_kind == "structured":

        def call():
            return checker.invoke({})
    else:
        original = StructuredTool.from_function(
            func=lambda: effects.append("called") or "ok", name="perform", description="Count a call"
        )
        tool = PolicyCheckedTool(original, checker.validate_runtime_authorization)

        def call():
            return tool.invoke({})

    assert call() == "ok"
    if kind == "memory":
        assert call() == "ok"
    else:
        # Holding the sole application connection forces any shared-pool check to fail.
        async with database.engine.connect():
            assert call() == "ok"
    assert effects == ["called", "called"]
    if delegated:
        assert "lifecycle" in checks
        if tool_kind != "generated":
            assert "approval" in checks

    async with database._with_session() as session:
        user = await session.get(User, user_id)
        user.is_active = False
        session.add(user)
        await session.commit()
    with pytest.raises(ToolException, match="inactive"):
        call()
    assert effects == ["called", "called"]

    async with database._with_session() as session:
        user = await session.get(User, user_id)
        user.is_active = True
        session.add(user)
        flow = await session.get(Flow, flow_id)
        node["data"]["node"]["template"]["tools_metadata"]["value"][0]["approval_actions"] = ["approve", "reject"]
        flow.data = {"nodes": [node], "edges": []}
        session.add(flow)
        await session.commit()
    if tool_kind != "generated":
        with pytest.raises(ToolException, match="settings changed"):
            call()
        assert effects == ["called", "called"]


async def test_sync_validation_closes_its_engine_before_its_loop(validation_db, monkeypatch):
    database, auth, user_id, _flow_id, _node, kind = validation_db
    if kind == "memory":
        pytest.skip("In-memory SQLite retains its original engine")
    created = []
    original_create = database._create_engine

    def create():
        engine = original_create()
        created.append(engine)
        return engine

    monkeypatch.setattr(database, "_create_engine", create)

    async def validate():
        from langflow.services.auth.service import _runtime_validation_scope

        async with _runtime_validation_scope() as session:
            await auth.validate_execution_user(user_id, db=session)
            if kind == "postgres":
                assert await session.scalar(text("SHOW application_name")) == "runtime-tool-validation"
            else:
                assert await session.scalar(text("PRAGMA busy_timeout")) == 2000

    for _ in range(2):
        auth.run_sync_validation(validate)
    assert len(created) == 2
    assert all(engine.pool.checkedout() == 0 and engine.pool.checkedin() == 0 for engine in created)
    assert database.engine.pool.checkedout() == 0
    assert all(engine.pool.size() == database.engine.pool.size() == 1 for engine in created)
    await auth.validate_execution_user(user_id)
