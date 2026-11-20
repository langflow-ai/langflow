"""V2 JSON workflow models and wire contracts, without a backend dependency."""

from __future__ import annotations

import copy
import json
from uuid import UUID

import httpx
import pytest
from langflow_sdk import AsyncClient, Client
from langflow_sdk.exceptions import (
    LangflowAuthError,
    LangflowHTTPError,
    LangflowNotFoundError,
    LangflowValidationError,
)
from langflow_sdk.workflow_models import (
    WorkflowExecutionResponse,
    WorkflowExecutionResult,
    WorkflowJobResponse,
    WorkflowRunRequest,
    WorkflowStopResponse,
)
from pydantic import TypeAdapter, ValidationError

FLOW = "00000000-0000-0000-0000-000000000001"
JOB = "00000000-0000-0000-0000-000000000002"
STAMP = "2026-11-18T19:00:00.123456+00:00"
ADAPTER = TypeAdapter(WorkflowExecutionResult)


def job_payload(**updates):
    return {"object": "job", "flow_id": FLOW, "job_id": JOB, "created_timestamp": STAMP, "status": "queued", **updates}


def result_payload(**updates):
    return {
        "object": "response",
        "flow_id": FLOW,
        "created_timestamp": STAMP,
        "status": "completed",
        "output": {"reason": "single", "text": "", "source": "out"},
        "has_errors": False,
        **updates,
    }


def test_public_exports():
    import langflow_sdk
    from langflow_sdk import workflow_models

    for name in (
        "WorkflowRunRequest",
        "WorkflowExecutionResponse",
        "WorkflowJobResponse",
        "WorkflowExecutionResult",
        "WorkflowOutput",
        "WorkflowComponentOutput",
        "WorkflowErrorDetail",
        "WorkflowStopResponse",
    ):
        assert getattr(langflow_sdk, name) is getattr(workflow_models, name)
        assert name in langflow_sdk.__all__


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (job_payload(status="suspended"), WorkflowJobResponse),
        (result_payload(status="suspended", human_request={"request_id": "r"}), WorkflowExecutionResponse),
        (job_payload(status="future_state"), WorkflowJobResponse),
    ],
)
def test_discriminator_and_forward_status(payload, expected):
    assert isinstance(ADAPTER.validate_python(payload), expected)


@pytest.mark.parametrize("field", ["object", "flow_id", "status", "created_timestamp", "output", "has_errors"])
def test_execution_required_fields(field):
    payload = result_payload()
    payload.pop(field)
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(payload)


@pytest.mark.parametrize("field", ["object", "flow_id", "job_id", "status", "created_timestamp"])
def test_job_required_fields(field):
    payload = job_payload()
    payload.pop(field)
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(payload)


@pytest.mark.parametrize("value", [None, "other", 1])
def test_invalid_object(value):
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(job_payload(object=value))


@pytest.mark.parametrize("field", ["errors", "warnings", "inputs", "globals", "outputs", "has_errors", "output"])
def test_non_nullable_fields(field):
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(result_payload(**{field: None}))


def test_nested_values_extras_nulls_and_fields_set():
    payload = result_payload(
        session_id=None,
        job_id=None,
        human_request=None,
        future={"new": [1, None]},
        errors=[{"error": "e", "code": None, "details": {"deep": [1]}, "extra": False}],
        warnings=["notice"],
        inputs={"nested": {"a": 1}},
        globals={"X": "value"},
        outputs={
            "out": {
                "type": "data",
                "status": "future",
                "display_name": None,
                "content": [1, {"a": None}],
                "metadata": {"x": [False]},
                "new": "value",
            }
        },
    )
    result = ADAPTER.validate_python(payload)
    assert result.model_dump(exclude_unset=True) == payload
    assert result.created_timestamp == STAMP
    assert result.has_errors is False  # retain server value, do not derive from errors
    absent = ADAPTER.validate_python(result_payload())
    assert "job_id" not in absent.model_fields_set
    assert "session_id" not in absent.model_dump(exclude_unset=True)
    assert ADAPTER.validate_python(job_payload()).links == {}  # no fabricated links


@pytest.mark.parametrize("reason", ["single", "multiple", "none", "non_string", "failed", "future_reason"])
def test_output_reasons(reason):
    result = ADAPTER.validate_python(result_payload(output={"reason": reason, "text": None, "source": None}))
    assert result.output.reason == reason


def test_no_mutable_default_sharing():
    first = ADAPTER.validate_python(result_payload())
    second = ADAPTER.validate_python(result_payload())
    first.errors.append({"error": "new"})
    first.inputs["x"] = 1
    assert second.errors == []
    assert second.inputs == {}
    a, b = WorkflowRunRequest(flow_id=FLOW), WorkflowRunRequest(flow_id=FLOW)
    a.tweaks["x"] = 1
    assert b.tweaks == {}


