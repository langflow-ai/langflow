"""Real two-session report erasure and repair-outcome admission races."""

import asyncio
import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.services.data_subjects import upgrade_reports
from langflow.services.data_subjects.context import EraseContext
from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from langflow.services.upgrade_reports import history
from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture(params=["foreign-keys-off", "foreign-keys-on", "postgresql"])
async def report_engine(tmp_path, request):
    admin_engine, namespace = None, None
    if request.param == "postgresql":
        raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
        if not raw:
            pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
        pytest.importorskip("psycopg")
        url = sa.make_url(raw).set(drivername="postgresql+psycopg")
        admin_engine = create_async_engine(url)
        namespace = f"report_erase_{uuid4().hex}"
        async with admin_engine.begin() as connection:
            await connection.execute(sa.schema.CreateSchema(namespace))
        engine = create_async_engine(url.update_query_dict({"options": f"-csearch_path={namespace}"}))
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'report-race.db'}", connect_args={"timeout": 10})

        @event.listens_for(engine.sync_engine, "connect")
        def configure_connection(connection, _record):
            cursor = connection.cursor()
            cursor.execute(
                "PRAGMA foreign_keys=ON" if request.param == "foreign-keys-on" else "PRAGMA foreign_keys=OFF"
            )
            cursor.close()

    try:
        async with engine.begin() as connection:
            if request.param != "postgresql":
                await connection.exec_driver_sql("PRAGMA journal_mode=WAL")
            await connection.run_sync(
                lambda sync: SQLModel.metadata.create_all(
                    sync, tables=[UpgradeReport.__table__, UpgradeReportRepair.__table__]
                )
            )
        yield engine
    finally:
        await engine.dispose()
        if admin_engine is not None:
            try:
                async with admin_engine.begin() as connection:
                    await connection.execute(sa.schema.DropSchema(namespace, cascade=True))
            finally:
                await admin_engine.dispose()


async def _seed_report(engine, subject):
    row = UpgradeReport(
        created_by=subject,
        generated_at=datetime.now(timezone.utc),
        target_version="1.14.0",
        flow_count=0,
        warning_count=0,
        failing_count=0,
        content_sha256="a" * 64,
        document_json='{"flows":[]}',
    )
    async with AsyncSession(engine, expire_on_commit=False) as session:
        session.add(row)
        await session.commit()
    return row.id


async def _erase(engine, context):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        deleted = await upgrade_reports.erase_upgrade_reports(session, context)
        await session.commit()
        return deleted


async def _record(engine, report_id, *, read_first=False):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        if read_first:
            # Keep a stale parent in the identity map. Admission must check
            # the database again after waiting for the eraser's transaction.
            cached_report = await session.get(UpgradeReport, report_id)
            assert cached_report is not None
        result = await history.record_repair_result(
            session, report_id=report_id, actor_id=uuid4(), target_sha256="b" * 64, result={"status": "unchanged"}
        )
        await session.commit()
        return result


async def _assert_empty(engine):
    async with AsyncSession(engine) as session:
        assert not (await session.exec(select(UpgradeReport))).all()
        assert not (await session.exec(select(UpgradeReportRepair))).all()


async def test_eraser_wins_and_stale_outcome_writer_cannot_leave_an_orphan(report_engine, monkeypatch):
    subject = uuid4()
    report_id = await _seed_report(report_engine, subject)
    context = EraseContext(request_id=uuid4(), subject_user_id=subject)
    eraser_locked, release_eraser, writer_attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = history.lock_report

    async def hold_eraser(session, report_id):
        locked = await original(session, report_id)
        eraser_locked.set()
        await release_eraser.wait()
        return locked

    async def observe_writer(session, report_id):
        writer_attempted.set()
        return await original(session, report_id)

    monkeypatch.setattr(upgrade_reports, "lock_report", hold_eraser)
    monkeypatch.setattr(history, "lock_report", observe_writer)
    tasks = []
    try:
        eraser = asyncio.create_task(_erase(report_engine, context))
        tasks.append(eraser)
        await asyncio.wait_for(eraser_locked.wait(), timeout=10)
        writer = asyncio.create_task(_record(report_engine, report_id, read_first=True))
        tasks.append(writer)
        await asyncio.wait_for(writer_attempted.wait(), timeout=10)
        assert not writer.done()
        release_eraser.set()
        assert await asyncio.wait_for(eraser, timeout=10) == 1
        with pytest.raises(ValueError, match="Upgrade report not found"):
            await asyncio.wait_for(writer, timeout=10)
        await _assert_empty(report_engine)
    finally:
        release_eraser.set()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_outcome_writer_wins_and_eraser_drains_it_before_deleting_report(report_engine, monkeypatch):
    subject = uuid4()
    report_id = await _seed_report(report_engine, subject)
    context = EraseContext(request_id=uuid4(), subject_user_id=subject)
    writer_locked, release_writer, eraser_attempted = asyncio.Event(), asyncio.Event(), asyncio.Event()
    original = history.lock_report

    async def hold_writer(session, report_id):
        locked = await original(session, report_id)
        writer_locked.set()
        await release_writer.wait()
        return locked

    async def observe_eraser(session, report_id):
        eraser_attempted.set()
        return await original(session, report_id)

    monkeypatch.setattr(history, "lock_report", hold_writer)
    monkeypatch.setattr(upgrade_reports, "lock_report", observe_eraser)
    tasks = []
    try:
        writer = asyncio.create_task(_record(report_engine, report_id))
        tasks.append(writer)
        await asyncio.wait_for(writer_locked.wait(), timeout=10)
        eraser = asyncio.create_task(_erase(report_engine, context))
        tasks.append(eraser)
        await asyncio.wait_for(eraser_attempted.wait(), timeout=10)
        assert not eraser.done()
        release_writer.set()
        assert await asyncio.wait_for(writer, timeout=10) is not None
        # The first bounded erase removes the admitted child; the next removes
        # the parent only after a fresh, serialized empty-child check.
        assert await asyncio.wait_for(eraser, timeout=10) == 1
        assert await _erase(report_engine, context) == 1
        await _assert_empty(report_engine)
    finally:
        release_writer.set()
        await asyncio.gather(*tasks, return_exceptions=True)
