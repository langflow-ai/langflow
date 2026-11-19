"""Read-path regression coverage for get_vertex_builds_by_flow_id.

The flow-scoped read index changes how the planner reaches these rows; it must
not change which rows come back or the order they come back in.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.vertex_builds.crud import get_vertex_builds_by_flow_id
from langflow.services.database.models.vertex_builds.model import VertexBuildBase, VertexBuildTable
from sqlalchemy.ext.asyncio import AsyncSession

_BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
# Two flows deliberately share these vertex ids: a flow-scoped read must not
# mix them even though the grouping subquery groups by id alone.
_VERTEX_IDS = ["ChatInput-aaaaa", "Prompt-bbbbb", "ChatOutput-ccccc"]


async def _add_flow(session: AsyncSession, user_id) -> Flow:
    flow = Flow(id=uuid4(), name=f"flow-{uuid4().hex[:8]}", user_id=user_id)
    session.add(flow)
    await session.flush()
    return flow


async def _add_builds(session: AsyncSession, flow_id, *, offset: int) -> None:
    """Add three builds per vertex, oldest first, so only the newest should surface."""
    for vertex_position, vertex_id in enumerate(_VERTEX_IDS):
        for attempt in range(3):
            build = VertexBuildBase(
                id=vertex_id,
                flow_id=flow_id,
                # Distinct per flow, vertex and attempt: ties would make the
                # expected result ambiguous rather than wrong.
                timestamp=_BASE_TIME + timedelta(minutes=offset + vertex_position * 10 + attempt),
                artifacts={},
                valid=True,
            )
            session.add(VertexBuildTable(**build.model_dump()))
    await session.flush()


@pytest.fixture
async def seeded_flows(async_session: AsyncSession):
    """Two flows owned by one user, sharing vertex ids, plus one owned by another user."""
    owner_id = uuid4()
    other_owner_id = uuid4()
    first = await _add_flow(async_session, owner_id)
    second = await _add_flow(async_session, owner_id)
    foreign = await _add_flow(async_session, other_owner_id)

    await _add_builds(async_session, first.id, offset=0)
    # Overlapping timestamps, so a query that ignored flow_id would interleave.
    await _add_builds(async_session, second.id, offset=0)
    await _add_builds(async_session, foreign.id, offset=0)
    await async_session.commit()
    return owner_id, other_owner_id, first, second, foreign


async def test_returns_newest_build_per_vertex_in_timestamp_order(async_session: AsyncSession, seeded_flows):
    owner_id, _, first, _, _ = seeded_flows

    builds = await get_vertex_builds_by_flow_id(async_session, first.id, owner_id)

    assert [build.id for build in builds] == _VERTEX_IDS
    timestamps = [build.timestamp for build in builds]
    assert timestamps == sorted(timestamps)
    # Three builds per vertex were written; only the newest of each comes back.
    assert len(builds) == len(_VERTEX_IDS)
    for vertex_position, build in enumerate(builds):
        expected = _BASE_TIME + timedelta(minutes=vertex_position * 10 + 2)
        assert build.timestamp.replace(tzinfo=timezone.utc) == expected


async def test_does_not_mix_flows_that_share_vertex_ids(async_session: AsyncSession, seeded_flows):
    owner_id, _, first, second, _ = seeded_flows

    first_builds = await get_vertex_builds_by_flow_id(async_session, first.id, owner_id)
    second_builds = await get_vertex_builds_by_flow_id(async_session, second.id, owner_id)

    assert {build.flow_id for build in first_builds} == {first.id}
    assert {build.flow_id for build in second_builds} == {second.id}
    # Same vertex ids on both sides, disjoint rows underneath.
    assert [build.id for build in first_builds] == [build.id for build in second_builds]
    assert not {build.build_id for build in first_builds} & {build.build_id for build in second_builds}


async def test_excludes_flows_owned_by_another_user(async_session: AsyncSession, seeded_flows):
    owner_id, other_owner_id, _, _, foreign = seeded_flows

    assert await get_vertex_builds_by_flow_id(async_session, foreign.id, owner_id) == []
    assert await get_vertex_builds_by_flow_id(async_session, foreign.id, other_owner_id) != []


async def test_limit_applies_to_the_oldest_builds_first(async_session: AsyncSession, seeded_flows):
    owner_id, _, first, _, _ = seeded_flows

    builds = await get_vertex_builds_by_flow_id(async_session, first.id, owner_id, limit=2)

    assert [build.id for build in builds] == _VERTEX_IDS[:2]
