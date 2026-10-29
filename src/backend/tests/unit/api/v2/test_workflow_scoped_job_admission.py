"""Background admission failures never execute components or complete successfully."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from langflow.api.v2 import workflow_background as workflow
from langflow.services.auth.context import AuthCredentialContext, get_current_auth_context, set_current_auth_context
from lfx.schema.workflow import JobStatus
from lfx.workflow.converters import ParsedWorkflowRun


@pytest.mark.parametrize("stream_protocol", ["langflow", "agui"])
@pytest.mark.parametrize("failure_type", [PermissionError, RuntimeError])
async def test_admission_failure_finishes_failed_with_safe_protocol_error(monkeypatch, stream_protocol, failure_type):
    job_id = uuid4()
    owner_id = uuid4()
    service = SimpleNamespace(
        authorize_job_start=AsyncMock(side_effect=failure_type("Private database failure detail")),
        get_job_by_job_id=AsyncMock(return_value=SimpleNamespace(status=JobStatus.QUEUED)),
        update_job_status=AsyncMock(),
    )
    stream = MagicMock(side_effect=AssertionError("Components must not run after admission failure"))
    monkeypatch.setattr(workflow, "get_job_service", lambda: service)
    monkeypatch.setattr(workflow, "_stream_event_frames", stream)
    previous = get_current_auth_context()
    credential = AuthCredentialContext(method="jwt")
    set_current_auth_context(credential)
    bg_run = workflow._BackgroundRun(user_id=str(owner_id), stream_protocol=stream_protocol)
    try:
        await workflow._buffer_background_run(
            bg_run=bg_run,
            flow=SimpleNamespace(id=uuid4(), name="Queued flow", user_id=owner_id),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), mode="background"),
            job_id=str(job_id),
            current_user=SimpleNamespace(id=owner_id),
            stream_protocol=stream_protocol,
        )
        assert get_current_auth_context() is credential
    finally:
        set_current_auth_context(previous)
    stream.assert_not_called()
    service.update_job_status.assert_awaited_once_with(job_id, JobStatus.FAILED, finished_timestamp=True)
    assert bg_run.done
    frames = [frame async for frame in bg_run.replay(0)]
    assert frames
    payloads = [
        json.loads(line.removeprefix("data: "))
        for frame in frames
        for line in frame.decode().splitlines()
        if line.startswith("data: ")
    ]
    if stream_protocol == "langflow":
        assert any(payload.get("event") == "error" for payload in payloads)
    else:
        assert any(payload.get("type") == "RUN_ERROR" for payload in payloads)
    assert "Private database failure detail" not in b"".join(frames).decode()


async def test_admission_cancellation_keeps_cancellation_path(monkeypatch):
    service = SimpleNamespace(authorize_job_start=AsyncMock(side_effect=asyncio.CancelledError))
    monkeypatch.setattr(workflow, "get_job_service", lambda: service)
    finalize = AsyncMock()
    monkeypatch.setattr(workflow, "_finalize_job_status", finalize)
    bg_run = workflow._BackgroundRun(user_id=str(uuid4()))
    with pytest.raises(asyncio.CancelledError):
        await workflow._buffer_background_run(
            bg_run=bg_run,
            flow=SimpleNamespace(id=uuid4()),
            parsed=ParsedWorkflowRun(flow_id=str(uuid4()), mode="background"),
            job_id=str(uuid4()),
            current_user=SimpleNamespace(id=uuid4()),
            stream_protocol="langflow",
        )
    assert bg_run.done
    assert bg_run.frames
    assert b"cancelled" in b"".join(bg_run.frames)
    finalize.assert_not_awaited()
