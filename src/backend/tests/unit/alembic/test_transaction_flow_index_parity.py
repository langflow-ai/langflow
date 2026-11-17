"""Compare real query/write/retention code with and without the additive index."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from fastapi_pagination import Params
from langflow.api.v1 import monitor
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.transactions import crud
from langflow.services.database.models.transactions.model import TransactionBase, TransactionTable
from langflow.services.telemetry_writer import service as writer_module
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DataError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.services.telemetry_writer.test_service import _build_writer

from .test_migration_execution import _make_alembic_cfg, db_url  # noqa: F401

_INDEX = "ix_transaction_flow_id_timestamp"


@pytest.mark.parametrize("limit", [0, -1, 1, 3, 20])
@pytest.mark.parametrize("ties", [False, True])
def test_real_read_and_retention_parity(db_url, monkeypatch, limit, ties):  # noqa: F811
    command.upgrade(_make_alembic_cfg(db_url), "head")
    settings = SimpleNamespace(settings=SimpleNamespace(max_transactions_to_keep=limit))
    monkeypatch.setattr(crud, "get_settings_service", lambda: settings)

    async def not_paused():
        return False

    monkeypatch.setattr(writer_module, "writes_paused", not_paused)

    # This comparison isolates the route's actual SQL, COUNT, pagination and
    # transformer. Native monitor auth/ownership/shared suites test the guard.
    async def known_flow(session, *, flow_id, **_):
        return await session.get(Flow, flow_id)

    monkeypatch.setattr(monitor, "_ensure_flow_action_or_404", known_flow)
    flow_ids = [uuid4(), uuid4()]
    ids = [[uuid4() for _ in range(8)] for _ in flow_ids]
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async def compare():
        engine = create_async_engine(db_url)
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        outcomes = []
        try:
            async with maker() as session:
                session.add_all([Flow(id=flow, name=f"flow-{flow}", data={}) for flow in flow_ids])
                await session.commit()
            for indexed in (False, True):
                async with engine.begin() as connection:
                    if indexed:
                        await connection.execute(text(f'CREATE INDEX {_INDEX} ON "transaction" (flow_id,timestamp)'))
                    else:
                        await connection.execute(text(f"DROP INDEX {_INDEX}"))
                    await connection.execute(delete(TransactionTable))
                rows = [
                    {
                        "id": ids[f][i],
                        "flow_id": flow,
                        "vertex_id": f"v{i}",
                        "status": "success",
                        "timestamp": stamp if ties else stamp + timedelta(seconds=i),
                        "inputs": {"keep": i},
                    }
                    for f, flow in enumerate(flow_ids)
                    for i in range(8)
                ]
                async with maker() as session:
                    session.add_all([TransactionTable(**row) for row in rows])
                    await session.commit()
                    page = await monitor.get_transactions(flow_ids[0], session, None, Params(page=2, size=3))
                    payload = page.model_dump(mode="json")
                    assert payload["total"] == 8
                    if ties:
                        assert len(payload["items"]) == 3
                        assert {item["id"] for item in payload["items"]} <= {str(x) for x in ids[0]}
                    else:
                        assert [item["vertex_id"] for item in payload["items"]] == ["v4", "v3", "v2"]
                    ascending = await crud.get_transactions_by_flow_id(session, flow_ids[0], limit=4)
                    if ties:
                        assert len(ascending) == 4
                        assert {row.id for row in ascending} <= set(ids[0])
                    else:
                        assert [row.vertex_id for row in ascending] == ["v0", "v1", "v2", "v3"]
                    expected_crud_error = engine.dialect.name == "postgresql" and limit <= 0
                    try:
                        await crud.log_transaction(
                            session,
                            TransactionBase(
                                flow_id=flow_ids[0],
                                vertex_id="new",
                                status="success",
                                timestamp=stamp + timedelta(seconds=20),
                            ),
                        )
                    except DataError:
                        assert expected_crud_error
                    else:
                        assert not expected_crud_error
                    retained = list(
                        (
                            await session.exec(
                                select(TransactionTable.id)
                                .where(TransactionTable.flow_id == flow_ids[0])
                                .order_by(TransactionTable.timestamp)
                            )
                        ).scalars()
                    )
                    untouched = (
                        (await session.exec(select(TransactionTable.id).where(TransactionTable.flow_id == flow_ids[1])))
                        .scalars()
                        .all()
                    )
                    assert set(untouched) == set(ids[1])
                # Actual outbox enqueue->drain->batched flush and dirty handoff.
                writer = _build_writer({"max_transactions_to_keep": limit})
                writer._engine = engine
                writer._session_maker = maker
                writer._started = True
                async with engine.begin() as connection:
                    await connection.execute(delete(TransactionTable))
                for row in rows:
                    assert writer.enqueue_transaction(row)
                tx_batch = writer._drain_batch("transactions", 200, None)
                vb_batch = []
                await writer._flush(tx_batch, vb_batch)
                assert writer._dirty_tx_flows == {str(flow) for flow in flow_ids}
                if limit == 3:

                    @asynccontextmanager
                    async def fail_before_commit():
                        async with maker() as failed_session:

                            async def fail_commit():
                                msg = "before commit"
                                raise RuntimeError(msg)

                            failed_session.commit = fail_commit
                            yield failed_session

                    writer._session_maker = fail_before_commit
                    with pytest.raises(RuntimeError, match="before commit"):
                        await writer._run_retention_pass()
                    assert writer._dirty_tx_flows == {str(flow) for flow in flow_ids}
                    async with maker() as session:
                        after_failure = set((await session.exec(select(TransactionTable.id))).scalars())
                        assert after_failure == {row["id"] for row in rows}
                    writer._session_maker = maker
                try:
                    await writer._run_retention_pass()
                except DataError:
                    assert engine.dialect.name == "postgresql"
                    assert limit < 0
                    assert writer._dirty_tx_flows == {str(flow) for flow in flow_ids}
                else:
                    assert not (engine.dialect.name == "postgresql" and limit < 0)
                async with maker() as session:
                    survivors = set((await session.exec(select(TransactionTable.id))).scalars())
                # New random CRUD ID is intentionally normalized; distinct-time
                # ordering and existing max-1/autoflush semantics are compared.
                if ties:
                    assert survivors <= {row["id"] for row in rows}
                    payload["items"] = len(payload["items"])
                    outcomes.append((payload, len(retained), [len(survivors & set(group)) for group in ids]))
                else:
                    outcomes.append((payload, [str(x) if x in ids[0] else "new" for x in retained], survivors))
                writer._started = False
            assert outcomes[0] == outcomes[1]
        finally:
            await engine.dispose()

    asyncio.run(compare())
