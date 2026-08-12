"""Project and exposure scoping on the MCP tool-call path.

``get_flow_snake_case`` resolves a tool name for ``handle_call_tool``. Before this
suite it selected every flow the calling user owned, with no project filter, no
``mcp_enabled`` filter and no deterministic ordering, which produced two defects on
a serving plane where one service account owns every deployed flow:

* a flow the operator marked as not exposed still ran when named;
* two projects exposing the same ``action_name`` collided, and which one became
  uncallable was decided by row order rather than by anything the operator controls.

These run against a real async session rather than a stubbed one, because the
regression lives in the query itself.
"""

from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User
from lfx.base.mcp.util import get_flow_snake_case


async def _seed_user(session) -> User:
    user = User(id=uuid4(), username=f"mcp-scope-{uuid4().hex[:8]}", password="x", is_active=True)  # noqa: S106
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _seed_project(session, user: User, name: str) -> Folder:
    project = Folder(id=uuid4(), name=name, user_id=user.id)
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def _seed_flow(
    session,
    user: User,
    project: Folder,
    name: str,
    *,
    action_name: str | None = None,
    mcp_enabled: bool = True,
) -> Flow:
    flow = Flow(
        id=uuid4(),
        name=name,
        user_id=user.id,
        folder_id=project.id,
        action_name=action_name,
        mcp_enabled=mcp_enabled,
        is_component=False,
        data={"nodes": [], "edges": []},
    )
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow


@pytest.mark.asyncio
async def test_should_not_resolve_flow_when_mcp_disabled_and_exposure_enforced(async_session):
    """A flow excluded from tools/list must not be reachable through tools/call."""
    user = await _seed_user(async_session)
    project = await _seed_project(async_session, user, "Project A")
    await _seed_flow(async_session, user, project, "Hidden Flow", action_name="hidden_action", mcp_enabled=False)

    resolved = await get_flow_snake_case(
        "hidden_action",
        str(user.id),
        async_session,
        is_action=True,
        project_id=project.id,
        mcp_enabled_only=True,
    )

    assert resolved is None


@pytest.mark.asyncio
async def test_should_resolve_flow_when_mcp_enabled_and_exposure_enforced(async_session):
    """The exposure filter must not block a flow the operator did expose."""
    user = await _seed_user(async_session)
    project = await _seed_project(async_session, user, "Project A")
    exposed = await _seed_flow(
        async_session, user, project, "Exposed Flow", action_name="exposed_action", mcp_enabled=True
    )

    resolved = await get_flow_snake_case(
        "exposed_action",
        str(user.id),
        async_session,
        is_action=True,
        project_id=project.id,
        mcp_enabled_only=True,
    )

    assert resolved is not None
    assert resolved.id == exposed.id


@pytest.mark.asyncio
async def test_should_resolve_per_project_when_action_name_collides(async_session):
    """Two projects exposing the same action name each resolve to their own flow."""
    user = await _seed_user(async_session)
    project_a = await _seed_project(async_session, user, "Project A")
    project_b = await _seed_project(async_session, user, "Project B")
    flow_a = await _seed_flow(async_session, user, project_a, "Repro Flow A", action_name="shared_action")
    flow_b = await _seed_flow(async_session, user, project_b, "Repro Flow B", action_name="shared_action")

    resolved_a = await get_flow_snake_case(
        "shared_action", str(user.id), async_session, is_action=True, project_id=project_a.id, mcp_enabled_only=True
    )
    resolved_b = await get_flow_snake_case(
        "shared_action", str(user.id), async_session, is_action=True, project_id=project_b.id, mcp_enabled_only=True
    )

    assert resolved_a is not None
    assert resolved_b is not None
    assert resolved_a.id == flow_a.id
    assert resolved_b.id == flow_b.id


@pytest.mark.asyncio
async def test_should_preserve_global_lookup_when_no_project_given(async_session):
    """The global MCP server passes no project and must keep its existing behavior."""
    user = await _seed_user(async_session)
    project = await _seed_project(async_session, user, "Project A")
    hidden = await _seed_flow(
        async_session, user, project, "Global Flow", action_name="global_action", mcp_enabled=False
    )

    resolved = await get_flow_snake_case("global_flow", str(user.id), async_session)

    assert resolved is not None
    assert resolved.id == hidden.id


@pytest.mark.asyncio
async def test_should_scope_to_owner_when_another_user_owns_the_name(async_session):
    """The user filter must survive the new project filter."""
    owner = await _seed_user(async_session)
    other = await _seed_user(async_session)
    owner_project = await _seed_project(async_session, owner, "Owner Project")
    other_project = await _seed_project(async_session, other, "Other Project")
    await _seed_flow(async_session, owner, owner_project, "Owned Flow", action_name="some_action")

    resolved = await get_flow_snake_case(
        "some_action", str(other.id), async_session, is_action=True, project_id=other_project.id, mcp_enabled_only=True
    )

    assert resolved is None


@pytest.mark.asyncio
async def test_should_resolve_deterministically_when_duplicate_names_share_a_project(async_session):
    """Within one project, a duplicate name must resolve to the same row every time.

    Duplicates are reachable because ``action_name`` carries no uniqueness constraint.
    Without an explicit ordering the winner is heap-order dependent, so an unrelated
    edit elsewhere can silently flip which flow a tool call executes.
    """
    user = await _seed_user(async_session)
    project = await _seed_project(async_session, user, "Project A")
    await _seed_flow(async_session, user, project, "Dup One", action_name="dup_action")
    await _seed_flow(async_session, user, project, "Dup Two", action_name="dup_action")

    first = await get_flow_snake_case(
        "dup_action", str(user.id), async_session, is_action=True, project_id=project.id, mcp_enabled_only=True
    )
    second = await get_flow_snake_case(
        "dup_action", str(user.id), async_session, is_action=True, project_id=project.id, mcp_enabled_only=True
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id
