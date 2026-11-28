"""A project's MCP server, reached by an account that does not own the project.

On a deployer plane the deployer owns every deployed project and holds no API key, so the
only keys there belong to service accounts that hold ``execute`` shares on the flows.
Without a plugin that loads across owners, the owner check stays exactly as it was.
"""

from uuid import uuid4

import pytest
from fastapi import HTTPException
from langflow.api.v1 import mcp_utils
from langflow.api.v1.mcp_utils import ensure_project_reachable, project_flow_owner
from langflow.services.database.models.flow import Flow
from langflow.services.database.models.folder import Folder
from langflow.services.database.models.user.model import User
from lfx.services.deps import session_scope


@pytest.fixture
async def deployer_project(user_two):
    """user_two's project: one flow exposed as a tool, one not."""
    project_id, exposed_id, hidden_id = uuid4(), uuid4(), uuid4()
    async with session_scope() as session:
        session.add(Folder(id=project_id, name=f"handbooks-{project_id.hex[:6]}", user_id=user_two.id))
        for flow_id, exposed in ((exposed_id, True), (hidden_id, False)):
            session.add(
                Flow(
                    id=flow_id,
                    name=f"flow-{flow_id.hex[:6]}",
                    data={"nodes": [], "edges": []},
                    user_id=user_two.id,
                    folder_id=project_id,
                    mcp_enabled=exposed,
                )
            )
    yield project_id, exposed_id, hidden_id
    async with session_scope() as session:
        for flow_id in (exposed_id, hidden_id):
            if flow := await session.get(Flow, flow_id):
                await session.delete(flow)
        if project := await session.get(Folder, project_id):
            await session.delete(project)


def _plugin(monkeypatch, *, cross_user: bool, executable: set):
    """Stand in for a registered plugin: load across owners, allow execute on `executable` only."""

    async def enabled():
        return cross_user

    async def visible(_user, *, candidates, act, **_):
        return [flow for flow in candidates if getattr(act, "value", act) == "execute" and flow.id in executable]

    monkeypatch.setattr(mcp_utils, "cross_user_fetch_enabled", enabled)
    monkeypatch.setattr(mcp_utils, "filter_visible_resources", visible)


async def test_owner_is_admitted_without_asking_the_plugin(user_two, deployer_project, monkeypatch):
    project_id, *_ = deployer_project
    _plugin(monkeypatch, cross_user=False, executable=set())

    await ensure_project_reachable(user_two, project_id, user_two.id)
    async with session_scope() as session:
        assert await project_flow_owner(session, project_id, user_two.id) == user_two.id


async def test_without_cross_user_fetch_a_non_owner_still_gets_404(
    active_user, user_two, deployer_project, monkeypatch
):
    project_id, exposed_id, _ = deployer_project
    # Even a share on the flow does not help: the OSS pass-through never widens the lookup.
    _plugin(monkeypatch, cross_user=False, executable={exposed_id})

    with pytest.raises(HTTPException) as refused:
        await ensure_project_reachable(active_user, project_id, user_two.id)
    assert (refused.value.status_code, refused.value.detail) == (404, "Project not found")
    async with session_scope() as session:
        assert await project_flow_owner(session, project_id, active_user.id) == active_user.id


async def test_a_caller_that_may_run_an_exposed_flow_reaches_the_owners_tools(
    active_user, user_two, deployer_project, monkeypatch
):
    project_id, exposed_id, _ = deployer_project
    _plugin(monkeypatch, cross_user=True, executable={exposed_id})

    await ensure_project_reachable(active_user, project_id, user_two.id)
    async with session_scope() as session:
        # tools/list and tools/call both resolve names against the owner's flows.
        assert await project_flow_owner(session, project_id, active_user.id) == user_two.id


async def test_a_caller_with_no_runnable_flow_gets_the_same_404(active_user, user_two, deployer_project, monkeypatch):
    project_id, _, hidden_id = deployer_project
    # A share on a flow that is not exposed as a tool does not reveal the project.
    _plugin(monkeypatch, cross_user=True, executable={hidden_id})

    with pytest.raises(HTTPException) as refused:
        await ensure_project_reachable(active_user, project_id, user_two.id)
    assert (refused.value.status_code, refused.value.detail) == (404, "Project not found")


