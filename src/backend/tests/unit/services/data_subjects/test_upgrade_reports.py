import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from langflow.api.v1.data_subjects_common import request_read
from langflow.services.data_subjects import upgrade_reports
from langflow.services.data_subjects.builder_account_steps import BUILDER_ACCOUNT_STEPS
from langflow.services.data_subjects.context import EraseContext, EraseStepPending
from langflow.services.data_subjects.engine import BUILDER_STEPS, is_retry_due, run_request
from langflow.services.data_subjects.errors import ReportOwnerAttributionRequiredError
from langflow.services.data_subjects.requests import approve, create_builder_request
from langflow.services.data_subjects.worker import DataSubjectEraseWorker
from langflow.services.database.models.data_subject_request import (
    DataSubjectRequest,
    DataSubjectRequestSource,
    DataSubjectRequestStatus,
)
from langflow.services.database.models.maintenance import MaintenanceState
from langflow.services.database.models.upgrade_report import UpgradeReport, UpgradeReportRepair
from langflow.services.database.models.user.model import User
from langflow.services.deps import session_scope
from sqlmodel import select

from tests.unit.services.data_subjects._seed import create_user


def _report(creator, *, owner=None, report_id=None):
    document = json.dumps({"flows": [{"owner": owner}]}, indent=4) + "\n\n"
    return UpgradeReport(
        id=report_id or uuid4(),
        created_by=creator,
        generated_at=datetime.now(timezone.utc),
        target_version="1.14.0",
        flow_count=1,
        warning_count=0,
        failing_count=0,
        content_sha256="a" * 64,
        document_json=document,
    )


def _repair(report_id, creator):
    return UpgradeReportRepair(
        report_id=report_id, created_by=creator, target_sha256="b" * 64, result_json='{"status":"unchanged"}'
    )


@pytest.mark.usefixtures("client")
async def test_builder_erase_removes_affected_archives_and_preserves_other_bytes(monkeypatch):
    subject = await create_user("report-erase-subject")
    admin = await create_user("report-erase-admin", superuser=True)
    monkeypatch.setattr(upgrade_reports, "REPORT_SCAN_BATCH_SIZE", 1)
    owned = _report(subject, report_id=UUID(int=2))
    named = _report(admin, owner={"id": str(subject).upper(), "username": "old-name"})
    # The creator's immutable ID independently establishes that this archive
    # is affected, even if its legacy owner entry has no usable ID.
    legacy = _report(subject, owner={"id": None, "username": "report-erase-subject"})
    # A renamed owner can have a different valid ID and the subject's reused
    # username. Its UUID remains authoritative, so this archive must survive.
    other = _report(admin, owner={"id": str(admin), "username": "report-erase-subject"}, report_id=UUID(int=1))
    original = other.document_json
    surviving_repair = _repair(other.id, admin)
    async with session_scope() as session:
        session.add_all([owned, named, legacy, other])
        await session.flush()
        session.add_all(
            [*(_repair(row.id, admin) for row in (owned, named, legacy)), _repair(other.id, subject), surviving_repair]
        )
        user = await session.get(User, subject)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=admin, source=DataSubjectRequestSource.ADMIN
        )
        await approve(session, request, admin)
        request_id = request.id
    pending_heartbeats = []

    async def heartbeat():
        async with session_scope() as session:
            saved = await session.get(DataSubjectRequest, request_id)
            if saved.cursor.get("data", {}).get("upgrade_report_after") == str(other.id):
                pending_heartbeats.append((saved.cursor["step"], saved.counts["upgrade_reports"]))

    assert await run_request(request_id, heartbeat=heartbeat) == DataSubjectRequestStatus.DONE.value
    assert (
        next(index for index, (name, _) in enumerate(BUILDER_STEPS) if name == "upgrade_reports"),
        0,
    ) in pending_heartbeats
    async with session_scope() as session:
        remaining = list((await session.exec(select(UpgradeReport))).all())
        assert [(row.id, row.document_json) for row in remaining] == [(other.id, original)]
        assert [row.id for row in (await session.exec(select(UpgradeReportRepair))).all()] == [surviving_repair.id]
        assert await session.get(User, subject) is None


