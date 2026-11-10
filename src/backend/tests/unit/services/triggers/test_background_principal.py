"""Trigger identity must reach the real background factory and durable replay."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langflow.api.utils.execution_principal import execution_principal_for
from langflow.api.v2 import workflow
from langflow.services.database.models.trigger.model import Trigger, TriggerEvent
from langflow.services.deps import get_background_execution_service
from langflow.services.triggers.dispatcher import build_submit_request
from pydantic import ValidationError

pytestmark = pytest.mark.no_blockbuster


@pytest.mark.parametrize("family", ["trigger_push", "trigger_listener"])
@pytest.mark.parametrize("resume", [None, {"checkpoint_id": "resume"}])
async def test_trigger_background_connection_principal_stays_non_interactive(monkeypatch, family, resume):
    owner_id, flow_id = uuid4(), uuid4()
    trigger = Trigger(flow_id=flow_id, user_id=owner_id, name="Trigger", kind="schedule")
    event = TriggerEvent(trigger_id=trigger.id, dedupe_key="tick")
    request = build_submit_request(trigger=trigger, event=event, binding_data=None, family=family)
    user = SimpleNamespace(id=owner_id)
    flow = SimpleNamespace(id=flow_id, user_id=owner_id, name="Flow")
    monkeypatch.setattr(workflow, "resolve_flow_for_execution", AsyncMock(return_value=flow))
    seen = []

    async def stream(**kwargs):
        principal = execution_principal_for(
            kwargs["execution_family"], user=kwargs["current_user"], flow_owner_id=kwargs["source_flow_owner_id"]
        )
        seen.append(principal)
        yield b"error", "error"

    monkeypatch.setattr(workflow, "_stream_event_frames", stream)
    # Use the same plaintext-safe request projection persisted for restart.
    request = get_background_execution_service()._redact_request(request)
    source = workflow._default_frame_source_factory(
        request=request, flow_id=flow_id, user=user, adapter=SimpleNamespace(terminal_error_type="error")
    )
    assert [frame async for frame in source(job_id=uuid4(), resume=resume)] == [(b"error", "error")]
    assert len(seen) == 1
    assert seen[0].family == family
    assert seen[0].kind == "flow_owner"
    assert seen[0].user_id == str(owner_id)
    assert seen[0].interactive is False
    assert seen[0].allow_explicit_shares is False


def test_public_workflow_request_cannot_choose_the_internal_trigger_family():
    with pytest.raises(ValidationError):
        workflow.WorkflowRunRequest(flow_id=str(uuid4()), execution_family="trigger_listener")
    with pytest.raises(ValueError, match="execution family"):
        workflow._parse_persisted_workflow_request({"flow_id": str(uuid4()), "execution_family": "v1_run"})
