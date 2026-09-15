"""Auditing flow runs: who ran which flow, from where, and whether it worked.

A run writes nothing to the Flow, so its event is only the outcome: the actor,
the trigger (the execution family that started it), the duration, and a safe
failure code. Inputs, outputs, request bodies and error text are never stored.

Every run surface funnels through ``simple_run_flow`` or the build driver, so
decorating those two covers the API, webhooks, the Playground, MCP, OpenAI
Responses and the workflow API without instrumenting each route.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import time
from contextvars import ContextVar
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, ParamSpec, TypeVar
from uuid import UUID

from fastapi import HTTPException
from lfx.log.logger import logger
from sqlalchemy.exc import IntegrityError

from langflow.services.audit.attribution import resolve_audit_actor
from langflow.services.audit.operations import AuditedOperation, database_cause, record_denial
from langflow.services.audit.vocabulary import (
    FLOW_EXECUTE,
    AuditErrorCode,
    AuditEventType,
    AuditOperation,
    AuditResourceType,
    AuditResult,
)
from langflow.services.audit.writer import (
    AuditEventDraft,
    build_audit_event,
    is_audit_enabled,
    persist_audit_event_independently,
)
from langflow.services.database.models.audit_event.model import AuditEvent

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langflow.services.audit.attribution import AuditActor

P = ParamSpec("P")
R = TypeVar("R")

_INVALID_REQUEST_ERRORS = frozenset({"InvalidChatInputError", "TweakRefusedError", "CustomComponentValidationError"})
_SUSPENSIONS = frozenset({"GraphPausedException"})
RUN_WRITE_ATTEMPTS = 6
RUN_WRITE_TIMEOUT_SECONDS = 30.0
_pending_writes: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class FlowRunTarget:
    flow_id: UUID | None
    flow_name: str | None
    user_id: UUID | None
    trigger: str


@dataclass
class _RunOutcome:
    failed: bool = False
    paused: bool = False


_outcome: ContextVar[_RunOutcome | None] = ContextVar("langflow_audited_run", default=None)


def mark_run_failed() -> None:
    """A component failed but the driver finished normally; the run still failed."""
    outcome = _outcome.get()
    if outcome is not None:
        outcome.failed = True


def mark_run_paused() -> None:
    """A paused run has no outcome yet; the resume that completes it records one."""
    outcome = _outcome.get()
    if outcome is not None:
        outcome.paused = True


def classify_run_failure(exc: BaseException) -> AuditErrorCode:
    """Blame the request when the request was wrong, otherwise the run."""
    if type(exc).__name__ in _INVALID_REQUEST_ERRORS:
        return AuditErrorCode.INVALID_CONTENT
    status_code = getattr(exc, "status_code", None)
    if isinstance(exc, HTTPException) and status_code is not None and status_code < HTTPStatus.INTERNAL_SERVER_ERROR:
        if status_code == HTTPStatus.NOT_FOUND:
            return AuditErrorCode.FLOW_NOT_FOUND
        if status_code in {HTTPStatus.CONFLICT, HTTPStatus.LOCKED, HTTPStatus.FORBIDDEN}:
            return AuditErrorCode.CONSTRAINT_VIOLATION
        return AuditErrorCode.INVALID_CONTENT
    cause = database_cause(exc)
    if cause is AuditErrorCode.SERVICE_UNAVAILABLE:
        return cause
    return AuditErrorCode.FLOW_EXECUTION_FAILED


async def _record_run(
    target: FlowRunTarget,
    actor: AuditActor,
    started: float,
    error_code: AuditErrorCode | None,
) -> None:
    if target.flow_id is None:
        return
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    event = build_audit_event(
        AuditEventDraft(
            resource_type=AuditResourceType.FLOW,
            resource_id=target.flow_id,
            resource_name=target.flow_name,
            action=FLOW_EXECUTE,
            operation=AuditOperation.RUN,
            event_type=AuditEventType.ACTION,
            result=AuditResult.FAILED if error_code is not None else AuditResult.SUCCEEDED,
            actor=actor,
            details={"schema_version": 1, "run": {"trigger": target.trigger, "duration_ms": duration_ms}},
            error_code=error_code,
        )
    )
    task = asyncio.create_task(_persist_run_event(event))
    _pending_writes.add(task)
    task.add_done_callback(_pending_writes.discard)


async def _persist_run_event(event: AuditEvent) -> None:
    """Keep trying until the run's event is stored; the run's response does not wait for it.

    Runs contend for the same writer the run itself uses, and under SQLite a burst of
    concurrent runs held the lock longer than the failure path's short timeout: measured,
    60 simultaneous runs lost 19 events that way. The event keeps one id across attempts,
    so an attempt that timed out after its commit landed is recognized, not duplicated.
    """
    error = "unknown"
    for attempt in range(RUN_WRITE_ATTEMPTS):
        try:
            # A fresh instance per attempt: re-adding one the session already marked
            # persistent is a silent no-op, which would hide a lost event.
            await persist_audit_event_independently(AuditEvent(**event.model_dump()), timeout=RUN_WRITE_TIMEOUT_SECONDS)
        except IntegrityError:
            return
        except Exception as exc:  # noqa: BLE001
            error = type(exc).__name__
            await asyncio.sleep(min(0.5 * 2**attempt, 8.0))
        else:
            return
    await logger.aerror(
        "op=persist_run_event outcome=not_persisted request_id=%s resource_id=%s error=%s",
        event.request_id,
        event.resource_id,
        error,
    )


async def drain_run_audit_writes(timeout: float = 30.0) -> None:
    """Let pending run events land before the process stops."""
    if _pending_writes:
        await asyncio.wait(set(_pending_writes), timeout=timeout)


def audited_flow_run(
    describe: Callable[[dict[str, Any]], FlowRunTarget],
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Record one event per run with its outcome; ``describe`` reads the run's arguments."""

    def decorate(run: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
        signature = inspect.signature(run)

        @functools.wraps(run)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            if not is_audit_enabled() or _outcome.get() is not None:
                return await run(*args, **kwargs)
            bound = signature.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            target = describe(dict(bound.arguments))
            actor = resolve_audit_actor(target.user_id)
            outcome = _RunOutcome()
            token = _outcome.set(outcome)
            started = time.perf_counter()
            try:
                result = await run(*args, **kwargs)
            except Exception as exc:
                if not outcome.paused and type(exc).__name__ not in _SUSPENSIONS:
                    await _record_run(target, actor, started, classify_run_failure(exc))
                raise
            finally:
                _outcome.reset(token)
            if not outcome.paused:
                await _record_run(
                    target, actor, started, AuditErrorCode.FLOW_EXECUTION_FAILED if outcome.failed else None
                )
            return result

        return wrapper

    return decorate


async def record_run_denial(user_id: UUID | None, flow_id: UUID | str | None) -> None:
    """A refused ``flow:execute``, recorded once at the guard every run surface calls."""
    if flow_id is None or user_id is None:
        return
    await record_denial(
        AuditedOperation(
            resource_type=AuditResourceType.FLOW,
            action=FLOW_EXECUTE,
            operation=AuditOperation.RUN,
            actor=resolve_audit_actor(user_id),
            resource_id=UUID(str(flow_id)),
        )
    )
