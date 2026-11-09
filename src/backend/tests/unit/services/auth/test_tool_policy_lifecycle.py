"""A saved flow can tighten tool settings after an agent was built."""

from contextlib import asynccontextmanager
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pandas as pd
import pytest
from langflow.services.auth.service import AuthService
from langflow.services.database.models.flow.model import Flow
from lfx.base.tools.component_tool import ComponentToolkit, disambiguate_tool_names
from lfx.custom import Component
from lfx.graph import Graph
from lfx.io import Output
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession


@pytest.fixture
async def saved_flow_scope(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'tool-policy.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(lambda connection: SQLModel.metadata.create_all(connection, tables=[Flow.__table__]))

    @asynccontextmanager
    async def scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session

    auth = AuthService(SimpleNamespace())
    monkeypatch.setattr("langflow.services.auth.service.session_scope", scope)
    monkeypatch.setattr("lfx.services.deps.get_auth_service", lambda: auth)
    try:
        yield scope
    finally:
        await engine.dispose()


@pytest.mark.parametrize("asynchronous", [False, True])
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
    ],
)
async def test_tool_uses_current_saved_policy_before_side_effects(saved_flow_scope, asynchronous, change):
    scope = saved_flow_scope
    effects = []

    class CountingTool(Component):
        outputs = [Output(name="result", display_name="Result", method="aperform" if asynchronous else "perform")]

        def perform(self) -> str:
            effects.append("called")
            return "ok"

        async def aperform(self) -> str:
            return self.perform()

    flow_id = uuid4()
    component = CountingTool(_id="counter")
    component.set_vertex(SimpleNamespace(graph=Graph(flow_id=str(flow_id))))
    tool = ComponentToolkit(component).get_tools()[0]
    row = {
        "tags": list(tool.tags),
        "name": tool.name,
        "status": True,
        "approval_actions": ["approve", "reject"] if change == "already_gated" else [],
    }
    tool = ComponentToolkit(component, metadata=pd.DataFrame([row])).update_tools_metadata([tool])[0]
    if change == "disambiguated_unchanged":
        tool = disambiguate_tool_names([tool, tool.model_copy()])[0]
    data = {"nodes": [{"id": "counter", "data": {"node": {"template": {"tools_metadata": {"value": [row]}}}}}]}
    async with scope() as session:
        session.add(Flow(id=flow_id, name="paused flow", data=data))
        await session.commit()

    async def invoke():
        return await tool.ainvoke({}) if asynchronous else tool.invoke({})

    assert await invoke() == "ok"
    assert effects == ["called"]
    changed = deepcopy(data)
    current = changed["nodes"][0]["data"]["node"]["template"]["tools_metadata"]["value"]
    if change in {"approval_added", "metadata_tampered"}:
        current[0]["approval_actions"] = ["approve", "reject"]
        if change == "metadata_tampered":
            tool.metadata["approval_actions"] = ["approve", "reject"]
    elif change == "disabled":
        current[0]["status"] = False
    elif change == "removed_tool":
        current.clear()
    elif change == "removed_node":
        changed["nodes"].clear()
    elif change == "renamed":
        current[0]["name"] = "renamed"
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
