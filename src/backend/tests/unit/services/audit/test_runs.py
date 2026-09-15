"""Run auditing: one outcome per run, none for a pause or a cancellation, and a safe code."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from langflow.services.audit import runs as runs_module
from langflow.services.audit.details import AuditContractError, validate_details
from langflow.services.audit.runs import (
    FlowRunTarget,
    audited_flow_run,
    classify_run_failure,
    drain_run_audit_writes,
    mark_run_failed,
    mark_run_paused,
)
from langflow.services.audit.vocabulary import AuditErrorCode, AuditOperation, AuditResourceType, AuditResult
from sqlalchemy.exc import OperationalError

from .test_writer_after_rollback import _events_for as _stored_events


async def _events_for(resource_ids):
    await drain_run_audit_writes()
    return await _stored_events(resource_ids)


FLOW = AuditResourceType.FLOW


class GraphPausedException(Exception):  # noqa: N818
    """Stands in for the engine's pause signal, which is matched by name."""


class TweakRefusedError(Exception):
    """Stands in for the run surface's tweak refusal, which is matched by name."""


def _target(flow_id, flow_name: str | None = "f") -> FlowRunTarget:
    return FlowRunTarget(flow_id=flow_id, flow_name=flow_name, user_id=uuid4(), trigger="v1_run")


def _run(behaviour, flow_name: str | None = "f"):
    @audited_flow_run(lambda arguments: _target(arguments["flow_id"], flow_name))
    async def run(flow_id):  # noqa: ARG001 - read by the decorator, not the body
        return await behaviour()

    return run


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_run_that_returns_records_one_success_with_its_trigger():
    flow_id = uuid4()

    async def ok():
        return "done"

    assert await _run(ok)(flow_id) == "done"

    [event] = await _events_for([flow_id])
    assert (event.action, event.operation, event.result, event.error_code) == ("flow:execute", "run", "succeeded", None)
    assert event.details["run"]["trigger"] == "v1_run"


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_run_whose_surface_does_not_know_the_name_records_the_stored_flow_name(client, logged_in_headers):
    long_name = f"named-{uuid4().hex}-" + "x" * 300
    created = await client.post("api/v1/flows/", json={"name": long_name, "data": {}}, headers=logged_in_headers)
    flow_id = UUID(created.json()["id"])
    missing_id = uuid4()

    async def ok():
        return None

    await _run(ok, flow_name=None)(flow_id)
    await _run(ok, flow_name=None)(missing_id)

    [event] = [stored for stored in await _events_for([flow_id]) if stored.operation == "run"]
    assert event.resource_name == created.json()["name"][:255]
    [unknown] = await _events_for([missing_id])
    assert unknown.resource_name is None


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_failure_reported_without_raising_is_still_a_failed_run():
    flow_id = uuid4()

    async def component_failed():
        mark_run_failed()

    await _run(component_failed)(flow_id)

    [event] = await _events_for([flow_id])
    assert (event.result, event.error_code) == ("failed", "FLOW_EXECUTION_FAILED")


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_raised_failure_is_recorded_and_re_raised_untouched():
    flow_id = uuid4()
    boom = RuntimeError("secret detail that must not be stored")

    async def raises():
        raise boom

    with pytest.raises(RuntimeError) as raised:
        await _run(raises)(flow_id)

    assert raised.value is boom
    [event] = await _events_for([flow_id])
    assert (event.result, event.error_code) == ("failed", "FLOW_EXECUTION_FAILED")
    assert "secret detail" not in str(event.details)