async def test_streamable_endpoint_keeps_404_for_another_users_key(client, deployer_project, user_one_api_key):
    """Through the real endpoint with the OSS pass-through: the old answer, unchanged."""
    project_id, *_ = deployer_project
    response = await client.post(
        f"api/v1/mcp/project/{project_id}/streamable",
        headers={"x-api-key": user_one_api_key},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Project not found"


@pytest.fixture
def as_caller(active_user, monkeypatch):
    """Run list and call as active_user, with the flow's graph and the run stubbed out."""
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    monkeypatch.setattr(mcp_utils, "json_schema_from_flow", lambda _flow: {"type": "object"})
    run = AsyncMock(return_value=SimpleNamespace(outputs=[]))
    monkeypatch.setattr(mcp_utils, "simple_run_flow", run)
    monkeypatch.setattr(mcp_utils.get_mcp_config(), "enable_progress_notifications", False)
    user_token = mcp_utils.current_user_ctx.set(active_user)
    caller_token = mcp_utils.authenticated_caller_ctx.set(active_user.id)
    yield run
    mcp_utils.authenticated_caller_ctx.reset(caller_token)
    mcp_utils.current_user_ctx.reset(user_token)


def _execute_only(monkeypatch, executable: set):
    """The plugin's per-flow check on the call path: execute is allowed on `executable` only."""

    async def ensure(_user, _act, *, flow_id, **_):
        if flow_id not in executable:
            raise HTTPException(status_code=403, detail="Forbidden")

    monkeypatch.setattr(mcp_utils, "ensure_flow_permission", ensure)


async def _second_exposed_flow(project_id, owner_id):
    flow_id = uuid4()
    async with session_scope() as session:
        session.add(
            Flow(
                id=flow_id,
                name=f"other-{flow_id.hex[:6]}",
                data={"nodes": [], "edges": []},
                user_id=owner_id,
                folder_id=project_id,
                mcp_enabled=True,
            )
        )
    return flow_id


@pytest.mark.usefixtures("as_caller")
async def test_a_non_owner_lists_only_the_owners_flows_it_may_run(user_two, deployer_project, monkeypatch):
    project_id, exposed_id, _ = deployer_project
    other_id = await _second_exposed_flow(project_id, user_two.id)
    try:
        _plugin(monkeypatch, cross_user=True, executable={exposed_id})
        tools, _ = await mcp_utils._collect_tools(project_id, mcp_enabled_only=True)
        assert [tool.name for tool in tools] == [f"flow_{exposed_id.hex[:6]}"]
    finally:
        async with session_scope() as session:
            await session.delete(await session.get(Flow, other_id))


async def test_a_non_owner_runs_its_flow_and_is_refused_the_others(user_two, deployer_project, monkeypatch, as_caller):
    project_id, exposed_id, _ = deployer_project
    other_id = await _second_exposed_flow(project_id, user_two.id)
    try:
        _plugin(monkeypatch, cross_user=True, executable={exposed_id})
        _execute_only(monkeypatch, {exposed_id})

        assert await mcp_utils.handle_call_tool(f"flow_{exposed_id.hex[:6]}", {}, None, project_id=project_id) == []
        as_caller.assert_awaited_once()

        with pytest.raises(HTTPException) as refused:
            await mcp_utils.handle_call_tool(f"other_{other_id.hex[:6]}", {}, None, project_id=project_id)
        assert refused.value.status_code == 403
        as_caller.assert_awaited_once()
    finally:
        async with session_scope() as session:
            await session.delete(await session.get(Flow, other_id))


async def test_a_deactivated_owner_closes_its_project_to_shared_callers(
    active_user, user_two, deployer_project, monkeypatch, as_caller
):
    project_id, exposed_id, _ = deployer_project
    _plugin(monkeypatch, cross_user=True, executable={exposed_id})
    _execute_only(monkeypatch, {exposed_id})
    async with session_scope() as session:
        (await session.get(User, user_two.id)).is_active = False
    try:
        with pytest.raises(HTTPException) as refused:
            await ensure_project_reachable(active_user, project_id, user_two.id)
        assert refused.value.status_code == 404
        with pytest.raises(ValueError, match="Project owner not found"):
            await mcp_utils.handle_call_tool(f"flow_{exposed_id.hex[:6]}", {}, None, project_id=project_id)
        as_caller.assert_not_awaited()
    finally:
        async with session_scope() as session:
            (await session.get(User, user_two.id)).is_active = True
