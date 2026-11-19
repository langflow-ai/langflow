"""Running tools and message writes honor native user deactivation."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from fastapi import HTTPException
from langchain_core.tools import BaseTool, StructuredTool, ToolException
from langflow.memory import aadd_messagetables, aupdate_messages
from langflow.schema.message import Message
from langflow.services.auth.service import AuthService
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.database.models.user.model import User
from lfx.base.tools.component_tool import _build_output_async_function, _build_output_function
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import Output
from lfx.memory.flow_context import (
    get_current_message_execution_principal,
    reset_current_flow_id,
    reset_current_message_execution_principal,
    reset_current_message_executor_id,
    reset_current_message_owner_id,
    set_current_flow_id,
    set_current_message_execution_principal,
    set_current_message_executor_id,
    set_current_message_owner_id,
)
from lfx.services.authorization.base import PUBLIC_ANONYMOUS_ACTOR_ID, ExecutionPrincipal
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def native_auth(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'execution.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda connection: SQLModel.metadata.create_all(
                connection, tables=[User.__table__, MessageTable.__table__, Flow.__table__]
            )
        )
    user_id = uuid4()
    async with AsyncSession(engine) as session:
        session.add(User(id=user_id, username="runner", password="", is_active=True))
        await session.commit()

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    auth = AuthService(SimpleNamespace())
    monkeypatch.setattr("langflow.services.auth.service.session_scope", scope)
    monkeypatch.setattr(
        "langflow.services.auth.service.get_db_service",
        lambda: SimpleNamespace(session_scope_for_sync_validation=scope),
    )
    monkeypatch.setattr("lfx.services.deps.get_auth_service", lambda: auth)
    monkeypatch.setattr("langflow.services.deps.get_auth_service", lambda: auth)
    try:
        yield auth, user_id, scope
    finally:
        await engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_tool_rechecks_user_after_it_was_built(native_auth, asynchronous):
    _auth, user_id, scope = native_auth
    effects = []

    class CountingTool(Component):
        outputs = [Output(name="result", display_name="Result", method="perform")]

        def perform(self) -> str:
            effects.append("called")
            return "ok"

        async def aperform(self) -> str:
            return self.perform()

    component = CountingTool()
    component.set_vertex(SimpleNamespace(graph=Graph(user_id=str(user_id))))
    component.graph.execution_principal = ExecutionPrincipal(kind="actor", user_id=str(user_id), actor_id=str(user_id))
    if asynchronous:
        call = _build_output_async_function(component, component.aperform)
        assert await call() == "ok"
    else:
        call = _build_output_function(component, component.perform)
        assert call() == "ok"
    assert effects == ["called"]

    async with scope() as session:
        user = await session.get(User, user_id)
        user.is_active = False
        session.add(user)
        await session.commit()

    if asynchronous:
        with pytest.raises(ToolException, match="inactive"):
            await call()
    else:
        with pytest.raises(ToolException, match="inactive"):
            call()
    assert effects == ["called"]


@pytest.mark.parametrize("operation", ["insert", "update"])
async def test_message_commit_rechecks_the_executor_in_its_write_session(native_auth, operation, monkeypatch):
    _auth, user_id, scope = native_auth
    monkeypatch.setattr("langflow.memory.session_scope", scope)
    async with scope() as session:
        user = await session.get(User, user_id)
        user.is_active = False
        session.add(user)
        await session.commit()
    flow_token = set_current_flow_id(uuid4())
    executor_token = set_current_message_executor_id(user_id)
    owner_token = set_current_message_owner_id(user_id)
    try:
        async with scope() as session:
            if operation == "insert":
                with pytest.raises(HTTPException, match="inactive"):
                    await aadd_messagetables(
                        [MessageTable(text="blocked", sender="Machine", sender_name="AI")], session
                    )
            else:
                with pytest.raises(HTTPException, match="inactive"):
                    await aupdate_messages(Message(id=uuid4(), text="blocked"))
    finally:
        reset_current_message_owner_id(owner_token)
        reset_current_message_executor_id(executor_token)
        reset_current_flow_id(flow_token)
    async with scope() as session:
        assert (await session.exec(select(MessageTable))).all() == []


async def test_deleted_execution_user_is_rejected(native_auth):
    auth, _user_id, _scope = native_auth
    with pytest.raises(HTTPException, match="no longer exists"):
        await auth.validate_execution_user(uuid4())


async def test_inactive_actor_cannot_keep_using_an_active_owners_credentials(native_auth):
    auth, user_id, scope = native_auth
    actor_id = uuid4()
    async with scope() as session:
        session.add(User(id=actor_id, username="actor", password="", is_active=False))
        await session.commit()
    with pytest.raises(HTTPException, match="inactive"):
        await auth.validate_execution_user(
            user_id,
            principal=ExecutionPrincipal(kind="flow_owner", user_id=str(user_id), actor_id=str(actor_id)),
        )


async def test_public_marker_only_skips_native_lookup_with_its_trusted_principal(native_auth):
    auth, _user_id, _scope = native_auth
    public = ExecutionPrincipal(kind="anonymous_public", actor_id=str(PUBLIC_ANONYMOUS_ACTOR_ID))
    await auth.validate_execution_user(PUBLIC_ANONYMOUS_ACTOR_ID, principal=public)
    with pytest.raises(HTTPException, match="no longer exists"):
        await auth.validate_execution_user(PUBLIC_ANONYMOUS_ACTOR_ID)
    with pytest.raises(HTTPException, match="no longer exists"):
        await auth.validate_execution_user(
            PUBLIC_ANONYMOUS_ACTOR_ID,
            principal=ExecutionPrincipal(kind="actor", user_id=str(PUBLIC_ANONYMOUS_ACTOR_ID)),
        )
    with pytest.raises(HTTPException, match="no longer exists"):
        await auth.validate_execution_user(uuid4(), principal=public)


async def test_public_chat_graph_remains_executable_and_ephemeral(native_auth, monkeypatch):
    _auth, _user_id, scope = native_auth
    monkeypatch.setattr("langflow.memory.session_scope", scope)
    chat_input = ChatInput(_id="chat_input")
    chat_input.set(input_value="public chat still works")
    chat_output = ChatOutput(_id="chat_output")
    chat_output.set(input_value=chat_input.message_response)
    graph = Graph(chat_input, chat_output, flow_id=str(uuid4()), user_id=str(PUBLIC_ANONYMOUS_ACTOR_ID))
    graph.execution_principal = ExecutionPrincipal(kind="anonymous_public", actor_id=str(PUBLIC_ANONYMOUS_ACTOR_ID))
    graph.session_id = "public-session"
    assert get_current_message_execution_principal() is None
    async for _ in graph.async_start():
        pass
    assert get_current_message_execution_principal() is None
    async with scope() as session:
        messages = (await session.exec(select(MessageTable))).all()
    rendered = chat_output.get_output_by_method(chat_output.message_response).value
    assert rendered.text == "public chat still works"
    assert messages == []


async def test_message_guard_receives_the_trusted_public_principal(native_auth):
    _auth, _user_id, scope = native_auth
    flow_token = set_current_flow_id(uuid4())
    executor_token = set_current_message_executor_id(PUBLIC_ANONYMOUS_ACTOR_ID)
    principal_token = set_current_message_execution_principal(
        ExecutionPrincipal(kind="anonymous_public", actor_id=str(PUBLIC_ANONYMOUS_ACTOR_ID))
    )
    try:
        async with scope() as session:
            await aadd_messagetables(
                [
                    MessageTable(
                        text="public",
                        sender="Machine",
                        sender_name="AI",
                        session_id="public",
                        user_id=PUBLIC_ANONYMOUS_ACTOR_ID,
                    )
                ],
                session,
            )
    finally:
        reset_current_message_execution_principal(principal_token)
        reset_current_message_executor_id(executor_token)
        reset_current_flow_id(flow_token)


@pytest.mark.parametrize("tool_kind", ["generated", "structured", "base"])
@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("identity", ["native", "public"])
async def test_all_toolkit_paths_recheck_native_lifecycle(native_auth, tool_kind, asynchronous, identity):
    _auth, user_id, scope = native_auth
    effects = []

    class CountingTool(Component):
        outputs = [Output(name="result", display_name="Result", method="aperform" if asynchronous else "perform")]

        def perform(self) -> str:
            effects.append("called")
            return "ok"

        async def aperform(self) -> str:
            return self.perform()

        async def _get_tools(self):
            if tool_kind == "generated":
                return await super()._get_tools()
            if tool_kind == "structured":
                return [
                    StructuredTool.from_function(
                        func=self.perform,
                        coroutine=self.aperform if asynchronous else None,
                        name="perform",
                        description="Count an invocation",
                        tags=["perform"],
                        handle_tool_error=True,
                    )
                ]

            class NativeTool(BaseTool):
                name: str = "perform"
                description: str = "Count an invocation"

                def _run(self) -> str:
                    effects.append("called")
                    return "ok"

                async def _arun(self) -> str:
                    return self._run()

            return [NativeTool(tags=["perform"], handle_tool_error=True)]

    flow_id = uuid4()
    executor = user_id if identity == "native" else PUBLIC_ANONYMOUS_ACTOR_ID
    graph = Graph(flow_id=str(flow_id), user_id=str(executor))
    graph.execution_principal = (
        ExecutionPrincipal(kind="actor", user_id=str(user_id), actor_id=str(user_id))
        if identity == "native"
        else ExecutionPrincipal(kind="anonymous_public", actor_id=str(executor))
    )
    component = CountingTool(_id="counter")
    component.set_vertex(SimpleNamespace(graph=graph))
    original = (await component._get_tools())[0]
    row = {"tags": list(original.tags), "name": original.name, "status": True, "approval_actions": []}
    component.tools_metadata = pd.DataFrame([row])
    tool = (await component.to_toolkit())[0]
    node = component.to_frontend_node()
    node["data"]["node"]["tool_mode"] = True
    node["data"]["node"]["template"]["tools_metadata"] = {"value": [row]}
    async with scope() as session:
        session.add(Flow(id=flow_id, name="tool lifecycle", user_id=user_id, data={"nodes": [node], "edges": []}))
        await session.commit()

    async def invoke():
        return await tool.ainvoke({}) if asynchronous else tool.invoke({})

    assert await invoke() == "ok"
    assert effects == ["called"]
    async with scope() as session:
        user = await session.get(User, user_id)
        user.is_active = False
        session.add(user)
        await session.commit()

    if identity == "public":
        assert await invoke() == "ok"
        assert effects == ["called", "called"]
    else:
        assert "inactive" in await invoke()
        assert effects == ["called"]