@pytest.mark.parametrize("values", [{"mode": "stream"}, {"mode": "other"}, {"typo": True}, {"input_value": []}])
def test_invalid_request(values):
    with pytest.raises(ValidationError):
        WorkflowRunRequest(flow_id=FLOW, **values)


@pytest.mark.parametrize("async_mode", [False, True])
async def test_wire_methods_and_payload(async_mode):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/stop"):
            return httpx.Response(200, json={"job_id": JOB, "message": "opaque, do not interpret"})
        return httpx.Response(200, json=job_payload())

    transport = httpx.MockTransport(handler)
    values = {
        "flow_id": UUID(FLOW),
        "input_value": "",
        "session_id": "",
        "mode": "background",
        "tweaks": {},
        "globals": {},
        "output_ids": [],
        "data": {},
        "files": [],
        "start_component_id": "a",
        "stop_component_id": "b",
        "stream_protocol": "custom_adapter",
        "expose_graph_state": False,
        "idempotency_key": "key",
    }
    request = WorkflowRunRequest(**values)
    if async_mode:
        async with httpx.AsyncClient(
            base_url="https://example.test/prefix",
            transport=transport,
            headers={"x-api-key": "test", "x-custom": "preserved"},
        ) as http:
            client = AsyncClient("https://example.test/prefix", httpx_client=http)
            assert isinstance(await client.run_workflow(request), WorkflowJobResponse)
            await client.get_workflow(UUID(JOB))
            stop = await client.stop_workflow(UUID(JOB))
            await client.aclose()
            assert not http.is_closed
    else:
        with httpx.Client(
            base_url="https://example.test/prefix",
            transport=transport,
            headers={"x-api-key": "test", "x-custom": "preserved"},
        ) as http:
            client = Client("https://example.test/prefix", httpx_client=http)
            assert isinstance(client.run_workflow(request), WorkflowJobResponse)
            client.get_workflow(UUID(JOB))
            stop = client.stop_workflow(UUID(JOB))
            client.close()
            assert not http.is_closed
    assert isinstance(stop, WorkflowStopResponse)
    assert stop.message == "opaque, do not interpret"
    assert not hasattr(stop, "status")
    assert [x.method for x in seen] == ["POST", "GET", "POST"]
    assert [x.url.path for x in seen] == [
        "/prefix/api/v2/workflows",
        "/prefix/api/v2/workflows",
        "/prefix/api/v2/workflows/stop",
    ]
    assert dict(seen[1].url.params) == {"job_id": JOB}
    assert json.loads(seen[2].content) == {"job_id": JOB}
    values["flow_id"] = FLOW
    assert json.loads(seen[0].content) == values
    assert all(x.headers["x-api-key"] == "test" and x.headers["x-custom"] == "preserved" for x in seen)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("bypass", ["assignment", "construct", "copy"])
async def test_mode_bypass_never_contacts_network(async_mode, bypass):
    request = WorkflowRunRequest(flow_id=FLOW)
    if bypass == "assignment":
        request.mode = "stream"
    elif bypass == "construct":
        request = WorkflowRunRequest.model_construct(flow_id=FLOW, mode="stream")
    else:
        request = request.model_copy(update={"mode": "stream"})

    def handler(_request):
        pytest.fail("invalid request reached network")

    transport = httpx.MockTransport(handler)
    with pytest.raises(ValidationError):
        await invoke(async_mode, transport, "run_workflow", request)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, LangflowHTTPError),
        (401, LangflowAuthError),
        (403, LangflowAuthError),
        (404, LangflowNotFoundError),
        (408, LangflowHTTPError),
        (409, LangflowHTTPError),
        (422, LangflowValidationError),
        (500, LangflowHTTPError),
    ],
)
@pytest.mark.parametrize(
    "detail",
    [
        {"code": "JOB_FAILED", "error_detail": {"nested": [None, 1]}},
        {"code": "JOB_FAILED", "error_detail": None},
        "plain",
        ["list"],
        None,
    ],
)
async def test_structured_http_errors(async_mode, status, error, detail):
    def handler(_request):
        return httpx.Response(status, json={"detail": copy.deepcopy(detail)})

    transport = httpx.MockTransport(handler)
    with pytest.raises(error) as caught:
        await invoke(async_mode, transport, "get_workflow", JOB)
    assert caught.value.status_code == status
    assert caught.value.detail == detail


async def invoke(async_mode, transport, method, argument):
    if async_mode:
        async with httpx.AsyncClient(base_url="https://example.test", transport=transport) as http:
            return await getattr(AsyncClient("https://example.test", httpx_client=http), method)(argument)
    with httpx.Client(base_url="https://example.test", transport=transport) as http:
        return getattr(Client("https://example.test", httpx_client=http), method)(argument)


