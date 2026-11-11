"""Real PostgreSQL repairs keep graph, recovery, and report outcomes atomic."""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.maintenance import MaintenanceState
from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from langflow.services.database.models.user.model import User
from langflow.services.flow_repair import service
from langflow.services.flow_repair.models import RepairApplyRequest, RepairPreviewRequest, RepairSelection
from langflow.services.upgrade_reports.history import store_report
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.services.flow_repair.test_planning import graph, registry

pytestmark = pytest.mark.no_blockbuster
REPORT = Path(__file__).parents[2] / "api" / "v1" / "fixtures" / "upgrade-report-v1.json"


@pytest.fixture
async def postgres_repairs(client, monkeypatch):  # noqa: ARG001
    raw = os.environ.get("LANGFLOW_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("LANGFLOW_TEST_POSTGRES_URL is not set")
    pytest.importorskip("psycopg")
    url = sa.make_url(raw).set(drivername="postgresql+psycopg")
    admin_engine = create_async_engine(url)
    namespace = f"repair_{uuid4().hex}"
    async with admin_engine.begin() as connection:
        await connection.execute(sa.schema.CreateSchema(namespace))
    selected = url.update_query_dict({"options": f"-csearch_path={namespace}"})
    engine = create_async_engine(selected)
    sessions = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    @asynccontextmanager
    async def scope():
        async with sessions() as session:
            try:
                yield session
                await session.commit()
            except BaseException:
                await session.rollback()
                raise

    async def load_registry():
        return registry()

    monkeypatch.setattr(service, "session_scope", scope)
    monkeypatch.setattr(service, "target_registry", load_registry)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with scope() as session:
            owner = User(username=f"pg-owner-{uuid4()}", password=uuid4().hex, is_active=True)
            actor = User(username=f"pg-admin-{uuid4()}", password=uuid4().hex, is_active=True, is_superuser=True)
            session.add_all([owner, actor, MaintenanceState(enabled=True)])
            await session.flush()
            report = await store_report(session, REPORT.read_bytes(), actor.id)
        yield scope, owner.id, actor.id, report.id
    finally:
        await engine.dispose()
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(sa.schema.DropSchema(namespace, cascade=True))
        finally:
            await admin_engine.dispose()


async def _selection(store, *, legacy=False):
    scope, owner_id, actor_id, report_id = store
    async with scope() as session:
        flow = Flow(name="PostgreSQL repair", user_id=owner_id, data=graph(), version_token=None if legacy else uuid4())
        session.add(flow)
        await session.flush()
        flow_id, original_token = flow.id, flow.version_token
    preview = await service.preview_repairs(RepairPreviewRequest(flow_ids=[flow_id], report_id=report_id), actor_id)
    [ready] = preview.results
    assert ready.status == "ready", ready
    payload = RepairApplyRequest(
        flows=[RepairSelection(flow_id=flow_id, version_token=ready.version_token, data_sha256=ready.data_sha256)],
        target_sha256=preview.target_sha256,
        report_id=report_id,
    )
    return payload, original_token


async def _state(store, flow_id):
    scope, _owner_id, _actor_id, report_id = store
    async with scope() as session:
        flow = await session.get(Flow, flow_id)
        versions = (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == flow_id))).all()
        outcomes = (
            await session.exec(select(UpgradeReportRepair).where(UpgradeReportRepair.report_id == report_id))
        ).all()
        report = await session.get(UpgradeReport, report_id)
        return flow, versions, [json.loads(row.result_json) for row in outcomes], report.document_json


@pytest.mark.parametrize("legacy", [False, True], ids=["token", "null-token"])
async def test_postgres_repair_commits_owner_recovery_and_report_together(postgres_repairs, legacy):
    payload, _token = await _selection(postgres_repairs, legacy=legacy)
    _scope, owner_id, actor_id, _report_id = postgres_repairs

    result = await service.apply_repairs(payload, actor_id)

    [updated] = result.results
    assert updated.status == "updated", updated
    flow, versions, outcomes, exported = await _state(postgres_repairs, payload.flows[0].flow_id)
    [recovery] = versions
    assert flow.user_id == recovery.user_id == owner_id
    assert recovery.id == updated.recovery_version_id
    assert recovery.retained is True
    assert recovery.data == graph()
    assert flow.data != recovery.data
    assert flow.version_token == updated.version_token
    assert [row["status"] for row in outcomes] == ["updated"]
    assert outcomes[0]["recovery_version_id"] == str(recovery.id)
    assert exported.encode() == REPORT.read_bytes()


async def test_postgres_simultaneous_repairs_create_only_one_recovery(postgres_repairs):
    payload, _token = await _selection(postgres_repairs)
    _scope, _owner_id, actor_id, _report_id = postgres_repairs

    results = await asyncio.gather(
        service.apply_repairs(payload.model_copy(deep=True), actor_id),
        service.apply_repairs(payload.model_copy(deep=True), actor_id),
    )

    assert sorted(batch.results[0].status for batch in results) == ["conflict", "updated"]
    _flow, versions, outcomes, _exported = await _state(postgres_repairs, payload.flows[0].flow_id)
    assert len(versions) == 1
    assert sorted(row["status"] for row in outcomes) == ["conflict", "updated"]


async def test_postgres_outcome_failure_rolls_back_graph_token_and_recovery(postgres_repairs, monkeypatch):
    payload, original_token = await _selection(postgres_repairs)
    _scope, _owner_id, actor_id, _report_id = postgres_repairs
    original = service._record_result

    async def fail_after_flush(session, result, **kwargs):
        await original(session, result, **kwargs)
        if result.status == "updated":
            msg = "injected failure after report outcome flush"
            raise RuntimeError(msg)

    monkeypatch.setattr(service, "_record_result", fail_after_flush)

    result = await service.apply_repairs(payload, actor_id)

    assert result.results[0].status == "failed"
    flow, versions, outcomes, exported = await _state(postgres_repairs, payload.flows[0].flow_id)
    assert flow.data == graph()
    assert flow.version_token == original_token
    assert versions == []
    assert [row["status"] for row in outcomes] == ["failed"]
    assert exported.encode() == REPORT.read_bytes()
