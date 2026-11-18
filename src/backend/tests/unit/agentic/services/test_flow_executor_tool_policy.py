"""Assistant tools are checked against the Assistant's own flow, not the user's open flow."""

import asyncio
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from langflow.agentic.services.flow_executor import _run_graph_with_events, execute_flow_file
from langflow.agentic.services.flow_types import FlowExecutionResult
from langflow.services.auth.service import AuthService
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from lfx.custom import Component
from lfx.events.event_manager import create_default_event_manager
from lfx.execution import reset_default_coordinator
from lfx.graph import Graph
from lfx.io import HandleInput, MessageTextInput, Output
from lfx.schema.message import Message
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

MODULE = "langflow.agentic.services.flow_executor"
TOOL_REFUSAL = "Tool settings changed"
TOOL_OUTPUTS: list[str] = []


class EchoTool(Component):
    display_name = "Echo Tool"
    inputs = [MessageTextInput(name="text", display_name="Text", tool_mode=True)]
    outputs = [Output(name="echo", display_name="Echo", method="echo")]

    def echo(self) -> Message:
        return Message(text=f"echo:{self.text}")


class ToolCaller(Component):
    display_name = "Tool Caller"
    inputs = [HandleInput(name="tools", display_name="Tools", input_types=["Tool"], is_list=True)]
    outputs = [Output(name="answer", display_name="Answer", method="answer")]

    async def answer(self) -> Message:
        output = str(await self.tools[0].ainvoke({"text": "hi"}))
        TOOL_OUTPUTS.append(output)
        return Message(text=output)


@pytest.fixture
async def stored_flows(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'assistant-tools.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda connection: SQLModel.metadata.create_all(connection, tables=[Flow.__table__, User.__table__])
        )
    user_id = uuid4()
    open_flow_id = uuid4()
    async with AsyncSession(engine) as session:
        session.add(User(id=user_id, username="assistant-user", password="", is_active=True))
        session.add(Flow(id=open_flow_id, name="user flow", user_id=user_id, data={"nodes": [], "edges": []}))
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
    reset_default_coordinator()
    TOOL_OUTPUTS.clear()
    try:
        yield str(user_id), str(open_flow_id)
    finally:
        reset_default_coordinator()
        await engine.dispose()


def _assistant_graph() -> Graph:
    tool = EchoTool(_id="EchoTool-1")
    tool._append_tool_to_outputs_map()
    caller = ToolCaller(_id="ToolCaller-1")
    caller.set(tools=tool.to_toolkit)
    return Graph(start=tool, end=caller)


async def test_assistant_tool_runs_when_the_user_flow_does_not_contain_it(stored_flows):
    user_id, open_flow_id = stored_flows
    with (
        patch(f"{MODULE}.resolve_flow_path", return_value=(Path("Assistant.json"), "json")),
        patch(f"{MODULE}.load_graph_for_execution", new_callable=AsyncMock, return_value=_assistant_graph()),
    ):
        await execute_flow_file(
            "Assistant.json", input_value="go", global_variables={"FLOW_ID": open_flow_id}, user_id=user_id
        )

    assert len(TOOL_OUTPUTS) == 1
    assert "echo:hi" in TOOL_OUTPUTS[0]


async def test_streamed_assistant_tool_runs_when_the_user_flow_does_not_contain_it(stored_flows):
    user_id, open_flow_id = stored_flows
    graph = _assistant_graph()
    execution_result = FlowExecutionResult()
    queue: asyncio.Queue = asyncio.Queue()

    await _run_graph_with_events(
        graph=graph,
        input_value="go",
        global_variables={"FLOW_ID": open_flow_id},
        user_id=user_id,
        session_id=None,
        event_manager=create_default_event_manager(asyncio.Queue()),
        event_queue=queue,
        execution_result=execution_result,
    )

    assert execution_result.error is None
    assert graph.flow_id == open_flow_id
    assert len(TOOL_OUTPUTS) == 1
    assert "echo:hi" in TOOL_OUTPUTS[0]


async def test_a_stored_flow_run_still_refuses_a_tool_missing_from_the_stored_flow(stored_flows):
    user_id, open_flow_id = stored_flows
    graph = _assistant_graph()
    graph.flow_id = open_flow_id
    graph.user_id = user_id

    async for _ in graph.async_start():
        pass

    assert len(TOOL_OUTPUTS) == 1
    assert TOOL_REFUSAL in TOOL_OUTPUTS[0]


def test_graph_copies_keep_the_assistant_tool_policy_source() -> None:
    graph = _assistant_graph()
    graph.runs_stored_flow = False

    assert deepcopy(graph).runs_stored_flow is False
    assert graph.copy_for_run(user_id=None).runs_stored_flow is False
    restored = Graph.__new__(Graph)
    restored.__setstate__(graph.__getstate__())
    assert restored.runs_stored_flow is False
