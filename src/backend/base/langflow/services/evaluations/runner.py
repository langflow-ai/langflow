"""Coordinator: execute every row of one run with bounded concurrency, then summarize."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger
from lfx.utils.flow_validation import prepare_flow_build_for_user
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from langflow.api.v1.global_variable_defaults import apply_global_variable_defaults
from langflow.services.database.models.evaluation import EvaluationResult, EvaluationRun
from langflow.services.database.models.evaluation.evaluation import TERMINAL_RUN_STATUSES
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.flow_version.model import FlowVersion
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.evaluations.dataset_service import all_items, item_text
from langflow.services.evaluations.failure_breaker import FailureBreaker, RunAbortedError, failure_detail
from langflow.services.evaluations.row_runner import execute_row, flow_policy_scope
from langflow.services.evaluations.row_scoring import score_row
from langflow.services.evaluations.summary import build_summary, summary_rows

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.services.settings.base import Settings
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.evaluation import DatasetItem

CANCEL_POLL_SECONDS = 2.0
USER_CANCELLED = "LANGFLOW_USER_CANCELLED"
INTERRUPTED_ERROR = "The run was interrupted before it finished."
ABORTED_ERROR = (
    "Stopped early: the last {count} rows failed with the same error, so the rest would most likely fail too. "
    "Fix the cause and re-run. Error: {error}"
)
_GLOBAL_LIMITS: dict[int, asyncio.Semaphore] = {}
_ACTIVE_RUNS: dict[UUID, asyncio.Future[Any]] = {}


@dataclass(frozen=True)
class RunContext:
    run: EvaluationRun
    flow: Flow
    user: User
    graph_data: dict[str, Any]
    rows: list[tuple[int, DatasetItem]]
    settings: Settings
    breaker: FailureBreaker


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _global_limit(capacity: int) -> asyncio.Semaphore:
    """One process-wide row limit per event loop (tests run several loops in one process)."""
    loop_key = id(asyncio.get_running_loop())
    semaphore = _GLOBAL_LIMITS.get(loop_key)
    if semaphore is None:
        semaphore = asyncio.Semaphore(capacity)
        _GLOBAL_LIMITS[loop_key] = semaphore
    return semaphore


def cancel_local_run(run_id: UUID) -> bool:
    rows = _ACTIVE_RUNS.get(run_id)
    if rows is None or rows.done():
        return False
    rows.cancel(USER_CANCELLED)
    return True


async def _pending_rows(session: AsyncSession, run: EvaluationRun) -> list[tuple[int, DatasetItem]]:
    """Rows to run, by dataset position; item writes are refused while a run is active, so positions hold."""
    if run.dataset_id is None:
        return []
    done = set((await session.exec(select(EvaluationResult.position).where(EvaluationResult.run_id == run.id))).all())
    items = await all_items(session, run.dataset_id, limit=run.total_items)
    return [(position, item) for position, item in enumerate(items) if position not in done]


async def _fail_run(session: AsyncSession, run_id: UUID, error: str) -> None:
    await session.exec(
        update(EvaluationRun).where(EvaluationRun.id == run_id).values(status="failed", error=error, finished_at=_now())
    )


async def _load_context(run_id: UUID) -> RunContext | None:
    settings = get_settings_service().settings
    async with session_scope() as session:
        run = (await session.exec(select(EvaluationRun).where(EvaluationRun.id == run_id))).first()
        if run is None or run.status in TERMINAL_RUN_STATUSES:
            return None
        version = (await session.exec(select(FlowVersion).where(FlowVersion.id == run.flow_version_id))).first()
        flow = (await session.exec(select(Flow).where(Flow.id == run.flow_id))).first()
        user = (await session.exec(select(User).where(User.id == run.user_id))).first()
        if version is None or version.data is None or flow is None or user is None:
            await _fail_run(session, run_id, "The flow, its pinned version or the user no longer exists.")
            return None
        rows = await _pending_rows(session, run)
        for row in (run, flow, user, *(item for _, item in rows)):
            session.expunge(row)
        version_data = dict(version.data)
    sanitized = await prepare_flow_build_for_user(version_data, is_superuser=bool(user.is_superuser))
    graph_data = sanitized if sanitized is not None else version_data
    graph_data = await apply_global_variable_defaults(graph_data, user.id)
    return RunContext(
        run=run,
        flow=flow,
        user=user,
        graph_data=graph_data,
        rows=rows,
        settings=settings,
        breaker=FailureBreaker(threshold=settings.evals_abort_after_identical_failures),
    )


class _RowNotStoredError(Exception):
    """Rolls back a row save whose run is gone or whose position is already stored."""


async def _store_result(run_id: UUID, result: EvaluationResult) -> bool:
    """Persist one row; False when the run row is gone (deleted with its project) or the row already exists."""
    errored = result.error is not None
    try:
        # Write first: on SQLite a read that later upgrades to a write fails at once instead of waiting.
        async with session_scope() as session:
            counted = await session.exec(
                update(EvaluationRun)
                .where(EvaluationRun.id == run_id)
                .values(
                    completed_items=EvaluationRun.completed_items + 1,
                    failed_items=EvaluationRun.failed_items + (1 if errored else 0),
                    passed_items=EvaluationRun.passed_items + (1 if result.passed else 0),
                )
            )
            if not counted.rowcount:
                raise _RowNotStoredError
            session.add(result)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise _RowNotStoredError from exc
    except _RowNotStoredError:
        return False
    return True


async def _record_row(ctx: RunContext, position: int, item: DatasetItem) -> None:
    settings = ctx.settings
    config = ctx.run.config
    question = item_text(item.input) or ""
    expected = item_text(item.expected_output)
    with flow_policy_scope(ctx.flow, ctx.user):
        execution = await execute_row(
            graph_data=ctx.graph_data,
            flow=ctx.flow,
            user=ctx.user,
            run_id=ctx.run.id,
            position=position,
            input_text=question,
            output_vertex_id=config["output_vertex_id"],
        )
        scored = await score_row(
            scorers=config["scorers"],
            threshold=float(config["pass_threshold"]),
            question=question,
            actual=execution.actual,
            expected=expected,
            errored=execution.error is not None,
            user_id=ctx.user.id,
            judge_max_output_tokens=settings.evals_judge_max_output_tokens,
        )
    if ctx.breaker.tripped_with is not None:
        return
    actual = execution.actual
    limit = settings.evals_actual_output_max_chars
    truncated = actual is not None and len(actual) > limit
    await _store_result(
        ctx.run.id,
        EvaluationResult(
            run_id=ctx.run.id,
            dataset_item_id=item.id,
            position=position,
            input=item.input,
            expected_output=item.expected_output,
            actual_output=actual[:limit] if actual is not None else None,
            output_truncated=truncated,
            error=execution.error,
            scores=scored.scores_json(),
            passed=scored.passed,
            duration_ms=execution.duration_ms,
            tokens_flow=execution.tokens,
            tokens_judge=scored.judge_tokens,
            cost_flow=execution.cost,
            cost_judge=scored.judge_cost,
            trace_id=execution.trace_id,
        ),
    )
    _check_breaker(ctx, failure_detail(execution.error, scored, config["scorers"]))


def _check_breaker(ctx: RunContext, detail: str | None) -> None:
    if ctx.breaker.record(detail):
        msg = ABORTED_ERROR.format(count=ctx.breaker.threshold, error=ctx.breaker.tripped_with)
        raise RunAbortedError(msg)


async def _record_timeout(ctx: RunContext, position: int, item: DatasetItem) -> None:
    if ctx.breaker.tripped_with is not None:
        return
    timeout = int(ctx.settings.evals_row_timeout_s)
    stored = await _store_result(
        ctx.run.id,
        EvaluationResult(
            run_id=ctx.run.id,
            dataset_item_id=item.id,
            position=position,
            input=item.input,
            expected_output=item.expected_output,
            error=f"Timed out after {timeout} seconds",
            scores={},
            passed=False,
            duration_ms=timeout * 1000,
        ),
    )
    if stored:
        _check_breaker(ctx, f"Timed out after {timeout} seconds")


async def _run_one(ctx: RunContext, position: int, item: DatasetItem, run_limit: asyncio.Semaphore) -> None:
    # Per-run slot first: a run waiting on its own limit must not hold a process-wide slot.
    async with run_limit, _global_limit(ctx.settings.evals_max_concurrency):
        # A run already stopped early must not start (or pay for) any further row.
        if ctx.breaker.tripped_with is not None:
            return
        try:
            await asyncio.wait_for(_record_row(ctx, position, item), timeout=ctx.settings.evals_row_timeout_s)
        except asyncio.TimeoutError:
            await _record_timeout(ctx, position, item)


async def _run_status(run_id: UUID) -> str | None:
    async with session_scope() as session:
        return (await session.exec(select(EvaluationRun.status).where(EvaluationRun.id == run_id))).first()


async def _watch_for_cancel(run_id: UUID, rows: asyncio.Future[Any]) -> None:
    """Pick up a cancel written by any process (another pod, or this one) while rows run."""
    while not rows.done():
        await asyncio.sleep(CANCEL_POLL_SECONDS)
        try:
            status = await _run_status(run_id)
        except Exception as exc:  # noqa: BLE001 - a failed poll must not end the run; the next poll retries
            await logger.awarning(f"evals_cancel_poll_failed run_id={run_id} error={type(exc).__name__}")
            continue
        # A missing run was deleted with its project: stop spending on it.
        if status in {"cancelled", None}:
            rows.cancel(USER_CANCELLED)
            return


async def _finalize_run(run_id: UUID, scorer_names: list[str], status: str, error: str | None = None) -> str:
    """Write the summary and the terminal status; a cancel written meanwhile wins. Returns the final status."""
    async with session_scope() as session:
        results = await summary_rows(session, run_id)
        values: dict[str, Any] = {"summary": build_summary(results, scorer_names), "finished_at": _now()}
        await session.exec(update(EvaluationRun).where(EvaluationRun.id == run_id).values(**values))
        terminal: dict[str, Any] = {"status": status}
        if error is not None:
            terminal["error"] = error
        await session.exec(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id, col(EvaluationRun.status) != "cancelled")
            .values(**terminal)
        )
        final = (await session.exec(select(EvaluationRun.status).where(EvaluationRun.id == run_id))).first()
    # A run deleted with its project counts as cancelled.
    return str(final) if final is not None else "cancelled"


async def run_evaluation(run_id: UUID) -> None:
    ctx = await _load_context(run_id)
    if ctx is None:
        return
    scorer_names = [spec["name"] for spec in ctx.run.config["scorers"]]
    async with session_scope() as session:
        await session.exec(
            update(EvaluationRun)
            .where(EvaluationRun.id == run_id, EvaluationRun.status == "queued")
            .values(status="running", started_at=_now())
        )
    run_limit = asyncio.Semaphore(ctx.settings.evals_row_concurrency)
    tasks = [asyncio.ensure_future(_run_one(ctx, position, item, run_limit)) for position, item in ctx.rows]
    rows = asyncio.gather(*tasks)
    _ACTIVE_RUNS[run_id] = rows
    watcher = asyncio.create_task(_watch_for_cancel(run_id, rows))
    try:
        await rows
    except asyncio.CancelledError:
        final = await _finalize_run(run_id, scorer_names, "failed", error=INTERRUPTED_ERROR)
        await logger.ainfo(f"evals_run_stopped run_id={run_id} status={final}")
        raise asyncio.CancelledError(USER_CANCELLED if final == "cancelled" else "") from None
    except Exception as exc:
        # A failed gather is already done, so cancelling it would not reach the siblings: cancel each row.
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if isinstance(exc, RunAbortedError):
            await _finalize_run(run_id, scorer_names, "failed", error=str(exc))
            await logger.awarning(f"evals_run_aborted run_id={run_id} reason=repeated_failure")
            return
        await _finalize_run(run_id, scorer_names, "failed", error=f"Run failed: {type(exc).__name__}")
        raise
    finally:
        _ACTIVE_RUNS.pop(run_id, None)
        watcher.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await watcher
    await _finalize_run(run_id, scorer_names, "completed")
    await logger.ainfo(f"evals_run_completed run_id={run_id} rows={len(ctx.rows)}")