@pytest.mark.usefixtures("client", "audit_enabled")
@pytest.mark.parametrize("pause", ["marked", "raised"])
async def test_a_paused_run_has_no_outcome_yet(pause):
    flow_id = uuid4()

    async def pauses():
        if pause == "marked":
            mark_run_paused()
            return
        raise GraphPausedException

    if pause == "raised":
        with pytest.raises(GraphPausedException):
            await _run(pauses)(flow_id)
    else:
        await _run(pauses)(flow_id)

    assert await _events_for([flow_id]) == []


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_cancelled_run_records_nothing():
    flow_id = uuid4()

    async def slow():
        await asyncio.sleep(10)

    task = asyncio.create_task(_run(slow)(flow_id))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert await _events_for([flow_id]) == []


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_run_started_inside_another_run_is_not_counted_twice():
    flow_id = uuid4()

    async def inner_ok():
        return None

    async def outer():
        await _run(inner_ok)(flow_id)

    await _run(outer)(flow_id)

    assert len(await _events_for([flow_id])) == 1


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (TweakRefusedError(), AuditErrorCode.INVALID_CONTENT),
        (HTTPException(400, "bad input"), AuditErrorCode.INVALID_CONTENT),
        (HTTPException(401, "end user required"), AuditErrorCode.INVALID_CONTENT),
        (HTTPException(404, "Flow not found"), AuditErrorCode.FLOW_NOT_FOUND),
        (HTTPException(403, "connection not allowed"), AuditErrorCode.CONSTRAINT_VIOLATION),
        (HTTPException(500, "Workflow failed"), AuditErrorCode.FLOW_EXECUTION_FAILED),
        (ValueError("component blew up"), AuditErrorCode.FLOW_EXECUTION_FAILED),
    ],
)
def test_run_failures_blame_the_request_only_when_the_request_was_wrong(exc, expected):
    assert classify_run_failure(exc) is expected


def test_a_run_event_carries_only_its_trigger_and_duration():
    stored = validate_details(
        FLOW,
        AuditResult.SUCCEEDED,
        {"schema_version": 1, "run": {"trigger": "webhook", "duration_ms": 12}},
        AuditOperation.RUN,
    )

    assert stored == {"schema_version": 1, "run": {"trigger": "webhook", "duration_ms": 12}}


@pytest.mark.parametrize(
    ("details", "operation"),
    [
        ({"schema_version": 1, "written_fields": ["data"]}, AuditOperation.RUN),
        ({"schema_version": 1, "run": {"trigger": "v1_run", "inputs": {"q": "x"}}}, AuditOperation.RUN),
        ({"schema_version": 1, "run": {"trigger": "Not A Trigger"}}, AuditOperation.RUN),
        ({"schema_version": 1, "run": {"duration_ms": -1}}, AuditOperation.RUN),
        ({"schema_version": 1, "run": {"trigger": "v1_run"}}, AuditOperation.PATCH),
    ],
)
def test_a_run_cannot_carry_changes_values_or_a_malformed_origin(details, operation):
    with pytest.raises(AuditContractError):
        validate_details(FLOW, AuditResult.SUCCEEDED, details, operation)


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_run_event_that_cannot_be_written_yet_is_retried_until_it_lands(monkeypatch):
    flow_id = uuid4()
    real_persist = runs_module.persist_audit_event_independently
    calls = 0

    async def locked_once(event, *, timeout):
        nonlocal calls
        calls += 1
        if calls == 1:
            msg = "database is locked"
            raise OperationalError(msg, None, Exception(msg))
        return await real_persist(event, timeout=timeout)

    monkeypatch.setattr(runs_module, "persist_audit_event_independently", locked_once)

    async def ok():
        return None

    await _run(ok)(flow_id)

    assert len(await _events_for([flow_id])) == 1
    assert calls == 2


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_an_attempt_that_timed_out_after_committing_is_not_duplicated(monkeypatch):
    flow_id = uuid4()
    real_persist = runs_module.persist_audit_event_independently
    calls = 0

    async def committed_then_timed_out(event, *, timeout):
        nonlocal calls
        calls += 1
        await real_persist(event, timeout=timeout)
        if calls == 1:
            raise TimeoutError

    monkeypatch.setattr(runs_module, "persist_audit_event_independently", committed_then_timed_out)

    async def ok():
        return None

    await _run(ok)(flow_id)

    assert len(await _events_for([flow_id])) == 1
    assert calls == 2


@pytest.mark.usefixtures("client", "audit_enabled")
async def test_a_run_event_that_never_lands_is_logged_and_never_breaks_the_run(monkeypatch):
    flow_id = uuid4()
    monkeypatch.setattr(runs_module, "RUN_WRITE_ATTEMPTS", 2)

    async def unavailable(event, *, timeout):  # noqa: ARG001
        msg = "database is unavailable"
        raise OperationalError(msg, None, Exception(msg))

    monkeypatch.setattr(runs_module, "persist_audit_event_independently", unavailable)

    async def ok():
        return "result"

    assert await _run(ok)(flow_id) == "result"
    assert await _events_for([flow_id]) == []
