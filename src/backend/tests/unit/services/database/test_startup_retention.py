"""Startup retention preserves flow partitions and unique build records."""

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from langflow.services.database.models.transactions.model import TransactionTable
from langflow.services.database.models.vertex_builds.model import VertexBuildTable
from langflow.services.utils import clean_transactions, clean_vertex_builds
from sqlmodel import select


@pytest.mark.parametrize("limit", [0, 1, 3, 6])
async def test_startup_transaction_retention_is_per_flow_and_repeatable(async_session, limit):
    """A busy flow must not evict another flow's transaction history."""
    flow_ids = [uuid4(), uuid4()]
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    ids = []
    for flow_id, count in zip(flow_ids, [5, 2], strict=True):
        rows = [
            TransactionTable(id=uuid4(), flow_id=flow_id, timestamp=timestamp, vertex_id="reused", status="success")
            for _ in range(count)
        ]
        async_session.add_all(rows)
        ids.append(sorted((row.id for row in rows), reverse=True)[:limit])
    await async_session.commit()
    settings = SimpleNamespace(settings=SimpleNamespace(max_transactions_to_keep=limit))
    for _ in range(2):
        await clean_transactions(settings, async_session)
        await async_session.commit()
        for flow_id, expected in zip(flow_ids, ids, strict=True):
            remaining = (
                await async_session.exec(select(TransactionTable.id).where(TransactionTable.flow_id == flow_id))
            ).all()
            assert set(remaining) == set(expected)


@pytest.mark.parametrize("limit", [0, 1, 3, 6])
async def test_startup_build_retention_uses_build_id(async_session, limit):
    """Deleting an old build must not delete newer builds of the same component."""
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        VertexBuildTable(build_id=UUID(int=i + 1), id="same-vertex", flow_id=uuid4(), valid=True, timestamp=timestamp)
        for i in range(5)
    ]
    async_session.add_all(rows)
    await async_session.commit()
    settings = SimpleNamespace(settings=SimpleNamespace(max_vertex_builds_to_keep=limit))
    expected = {row.build_id for row in rows[-limit:]} if limit else set()
    for _ in range(2):
        await clean_vertex_builds(settings, async_session)
        await async_session.commit()
        remaining = (await async_session.exec(select(VertexBuildTable.build_id))).all()
        assert set(remaining) == expected
