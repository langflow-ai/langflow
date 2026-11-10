"""A saved flow can tighten tool settings after an agent was built."""

from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, StructuredTool
from langflow.services.auth.service import AuthService
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.user.model import User
from lfx.base.tools.component_tool import disambiguate_tool_names
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import Output
from lfx.services.authorization.base import ExecutionPrincipal
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def saved_flow_scope(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tool-policy.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda connection: SQLModel.metadata.create_all(connection, tables=[Flow.__table__, User.__table__])
        )
    user_id = uuid4()
    async with AsyncSession(engine) as session:
        session.add(User(id=user_id, username="tool-author", password="", is_active=True))
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
    try:
        yield scope, user_id
    finally:
        await engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("tool_kind", ["generated", "structured", "base"])
@pytest.mark.parametrize("grouped", [False, True])
@pytest.mark.parametrize(
    "change",
    [
        "approval_added",
        "disabled",
        "removed_tool",
        "removed_node",
        "renamed",
        "unchanged",
        "already_gated",
        "disambiguated_unchanged",
        "metadata_tampered",
        "tool_mode_off",
        "metadata_added",
        "metadata_removed",
    ],
)
async def test_tool_uses_current_saved_policy_before_side_effects(
    saved_flow_scope, asynchronous, change, tool_kind, grouped
):
    scope, user_id = saved_flow_scope
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

                def _run(self, config: RunnableConfig) -> str:
                    effects.append("called")
                    assert config is not None
                    return "ok"

                async def _arun(self, config: RunnableConfig) -> str:
                    return self._run(config)

            return [NativeTool(tags=["perform"], handle_tool_error=True)]

    flow_id = uuid4()
    component = CountingTool(_id="counter")
    graph = Graph(flow_id=str(flow_id), user_id=str(user_id))
    graph.execution_principal = ExecutionPrincipal(kind="actor", user_id=str(user_id), actor_id=str(user_id))
    component.set_vertex(SimpleNamespace(graph=graph))
    tool = (await component._get_tools())[0]
    row = {
        "tags": list(tool.tags),
        "name": tool.name,
        "status": True,
        "approval_actions": ["approve", "reject"] if change == "already_gated" else [],
    }
    if change != "metadata_added":
        component.tools_metadata = pd.DataFrame([row])
    tool = (await component.to_toolkit())[0]
    if change == "disambiguated_unchanged":
        tool = disambiguate_tool_names([tool, tool.model_copy()])[0]
    node = component.to_frontend_node()
    node["data"]["node"]["tool_mode"] = True
    node["data"]["node"]["template"]["tools_metadata"] = {"value": [row]}
    if change == "metadata_added":
        node["data"]["node"]["template"].pop("tools_metadata")
    data = {"nodes": [node], "edges": []}
    if grouped:
        data = {
            "nodes": [
                {
                    "id": "group",
                    "data": {
                        "id": "group",
                        "node": {
                            "template": {},
                            "flow": {"data": data},
                            "outputs": [],
                        },
                    },
                }
            ],
            "edges": [],
        }
    async with scope() as session:
        session.add(Flow(id=flow_id, name="paused flow", user_id=user_id, data=data))
        await session.commit()

    async def invoke():
        return await tool.ainvoke({}) if asynchronous else tool.invoke({})

    assert await invoke() == "ok"
    assert effects == ["called"]
    changed = deepcopy(data)
    executable = changed["nodes"][0]["data"]["node"]["flow"]["data"] if grouped else changed
    current_node = executable["nodes"][0]["data"]["node"]
    current = current_node["template"].setdefault("tools_metadata", {"value": [row]})["value"]
    if change in {"approval_added", "metadata_tampered", "metadata_added"}:
        current[0]["approval_actions"] = ["approve", "reject"]
        if change == "metadata_tampered":
            tool.metadata["approval_actions"] = ["approve", "reject"]
    elif change == "disabled":
        current[0]["status"] = False
    elif change == "removed_tool":
        current.clear()
    elif change == "removed_node":
        executable["nodes"].clear()
    elif change == "renamed":
        current[0]["name"] = "renamed"
    elif change == "tool_mode_off":
        current_node["tool_mode"] = False
    elif change == "metadata_removed":
        current_node["template"].pop("tools_metadata")
    async with scope() as session:
        flow = await session.get(Flow, flow_id)
        flow.data = changed
        session.add(flow)
        await session.commit()

    if change in {"unchanged", "already_gated", "disambiguated_unchanged"}:
        assert await invoke() == "ok"
        assert effects == ["called", "called"]
    else:
        assert "Tool settings changed" in await invoke()
        assert effects == ["called"]