@pytest.mark.parametrize("owner_id", [None, "not-a-uuid"], ids=["missing-owner-id", "invalid-owner-id"])
@pytest.mark.usefixtures("client")
async def test_ambiguous_reused_owner_name_holds_account_erasure_for_manual_review(owner_id):
    reused_name = "report-reused-owner"
    original_owner = await create_user(reused_name)
    async with session_scope() as session:
        original = await session.get(User, original_owner)
        original.username = "report-renamed-original-owner"
        session.add(original)
    subject = await create_user(reused_name)
    admin = await create_user("report-attribution-admin", superuser=True)
    owner = {"username": reused_name}
    if owner_id is not None:
        owner["id"] = owner_id
    archive = _report(admin, owner=owner)
    original_bytes = archive.document_json
    async with session_scope() as session:
        session.add(archive)
        user = await session.get(User, subject)
        request, _ = await create_builder_request(
            session, subject=user, requested_by=admin, source=DataSubjectRequestSource.ADMIN
        )
        await approve(session, request, admin)
        request_id = request.id

    assert await run_request(request_id) == DataSubjectRequestStatus.ERASING.value
    async with session_scope() as session:
        held = await session.get(DataSubjectRequest, request_id)
        saved_cursor, saved_error = dict(held.cursor), dict(held.error)
        assert held.finished_at is None
        assert held.error["code"] == ReportOwnerAttributionRequiredError.code
        assert held.error["manual_review_required"] is True
        assert held.error["retry_at"] is None
        assert held.error["details"]["report_id"] == str(archive.id)
        assert "manual attribution review" in held.error["details"]["action"]
        assert request_read(held).error == held.error
        assert not is_retry_due(held, datetime.now(timezone.utc) + timedelta(days=365))
        assert held.cursor["step"] == next(
            index for index, (name, _) in enumerate(BUILDER_STEPS) if name == "upgrade_reports"
        )
        assert await session.get(User, subject) is not None
        assert (await session.get(User, original_owner)).username == "report-renamed-original-owner"
        assert (await session.get(UpgradeReport, archive.id)).document_json == original_bytes

    assert request_id not in await DataSubjectEraseWorker()._due_requests()
    assert await run_request(request_id) == DataSubjectRequestStatus.ERASING.value
    async with session_scope() as session:
        held = await session.get(DataSubjectRequest, request_id)
        assert held.cursor == saved_cursor
        assert held.error == saved_error
        assert held.counts.get("upgrade_reports", 0) == 0
        assert await session.get(User, subject) is not None
        assert (await session.get(UpgradeReport, archive.id)).document_json == original_bytes


@pytest.mark.usefixtures("client")
async def test_report_erase_resumes_child_batches_and_rechecks_late_imports(monkeypatch):
    subject, other = uuid4(), uuid4()
    rows = [_report(other, report_id=UUID(int=index)) for index in range(1, 7)]
    rows[3].created_by = subject
    ctx = EraseContext(request_id=uuid4(), subject_user_id=subject)
    monkeypatch.setattr(upgrade_reports, "REPORT_SCAN_BATCH_SIZE", 2)
    monkeypatch.setattr("langflow.services.data_subjects.batching.BATCH_SIZE", 2)
    async with session_scope() as session:
        session.add_all(rows)
        await session.flush()
        session.add_all([_repair(rows[3].id, other) for _ in range(3)])
    counts = []
    for _ in range(6):
        async with session_scope() as session:
            counts.append(await upgrade_reports.erase_upgrade_reports(session, ctx))
        ctx = EraseContext(request_id=ctx.request_id, subject_user_id=subject, cursor=dict(ctx.cursor))
    assert isinstance(counts[0], EraseStepPending)
    assert counts[1:4] == [2, 1, 1]
    assert isinstance(counts[4], EraseStepPending)
    assert counts[5] == 0
    assert ctx.cursor == {}
    async with session_scope() as session:
        session.add(_report(subject, report_id=UUID(int=0)))
    async with session_scope() as session:
        assert await upgrade_reports.erase_upgrade_reports(session, ctx) == 1
    for _ in range(4):
        async with session_scope() as session:
            progress = await upgrade_reports.erase_upgrade_reports(session, ctx)
        if progress == 0:
            break
        assert isinstance(progress, EraseStepPending)
    else:
        pytest.fail("The final scan did not finish")
    async with session_scope() as session:
        assert [row.id for row in (await session.exec(select(UpgradeReport).order_by(UpgradeReport.id))).all()] == [
            row.id for row in rows if row.id != rows[3].id
        ]
        assert not (await session.exec(select(UpgradeReportRepair))).all()


@pytest.mark.usefixtures("client")
async def test_erasing_maintenance_setter_preserves_the_active_freeze():
    subject = uuid4()
    ctx = EraseContext(request_id=uuid4(), subject_user_id=subject)
    clear_setter = dict(BUILDER_ACCOUNT_STEPS)["maintenance_setter"]
    async with session_scope() as session:
        state = await session.get(MaintenanceState, 1)
        state.enabled, state.set_by, state.reason = True, subject, "Database upgrade"
        session.add(state)
    async with session_scope() as session:
        assert await clear_setter(session, ctx) == 1
    async with session_scope() as session:
        state = await session.get(MaintenanceState, 1)
        assert state.enabled is True
        assert state.set_by is None
        assert state.reason == "Database upgrade"
        assert await clear_setter(session, ctx) == 0
