from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import BackgroundTasks, HTTPException, Request
from langflow.api.v1 import openai_responses
from langflow.schema import OpenAIResponsesRequest


def _flow(*, owner_id):
    return SimpleNamespace(
        id=uuid4(),
        user_id=owner_id,
        workspace_id=None,
        folder_id=None,
        data={
            "nodes": [
                {"data": {"type": "ChatInput"}},
                {"data": {"type": "ChatOutput"}},
            ]
        },
    )


def _request(model: str, *, stream: bool = False) -> OpenAIResponsesRequest:
    return OpenAIResponsesRequest(model=model, input="hello", stream=stream)


async def test_openai_execute_denial_matches_missing_flow_response(monkeypatch: pytest.MonkeyPatch) -> None:
    owner_id = uuid4()
    flow = _flow(owner_id=owner_id)

    async def deny(*_args, **_kwargs):
        raise HTTPException(status_code=403, detail="policy denied")

    monkeypatch.setattr(openai_responses, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=flow))
    monkeypatch.setattr(openai_responses, "ensure_flow_permission", deny)
    api_user = SimpleNamespace(id=uuid4())
    telemetry = SimpleNamespace(log_package_run=AsyncMock())

    denied = await openai_responses.create_response(
        request=_request(str(flow.id)),
        background_tasks=BackgroundTasks(),
        api_key_user=api_user,
        telemetry_service=telemetry,
        http_request=Request({"type": "http", "headers": []}),
    )
    monkeypatch.setattr(openai_responses, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=None))
    missing = await openai_responses.create_response(
        request=_request(str(flow.id)),
        background_tasks=BackgroundTasks(),
        api_key_user=api_user,
        telemetry_service=telemetry,
        http_request=Request({"type": "http", "headers": []}),
    )

    assert denied.model_dump() == missing.model_dump()
    assert denied.error["code"] == "flow_not_found"


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_openai_sync_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    sensitive_detail = "owner-openai-provider-secret"
    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    flow = _flow(owner_id=owner_id)

    monkeypatch.setattr(openai_responses, "get_flow_by_id_or_endpoint_name", AsyncMock(return_value=flow))
    monkeypatch.setattr(openai_responses, "ensure_flow_permission", AsyncMock())
    monkeypatch.setattr(
        openai_responses,
        "run_flow_for_openai_responses",
        AsyncMock(side_effect=RuntimeError(sensitive_detail)),
    )

    response = await openai_responses.create_response(
        request=_request(str(flow.id)),
        background_tasks=BackgroundTasks(),
        api_key_user=SimpleNamespace(id=caller_id),
        telemetry_service=SimpleNamespace(log_package_run=AsyncMock()),
        http_request=Request({"type": "http", "headers": []}),
    )

    if caller_kind == "owner":
        assert sensitive_detail in response.error["message"]
    else:
        assert response.error["message"] == "Workflow execution failed."
        assert sensitive_detail not in response.model_dump_json()


@pytest.mark.parametrize("caller_kind", ["delegate", "owner"])
async def test_openai_stream_fallback_error_depends_on_flow_ownership(
    monkeypatch: pytest.MonkeyPatch,
    caller_kind: str,
) -> None:
    sensitive_detail = "owner-openai-stream-secret"
    owner_id = uuid4()
    caller_id = owner_id if caller_kind == "owner" else uuid4()
    flow = _flow(owner_id=owner_id)

    async def idle_run_flow_generator(**_kwargs):
        return None

    async def failing_consumer(*_args, **_kwargs):
        raise RuntimeError(sensitive_detail)
        yield  # pragma: no cover

    monkeypatch.setattr(openai_responses, "run_flow_generator", idle_run_flow_generator)
    monkeypatch.setattr(openai_responses, "consume_and_yield", failing_consumer)

    response = await openai_responses.run_flow_for_openai_responses(
        flow=flow,
        request=_request(str(flow.id), stream=True),
        api_key_user=SimpleNamespace(id=caller_id),
        stream=True,
    )
    wire = "".join([chunk async for chunk in response.body_iterator])

    if caller_kind == "owner":
        assert sensitive_detail in wire
    else:
        assert "Workflow execution failed." in wire
        assert sensitive_detail not in wire