@pytest.mark.parametrize("async_mode", [False, True])
async def test_default_request_omits_none(async_mode):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=result_payload())

    result = await invoke(
        async_mode,
        httpx.MockTransport(handler),
        "run_workflow",
        WorkflowRunRequest(flow_id=FLOW, session_id=None, expose_graph_state=None),
    )
    assert isinstance(result, WorkflowExecutionResponse)
    assert seen == [
        {"flow_id": FLOW, "input_value": "", "mode": "sync", "tweaks": {}, "globals": {}, "stream_protocol": "langflow"}
    ]


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("method", ["run_workflow", "get_workflow", "stop_workflow"])
async def test_plain_http_error_on_each_method(async_mode, method):
    def handler(_request):
        return httpx.Response(500, text="plain failure")

    argument = WorkflowRunRequest(flow_id=FLOW) if method == "run_workflow" else JOB
    with pytest.raises(LangflowHTTPError) as caught:
        await invoke(async_mode, httpx.MockTransport(handler), method, argument)
    assert caught.value.detail == "plain failure"


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("payload", [None, [], {"object": "unknown"}, {"object": "response"}])
async def test_malformed_success(async_mode, payload):
    def handler(_request):
        return httpx.Response(200, content=json.dumps(payload).encode())

    with pytest.raises(ValidationError):
        await invoke(async_mode, httpx.MockTransport(handler), "get_workflow", JOB)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("failure", [httpx.ConnectError, httpx.ReadTimeout])
async def test_connection_and_network_timeout(async_mode, failure):
    from langflow_sdk import LangflowConnectionError

    def handler(request):
        message = "test transport failure"
        raise failure(message, request=request)

    expected = LangflowConnectionError if failure is httpx.ConnectError else httpx.ReadTimeout
    with pytest.raises(expected):
        await invoke(async_mode, httpx.MockTransport(handler), "get_workflow", JOB)


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize("mode", ["sync", "background"])
async def test_unknown_protocol_structured_rejection(async_mode, mode):
    detail = {"code": "UNKNOWN_STREAM_PROTOCOL", "available": ["agui", "langflow"]}

    def handler(request):
        assert json.loads(request.content)["mode"] == mode
        return httpx.Response(422, json={"detail": detail})

    with pytest.raises(LangflowValidationError) as caught:
        await invoke(
            async_mode,
            httpx.MockTransport(handler),
            "run_workflow",
            WorkflowRunRequest(flow_id=FLOW, mode=mode, stream_protocol="unknown"),
        )
    assert caught.value.detail == detail


@pytest.mark.parametrize("async_mode", [False, True])
async def test_owned_client_auth_and_context_close(async_mode):
    if async_mode:
        async with AsyncClient("https://example.test", api_key="test-key") as client:  # pragma: allowlist secret
            assert client._http.headers["x-api-key"] == "test-key"  # noqa: SLF001
        assert client._http.is_closed  # noqa: SLF001
    else:
        with Client("https://example.test", api_key="test-key") as client:  # pragma: allowlist secret
            assert client._http.headers["x-api-key"] == "test-key"  # noqa: SLF001
        assert client._http.is_closed  # noqa: SLF001


@pytest.mark.parametrize("async_mode", [False, True])
@pytest.mark.parametrize(
    ("status", "detail"),
    [
        (408, {"code": "EXECUTION_TIMEOUT", "job_id": JOB, "flow_id": FLOW}),
        (409, {"code": "JOB_NOT_CANCELLABLE", "mode": "sync"}),
        (409, {"code": "DUPLICATE_REQUEST", "flow_id": FLOW}),
        (422, {"code": "MODE_UNSUPPORTED_FIELDS", "fields": ["globals"]}),
        (500, {"code": "JOB_FAILED", "error_detail": None}),
    ],
)
async def test_real_error_contract_shapes(async_mode, status, detail):
    def handler(_request):
        return httpx.Response(status, json={"detail": detail})

    with pytest.raises(LangflowHTTPError) as caught:
        await invoke(async_mode, httpx.MockTransport(handler), "get_workflow", JOB)
    assert caught.value.status_code == status
    assert caught.value.detail == detail


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "message", "status": "completed", "content": None, "metadata": None},
        {"type": "data", "status": "completed", "content": 12},
        {"type": "data", "status": "completed", "content": {"nested": [True]}},
    ],
)
def test_component_content_and_nullable_metadata(payload):
    result = ADAPTER.validate_python(result_payload(outputs={"out": payload}))
    assert result.outputs["out"].model_dump(exclude_unset=True) == payload


@pytest.mark.parametrize("field", ["links", "errors", "globals", "job_id", "created_timestamp"])
def test_job_rejects_invalid_null(field):
    with pytest.raises(ValidationError):
        ADAPTER.validate_python(job_payload(**{field: None}))
