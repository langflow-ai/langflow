"""A repair must not outlive the owner and policy context it validated."""

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.maintenance import MaintenanceState
from langflow.services.database.models.upgrade_report import UpgradeReportRepair
from langflow.services.database.models.user.model import User
from langflow.services.flow_repair import service
from langflow.services.flow_repair.models import RepairApplyRequest, RepairSelection
from langflow.services.flow_repair.planning import data_digest
from langflow.services.upgrade_reports.history import store_report
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select, update
from sqlmodel.ext.asyncio.session import AsyncSession

from tests.unit.services.flow_repair.test_planning import graph, registry

pytestmark = pytest.mark.no_blockbuster
REPORT = Path(__file__).parents[2] / "api" / "v1" / "fixtures" / "upgrade-report-v1.json"


@pytest.fixture
async def sqlite_repairs(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'repairs.db'}")

    @sa.event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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

    async def admin(session, actor_id):
        actor = await session.get(User, actor_id)
        assert actor.is_active
        assert actor.is_superuser
        return actor

    async def authorize(session, current, actor):
        assert actor.is_superuser
        return await session.get(User, current.user_id)

    monkeypatch.setattr(service, "session_scope", scope)
    monkeypatch.setattr(service, "target_registry", load_registry)
    monkeypatch.setattr(service, "require_admin", admin)
    monkeypatch.setattr(service, "authorize_flow", authorize)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)
        async with scope() as session:
            owner = User(username=f"owner-{uuid4()}", password=uuid4().hex, is_active=True)
            other = User(username=f"other-{uuid4()}", password=uuid4().hex, is_active=True)
            actor = User(username=f"admin-{uuid4()}", password=uuid4().hex, is_active=True, is_superuser=True)
            session.add_all([owner, other, actor, MaintenanceState(enabled=True)])
            await session.flush()
            original = Folder(name="Original project", user_id=owner.id)
            moved = Folder(name="Moved project", user_id=owner.id)
            session.add_all([original, moved])
            await session.flush()
            report = await store_report(session, REPORT.read_bytes(), actor.id)
        yield scope, owner.id, other.id, actor.id, original.id, moved.id, report.id
    finally:
        await engine.dispose()


async def selected_flow(store, *, legacy=False, **metadata):
    scope, owner_id, _other_id, _actor_id, _original_id, _moved_id, _report_id = store
    async with scope() as session:
        flow = Flow(
            name="SQLite repair context",
            user_id=owner_id,
            data=graph(),
            version_token=None if legacy else uuid4(),
            **metadata,
        )
        session.add(flow)
        await session.flush()
        # SQLAlchemy insert defaults replace explicit None for Boolean fields.
        # Use an UPDATE to represent actual nullable historical rows.
        nulls = {key: value for key, value in metadata.items() if value is None}
        if nulls:
            await session.exec(update(Flow).where(Flow.id == flow.id).values(**nulls))
            await session.refresh(flow)
    payload = RepairApplyRequest(
        flows=[RepairSelection(flow_id=flow.id, version_token=flow.version_token, data_sha256=data_digest(flow.data))],
        target_sha256=data_digest(registry()),
        report_id=store[-1],
    )
    return flow, payload


CONTEXT_CHANGES = [
    ("folder_id", "original", "moved"),
    ("folder_id", "original", None),
    ("folder_id", None, "moved"),
    ("workspace_id", "original", "moved"),
    ("workspace_id", "original", None),
    ("workspace_id", None, "moved"),
    ("user_id", "owner", "other"),
    ("user_id", "owner", None),
    ("locked", False, True),
    ("locked", None, True),
    ("fs_path", None, "/synthetic/external/flow.json"),
    ("is_component", False, True),
    ("is_component", None, True),
]


@pytest.mark.parametrize("legacy", [False, True], ids=["token", "null-token"])
@pytest.mark.parametrize(("field", "before", "after"), CONTEXT_CHANGES)
async def test_sqlite_context_move_after_policy_validation_refuses_repair(
    sqlite_repairs, monkeypatch, field, before, after, legacy
):
    scope, owner_id, other_id, actor_id, original_id, moved_id, report_id = sqlite_repairs
    values = {"owner": owner_id, "other": other_id, "original": original_id, "moved": moved_id}
    previous = values.get(before, before)
    changed = values.get(after, after)
    initial = {} if field == "user_id" else {field: previous}
    flow, payload = await selected_flow(sqlite_repairs, legacy=legacy, **initial)
    observed = []

    async def allowed_before_move(current, owner, _updated, _registry):
        assert owner.id == owner_id
        observed.append(getattr(current, field))
        # This independent commit lands after validation but before the claim.
        # SQLite ignores SELECT FOR UPDATE, so a token-only claim would accept it.
        async with scope() as other:
            await other.exec(update(Flow).where(Flow.id == flow.id).values(**{field: changed}))

    monkeypatch.setattr(service, "validate_owner_policy", allowed_before_move)

    result = await service.apply_repairs(payload, actor_id)

    assert observed == [previous]
    [outcome] = result.results
    assert outcome.status == "conflict"
    assert outcome.reason_codes == ["source_changed"]
    async with scope() as session:
        persisted = await session.get(Flow, flow.id)
        assert getattr(persisted, field) == changed
        assert persisted.data == flow.data
        assert persisted.version_token == flow.version_token
        assert (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == flow.id))).all() == []
        records = (
            await session.exec(select(UpgradeReportRepair).where(UpgradeReportRepair.report_id == report_id))
        ).all()
        assert [json.loads(record.result_json)["status"] for record in records] == ["conflict"]


@pytest.mark.parametrize("legacy", [False, True], ids=["token", "null-token"])
async def test_sqlite_harmless_metadata_edit_does_not_block_repair(sqlite_repairs, monkeypatch, legacy):
    scope, _owner_id, _other_id, actor_id, _original_id, _moved_id, _report_id = sqlite_repairs
    flow, payload = await selected_flow(sqlite_repairs, legacy=legacy)
    changed = {
        "name": "Renamed during repair",
        "description": "A concurrent metadata edit",
        "tags": ["keep"],
        "updated_at": datetime.now(timezone.utc),
    }

    async def allowed_before_rename(*_args):
        async with scope() as other:
            await other.exec(update(Flow).where(Flow.id == flow.id).values(**changed))

    monkeypatch.setattr(service, "validate_owner_policy", allowed_before_rename)

    result = await service.apply_repairs(payload, actor_id)

    assert result.results[0].status == "updated"
    async with scope() as session:
        persisted = await session.get(Flow, flow.id)
        assert persisted.name == changed["name"]
        assert persisted.description == changed["description"]
        assert persisted.tags == changed["tags"]
        assert persisted.data != flow.data
        assert persisted.version_token != flow.version_token
        [recovery] = (await session.exec(select(FlowVersion).where(FlowVersion.flow_id == flow.id))).all()
        assert recovery.data == flow.data
        assert recovery.retained is True
