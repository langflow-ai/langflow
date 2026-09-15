from __future__ import annotations

import asyncio
import contextlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException
from langflow.api.v1.schemas import FlowDataRequest
from langflow.events.event_manager import create_default_event_manager
from langflow.services.job_queue.service import JobQueueService
from lfx.schema.schema import InputValueRequest


async def test_generate_flow_events_sanitizes_cooperative_and_queue_fallback_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both generate-flow error paths obey the caller-visible policy."""
    from langflow.api import build

    sensitive_detail = "owner-provider-secret"

    @contextlib.asynccontextmanager
    async def fake_session_scope():
        yield SimpleNamespace()

    monkeypatch.setattr(build, "session_scope", fake_session_scope)
    monkeypatch.setattr(build, "get_chat_service", lambda: SimpleNamespace())
    monkeypatch.setattr(
        build,
        "get_telemetry_service",
        lambda: SimpleNamespace(log_package_playground=AsyncMock()),
    )
    monkeypatch.setattr(
        build,
        "build_graph_from_data",
        AsyncMock(side_effect=RuntimeError(sensitive_detail)),
    )

    queue: asyncio.Queue = asyncio.Queue()
    event_manager = create_default_event_manager(queue)
    producer = build.generate_flow_events(
        flow_id=uuid4(),
        background_tasks=BackgroundTasks(),
        event_manager=event_manager,
        inputs=InputValueRequest(input_value="hello", session="delegate-session"),
        data=FlowDataRequest(nodes=[], edges=[]),
        files=None,
        stop_component_id=None,
        start_component_id=None,
        log_builds=False,
        current_user=SimpleNamespace(id=uuid4()),
        flow_name="shared-flow",
        expose_error_details=False,
    )

    with pytest.raises(HTTPException, match="Workflow execution failed") as exc_info:
        await JobQueueService._guarded_task("job-id", producer, event_manager, queue)
    assert exc_info.value.status_code == 500

    payloads: list[dict] = []
    saw_sentinel = False
    while not queue.empty():
        _event_id, value, _timestamp = queue.get_nowait()
        if value is None:
            saw_sentinel = True
            continue
        payloads.append(json.loads(value))

    error_payloads = [payload for payload in payloads if payload["event"] == "error"]
    assert error_payloads
    assert saw_sentinel
    assert all("Workflow execution failed." in json.dumps(payload) for payload in error_payloads)
    assert sensitive_detail not in json.dumps(payloads)


@pytest.mark.no_blockbuster
async def test_anonymous_public_policy_error_stream_hides_policy_key_and_traceback(
    client, json_memory_chatbot_no_llm, logged_in_headers, monkeypatch
):
    from lfx.services.integration_policy import IntegrationPolicyService
    from lfx.services.policy_bundle import PolicyBundleService, PolicyBundleSnapshot

    flow_data = json.loads(json_memory_chatbot_no_llm)
    flow_data["access_type"] = "PUBLIC"
    created = await client.post("api/v1/flows/", json=flow_data, headers=logged_in_headers)
    assert created.status_code == 201, created.text
    policy_key = "integrations.qaprobe.doc.search"
    bundle = PolicyBundleService()
    bundle.publish(PolicyBundleSnapshot(revision=1, blocked_integration_action_keys={policy_key}))
    service = IntegrationPolicyService(policy_bundle_service=bundle)
    monkeypatch.setattr("lfx.services.deps.get_integration_policy_service", lambda: service)
    integration = SimpleNamespace(
        provider_id="qaprobe",
        capability_manifest=SimpleNamespace(
            capabilities=(
                SimpleNamespace(
                    id="qaprobe.doc.search",
                    policy_keys=(policy_key,),
                    component_ref="ChatInput",
                ),
            )
        ),
    )
    from lfx.extension.bundle_registry import get_default_registry

    monkeypatch.setattr(get_default_registry(), "list_integrations", lambda: [integration])
    client.cookies.clear()
    client.cookies.set("client_id", str(uuid4()))
    response = await client.post(f"api/v1/build_public_tmp/{created.json()['id']}/flow", json={})
    assert response.status_code == 200, response.text
    job_id = response.json()["job_id"]
    events = await client.get(f"api/v1/build_public_tmp/{job_id}/events")
    assert events.status_code == 200, events.text
    payloads = [json.loads(line) for line in events.text.splitlines() if line.strip()]
    errors = [payload for payload in payloads if payload.get("event") == "error"]
    assert errors, events.text
    assert "policy-blocked" in events.text
    assert policy_key not in events.text
    assert "Traceback" not in events.text
    assert "/lfx/" not in events.text
