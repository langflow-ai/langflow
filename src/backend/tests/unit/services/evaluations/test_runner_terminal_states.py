"""Keep finished evaluation runs unchanged when their workers resume late."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.services.database.models.evaluation import EvaluationResult, EvaluationRun
from langflow.services.database.models.jobs.model import Job, JobStatus, JobType
from langflow.services.evaluations import run_reconcile, runner
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

pytestmark = pytest.mark.no_blockbuster


@pytest.fixture
async def run_store(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runs.db'}")
    async with engine.begin() as connection:
        for model in (Job, EvaluationRun, EvaluationResult):
            await connection.run_sync(model.__table__.create)

    @asynccontextmanager
    async def session_scope():
        async with AsyncSession(engine, expire_on_commit=False) as session:
            yield session
            await session.commit()

    monkeypatch.setattr(runner, "session_scope", session_scope)
    try:
        yield session_scope
    finally:
        await engine.dispose()


async def _create_run(run_store, status, **values):
    run = EvaluationRun(
        evaluation_id=uuid4(),
        user_id=uuid4(),
        flow_name="Echo",
        dataset_name="Questions",
        dataset_revision=1,
        status=status,
        total_items=1,
        **values,
    )
    async with run_store() as session:
        session.add(run)
    return run


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
async def test_should_reject_results_after_a_run_finishes(run_store, status):
    summary = {"rows": {"total": 0}}
    run = await _create_run(run_store, status, summary=summary)
    row = EvaluationResult(run_id=run.id, position=0, input={"text": "q"}, passed=True)

    assert await runner._store_result(run.id, row) is False

    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert (stored.completed_items, stored.passed_items, stored.failed_items) == (0, 0, 0)
        assert stored.summary == summary
        assert (await session.exec(select(EvaluationResult))).all() == []


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_should_keep_storing_active_results_once(run_store, status):
    run = await _create_run(run_store, status)

    def row():
        return EvaluationResult(run_id=run.id, position=0, input={"text": "q"}, passed=True)

    assert await runner._store_result(run.id, row()) is True
    assert await runner._store_result(run.id, row()) is False
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert (stored.completed_items, stored.passed_items) == (1, 1)


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
async def test_should_preserve_a_terminal_run_when_a_worker_finalizes_late(run_store, status):
    finished_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    summary = {"rows": {"total": 0}}
    run = await _create_run(run_store, status, error="original", summary=summary, finished_at=finished_at)

    assert await runner._finalize_run(run.id, [], "completed", error="late") == (status, False)

    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert stored.error == "original"
        assert stored.summary == summary
        assert stored.finished_at.replace(tzinfo=timezone.utc) == finished_at


async def test_should_summarize_rows_saved_before_cancellation(run_store):
    finished_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    run = await _create_run(run_store, "cancelled", finished_at=finished_at, completed_items=1)
    async with run_store() as session:
        session.add(EvaluationResult(run_id=run.id, position=0, input={"text": "q"}, passed=True))

    assert await runner._finalize_run(run.id, [], "failed", error="late") == ("cancelled", False)

    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert stored.summary["rows"]["total"] == 1
        assert stored.error is None
        assert stored.finished_at.replace(tzinfo=timezone.utc) == finished_at


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
async def test_should_not_replace_a_terminal_state_during_context_failure(run_store, status):
    run = await _create_run(run_store, status, error="original")
    async with run_store() as session:
        await runner._fail_run(session, run.id, "late")
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert (stored.status, stored.error) == (status, "original")


async def test_should_stop_a_worker_after_stale_heartbeat_reconciliation(run_store, monkeypatch):
    old = datetime.now(timezone.utc) - timedelta(minutes=10)
    run = await _create_run(run_store, "running", job_id=uuid4(), created_at=old)
    async with run_store() as session:
        session.add(
            Job(
                job_id=run.job_id,
                flow_id=uuid4(),
                status=JobStatus.IN_PROGRESS,
                type=JobType.EVALUATION,
                created_timestamp=old,
                job_metadata={"heartbeat_at": old.isoformat()},
            )
        )
    monkeypatch.setattr(
        run_reconcile,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(background_lease_ttl_s=60)),
    )
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        await run_reconcile.reconcile_runs(session, [stored])
        assert stored.status == "failed"

    monkeypatch.setattr(runner, "CANCEL_POLL_SECONDS", 0)
    rows = asyncio.get_running_loop().create_future()
    original_status = runner._run_status

    async def observed_status(run_id):
        status = await original_status(run_id)
        asyncio.get_running_loop().call_soon(lambda: None if rows.done() else rows.set_result(None))
        return status

    monkeypatch.setattr(runner, "_run_status", observed_status)
    await runner._watch_for_cancel(run.id, rows)
    assert rows.cancelled()
    assert await runner._store_result(run.id, EvaluationResult(run_id=run.id, position=0, input={})) is False
    assert await runner._finalize_run(run.id, [], "completed") == ("failed", False)
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert stored.completed_items == 0
        assert stored.error == run_reconcile.WORKER_LOST_ERROR


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
async def test_should_not_launch_rows_if_a_run_finishes_while_context_loads(run_store, monkeypatch, status):
    run = await _create_run(run_store, "queued", config={"scorers": []})

    async def load_context(_run_id):
        async with run_store() as session:
            stored = await session.get(EvaluationRun, run.id)
            stored.status = status
            session.add(stored)
        return SimpleNamespace(
            run=run,
            settings=SimpleNamespace(evals_row_concurrency=1),
            rows=[(0, SimpleNamespace())],
        )

    execute = AsyncMock()
    monkeypatch.setattr(runner, "_load_context", load_context)
    monkeypatch.setattr(runner, "_run_one", execute)
    monkeypatch.setattr(runner, "_continue_comparison", AsyncMock())
    await runner.run_evaluation(run.id)

    execute.assert_not_awaited()
    async with run_store() as session:
        assert (await session.get(EvaluationRun, run.id)).status == status


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_should_finalize_active_runs_with_their_saved_results(run_store, status):
    run = await _create_run(run_store, status, completed_items=1)
    async with run_store() as session:
        session.add(EvaluationResult(run_id=run.id, position=0, input={"text": "q"}, passed=True))

    assert await runner._finalize_run(run.id, [], "completed") == ("completed", True)

    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert stored.summary["rows"]["total"] == 1
        assert stored.finished_at is not None
        assert stored.completed_items == 1


@pytest.mark.parametrize("status", ["queued", "running"])
async def test_should_record_context_failures_only_for_active_runs(run_store, status):
    run = await _create_run(run_store, status)
    async with run_store() as session:
        await runner._fail_run(session, run.id, "missing flow")
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert (stored.status, stored.error) == ("failed", "missing flow")


@pytest.mark.usefixtures("run_store")
async def test_should_drop_writes_for_a_deleted_run():
    run_id = uuid4()
    row = EvaluationResult(run_id=run_id, position=0, input={})
    assert await runner._store_result(run_id, row) is False
    assert await runner._finalize_run(run_id, [], "completed") == ("cancelled", False)


@pytest.mark.parametrize("aborted", [False, True])
async def test_should_not_advance_comparison_after_another_process_finishes_the_run(run_store, monkeypatch, aborted):
    run = await _create_run(
        run_store,
        "queued",
        config={"scorers": []},
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    context = SimpleNamespace(
        run=run,
        settings=SimpleNamespace(evals_row_concurrency=1),
        rows=[(0, SimpleNamespace())],
    )
    monkeypatch.setattr(runner, "_load_context", AsyncMock(return_value=context))
    monkeypatch.setattr(
        run_reconcile,
        "get_settings_service",
        lambda: SimpleNamespace(settings=SimpleNamespace(background_lease_ttl_s=60)),
    )

    async def finish_row(*_args):
        async with run_store() as session:
            stored = await session.get(EvaluationRun, run.id)
            await run_reconcile.reconcile_runs(session, [stored])
            assert stored.status == "failed"
        if aborted:
            reason = "stopped"
            raise runner.RunAbortedError(reason)

    continuation = AsyncMock()
    monkeypatch.setattr(runner, "_run_one", finish_row)
    monkeypatch.setattr(runner, "_continue_comparison", continuation)
    await runner.run_evaluation(run.id)

    continuation.assert_not_awaited()
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert stored.status == "failed"
        assert stored.error == run_reconcile.WORKER_LOST_ERROR


@pytest.mark.parametrize("aborted", [False, True])
async def test_should_advance_comparison_when_this_worker_finishes_the_run(run_store, monkeypatch, aborted):
    run = await _create_run(run_store, "queued", config={"scorers": []})
    context = SimpleNamespace(
        run=run,
        settings=SimpleNamespace(evals_row_concurrency=1),
        rows=[(0, SimpleNamespace())],
    )
    monkeypatch.setattr(runner, "_load_context", AsyncMock(return_value=context))

    async def finish_row(*_args):
        if aborted:
            reason = "stopped"
            raise runner.RunAbortedError(reason)

    continuation = AsyncMock()
    monkeypatch.setattr(runner, "_run_one", finish_row)
    monkeypatch.setattr(runner, "_continue_comparison", continuation)
    await runner.run_evaluation(run.id)

    continuation.assert_awaited_once_with(run.id)
    async with run_store() as session:
        stored = await session.get(EvaluationRun, run.id)
        assert stored.status == ("failed" if aborted else "completed")
