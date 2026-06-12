from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx.components import jungle_grid
from lfx.components.jungle_grid._client import (
    JungleGridClient,
    JungleGridError,
    normalize_base_url,
    parse_json_field,
    sanitize,
    validate_command,
    validate_environment,
    validate_expected_artifacts,
    validate_input_references,
)
from lfx.components.jungle_grid.artifact_download_url import JungleGridCreateArtifactDownloadURLComponent
from lfx.components.jungle_grid.cancel_job import JungleGridCancelJobComponent
from lfx.components.jungle_grid.create_job_input_upload import JungleGridCreateJobInputUploadComponent
from lfx.components.jungle_grid.estimate_job import JungleGridEstimateJobComponent
from lfx.components.jungle_grid.get_job_events import JungleGridGetJobEventsComponent
from lfx.components.jungle_grid.get_job_logs import JungleGridGetJobLogsComponent
from lfx.components.jungle_grid.get_job_runtime import JungleGridGetJobRuntimeComponent
from lfx.components.jungle_grid.get_job_status import JungleGridGetJobStatusComponent
from lfx.components.jungle_grid.list_job_artifacts import JungleGridListJobArtifactsComponent
from lfx.components.jungle_grid.list_job_inputs import JungleGridListJobInputsComponent
from lfx.components.jungle_grid.list_jobs import JungleGridListJobsComponent
from lfx.components.jungle_grid.submit_job import JungleGridSubmitJobComponent

from lfx import components

API_KEY = "jg_test_secret_value"
SIGNED_URL = "https://storage.example.test/signed/test-token"
ALL_COMPONENTS = (
    JungleGridEstimateJobComponent,
    JungleGridSubmitJobComponent,
    JungleGridCreateJobInputUploadComponent,
    JungleGridListJobInputsComponent,
    JungleGridListJobsComponent,
    JungleGridGetJobStatusComponent,
    JungleGridGetJobEventsComponent,
    JungleGridGetJobRuntimeComponent,
    JungleGridGetJobLogsComponent,
    JungleGridCancelJobComponent,
    JungleGridListJobArtifactsComponent,
    JungleGridCreateArtifactDownloadURLComponent,
)


def _response(
    status_code: int = 200,
    payload: dict[str, Any] | None = None,
    *,
    text: str | None = None,
) -> httpx.Response:
    request = httpx.Request("GET", "https://api.junglegrid.dev/test")
    if text is not None:
        return httpx.Response(status_code, text=text, request=request)
    return httpx.Response(status_code, json={} if payload is None else payload, request=request)


def _defaults() -> dict[str, Any]:
    return {
        "api_key": API_KEY,
        "api_base_url": "https://api.junglegrid.dev",
        "workload_name": "langflow-test",
        "workload_type": "batch",
        "model_size": 1,
        "image": "python:3.11-slim",
        "command": '["python", "-c", "print(1)"]',
        "args": "[]",
        "routing_mode": "cost",
        "template": "",
        "notes": "",
        "env": "{}",
        "input_files": "[]",
        "script_files": "[]",
        "script_file": "",
        "expected_artifacts": '["/workspace/artifacts/output.txt"]',
        "metadata": "{}",
        "callback_url": "",
        "callback_auth_token": "",
        "callback_metadata": "{}",
        "filename": "audio.wav",
        "content_type": "audio/wav",
        "kind": "input",
        "limit": 10,
        "cursor": "",
        "status": "",
        "job_id": "job_test",
        "artifact_id": "artifact_test",
        "reason": "test cancellation",
    }


def _component(component_class, **overrides):
    values = _defaults() | overrides
    input_names = {input_.name for input_ in component_class.inputs}
    return component_class(**{key: value for key, value in values.items() if key in input_names})


async def _run(component, payload: dict[str, Any] | None = None) -> tuple[Any, AsyncMock]:
    method = getattr(component, component.outputs[0].method)
    mocked = AsyncMock(return_value=_response(payload={} if payload is None else payload))
    with patch("httpx.AsyncClient.request", mocked):
        result = await method()
    return result, mocked


@pytest.mark.parametrize("component_class", ALL_COMPONENTS)
def test_all_components_expose_expected_inputs_outputs_and_metadata(component_class) -> None:
    component = _component(component_class)
    node = component.to_frontend_node()["data"]["node"]
    input_names = {input_.name for input_ in component_class.inputs}
    assert {"api_key", "api_base_url"} <= input_names
    assert component_class.outputs[0].name == "data"
    assert node["icon"] == "JungleGrid"
    assert node["display_name"] == component_class.display_name
    assert component_class.__doc__


def test_bundle_discovery_and_public_exports() -> None:
    assert "jungle_grid" in components.__all__
    assert "jungle_grid" in dir(components)
    assert components.jungle_grid is jungle_grid
    assert set(jungle_grid.__all__) == {component.__name__ for component in ALL_COMPONENTS}
    assert set(jungle_grid.__dir__()) == set(jungle_grid.__all__)
    for component_class in ALL_COMPONENTS:
        assert getattr(jungle_grid, component_class.__name__) is component_class


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://api.junglegrid.dev", "https://api.junglegrid.dev"),
        ("https://workspace.junglegrid.example", "https://workspace.junglegrid.example"),
        ("https://api.junglegrid.dev/", "https://api.junglegrid.dev"),
    ],
)
def test_normalize_base_url_accepts_valid_origins(value: str, expected: str) -> None:
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "https://api.junglegrid.dev/v1",
        "https://api.junglegrid.dev?debug=true",
        "https://api.junglegrid.dev#fragment",
        "http://api.junglegrid.dev",
        "https:///missing-host",
        "https://user:password@api.junglegrid.dev",
    ],
)
def test_normalize_base_url_rejects_unsafe_values(value: str) -> None:
    with pytest.raises(JungleGridError, match="path-free HTTPS URL with a hostname"):
        normalize_base_url(value)


def test_json_helpers_preserve_empty_collections_and_structured_values() -> None:
    assert parse_json_field("[]", "Args", list) == []
    assert parse_json_field({}, "Metadata", dict) == {}
    assert validate_environment("{}") == {}
    assert validate_input_references("[]", "Input Files") == []


@pytest.mark.parametrize("value", ["{", '"text"', "1"])
def test_json_validation_has_specific_errors(value: str) -> None:
    with pytest.raises(JungleGridError, match=r"Metadata must be (valid JSON|a JSON object)"):
        parse_json_field(value, "Metadata", dict)


@pytest.mark.parametrize("value", ['["python", ""]', '["python", 1]', "[]"])
def test_command_array_validation_rejects_invalid_entries(value: str) -> None:
    with pytest.raises(JungleGridError, match=r"Command must (contain|be)"):
        validate_command(value)


def test_command_validation_preserves_legacy_string() -> None:
    assert validate_command("python") == "python"
    assert validate_command('["python", "script.py"]') == ["python", "script.py"]


def test_environment_validation_rejects_non_string_values_without_echoing_them() -> None:
    secret_value = "do-not-echo"  # noqa: S105
    with pytest.raises(JungleGridError, match="string values") as exc_info:
        validate_environment({"TOKEN": {"secret": secret_value}})
    assert secret_value not in str(exc_info.value)


@pytest.mark.parametrize(
    "value",
    [
        '["/tmp/file.txt"]',
        '[{"path":"/tmp/file.txt"}]',
        '[{"input_id":""}]',
        "[1]",
    ],
)
def test_input_references_reject_paths_and_malformed_items(value: str) -> None:
    with pytest.raises(JungleGridError, match=r"(managed input IDs|non-empty input_id)"):
        validate_input_references(value, "Input Files")


def test_input_references_normalize_string_ids() -> None:
    assert validate_input_references('["inp_audio123"]', "Input Files") == [{"input_id": "inp_audio123"}]


def test_expected_artifacts_require_managed_directory() -> None:
    with pytest.raises(JungleGridError, match="/workspace/artifacts/"):
        validate_expected_artifacts('["/tmp/output.txt"]')


def test_recursive_redaction_covers_nested_dicts_and_lists() -> None:
    value = {
        "items": [{"token": "secret", "nested": {"upload_url": SIGNED_URL}}],
        "authorization": "Bearer secret",
    }
    assert sanitize(value) == {
        "items": [{"token": "[redacted]", "nested": {"upload_url": "[redacted]"}}],
        "authorization": "[redacted]",
    }


async def test_client_unwraps_mcp_response_envelope_and_uses_authorization_header_only() -> None:
    client = JungleGridClient(API_KEY)
    mocked = AsyncMock(return_value=_response(payload={"ok": True, "data": {"job_id": "job_1"}}))
    with patch("httpx.AsyncClient.request", mocked):
        result = await client.request("GET", "/v1/mcp/jobs/job_1")
    assert result == {"job_id": "job_1"}
    assert mocked.call_args.kwargs["headers"]["Authorization"] == f"Bearer {API_KEY}"
    assert API_KEY not in mocked.call_args.args[1]
    assert mocked.call_args.kwargs["json"] is None


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 429, 500])
async def test_api_errors_preserve_safe_code_and_message(status_code: int) -> None:
    client = JungleGridClient(API_KEY)
    payload = {
        "error": {
            "code": "SAFE_CODE",
            "message": f"Safe API message {SIGNED_URL} Bearer {API_KEY} token={API_KEY}",
            "token": API_KEY,
            "upload_url": SIGNED_URL,
        }
    }
    with (
        patch("httpx.AsyncClient.request", AsyncMock(return_value=_response(status_code, payload))),
        pytest.raises(
            JungleGridError,
            match=rf"Jungle Grid API error {status_code} \(SAFE_CODE\): Safe API message "
            r"\[redacted-url\] Bearer \[redacted\] token=\[redacted\]",
        ) as exc_info,
    ):
        await client.request("GET", "/v1/mcp/jobs/job_1")
    assert API_KEY not in str(exc_info.value)
    assert SIGNED_URL not in str(exc_info.value)


async def test_timeout_error_is_sanitized() -> None:
    client = JungleGridClient(API_KEY)
    with (
        patch("httpx.AsyncClient.request", AsyncMock(side_effect=httpx.TimeoutException(f"timeout {API_KEY}"))),
        pytest.raises(JungleGridError, match="Jungle Grid request timed out") as exc_info,
    ):
        await client.request("GET", "/v1/mcp/jobs")
    assert API_KEY not in str(exc_info.value)


async def test_network_error_is_sanitized() -> None:
    client = JungleGridClient(API_KEY)
    request = httpx.Request("GET", f"https://api.junglegrid.dev/?token={API_KEY}")
    error = httpx.RequestError(f"network {API_KEY}", request=request)
    with (
        patch("httpx.AsyncClient.request", AsyncMock(side_effect=error)),
        pytest.raises(JungleGridError, match="Jungle Grid network error: network") as exc_info,
    ):
        await client.request("GET", "/v1/mcp/jobs")
    assert API_KEY not in str(exc_info.value)


async def test_non_json_success_response_is_handled_safely() -> None:
    client = JungleGridClient(API_KEY)
    with (
        patch("httpx.AsyncClient.request", AsyncMock(return_value=_response(text="<html>bad</html>"))),
        pytest.raises(JungleGridError, match="non-JSON response"),
    ):
        await client.request("GET", "/v1/mcp/jobs")


async def test_estimate_calls_current_endpoint_and_never_submits() -> None:
    component = _component(JungleGridEstimateJobComponent, args="[]", metadata=None)
    _, mocked = await _run(component, {"available": True})
    assert mocked.call_args.args[:2] == ("POST", "https://api.junglegrid.dev/v1/mcp/jobs/estimate")
    assert mocked.call_args.kwargs["json"]["args"] == []
    assert mocked.call_count == 1
    assert not mocked.call_args.args[1].endswith("/v1/mcp/jobs")


async def test_estimate_supports_alternate_base_url_and_trailing_slash() -> None:
    component = _component(JungleGridEstimateJobComponent, api_base_url="https://workspace.example/")
    _, mocked = await _run(component)
    assert mocked.call_args.args[1] == "https://workspace.example/v1/mcp/jobs/estimate"


async def test_submit_maps_workload_name_and_current_fields() -> None:
    component = _component(
        JungleGridSubmitJobComponent,
        workload_name="audio-transcription",
        workload_type="fine_tuning",
        command='["python", "/workspace/scripts/transcribe.py"]',
        args="[]",
        env='{"MODEL_NAME":"small"}',
        input_files='["inp_audio123"]',
        script_files='[{"input_id":"inp_script123"}]',
        metadata="{}",
        callback_metadata="{}",
    )
    _, mocked = await _run(component, {"job_id": "job_1"})
    body = mocked.call_args.kwargs["json"]
    assert mocked.call_args.args[1] == "https://api.junglegrid.dev/v1/mcp/jobs"
    assert body["name"] == "audio-transcription"
    assert "workload_name" not in body
    assert body["workload_type"] == "fine-tuning"
    assert body["command"] == ["python", "/workspace/scripts/transcribe.py"]
    assert body["args"] == []
    assert body["environment"] == {"MODEL_NAME": "small"}
    assert body["input_files"] == [{"input_id": "inp_audio123"}]
    assert body["script_files"] == [{"input_id": "inp_script123"}]
    assert body["expected_artifacts"] == ["/workspace/artifacts/output.txt"]
    assert body["metadata"] == {}
    assert body["callback_metadata"] == {}


async def test_submit_preserves_legacy_command_plus_args_semantics() -> None:
    component = _component(JungleGridSubmitJobComponent, command="python", args='["-c", "print(1)"]')
    _, mocked = await _run(component)
    body = mocked.call_args.kwargs["json"]
    assert body["command"] == "python"
    assert body["args"] == ["-c", "print(1)"]


async def test_submit_supports_legacy_serialized_name_and_workload_fields() -> None:
    component = _component(JungleGridSubmitJobComponent)
    component._attributes.pop("workload_name", None)
    component._attributes["name"] = "legacy-name"
    component._attributes.pop("workload_type", None)
    component._attributes["workload"] = "batch"
    _, mocked = await _run(component)
    assert mocked.call_args.kwargs["json"]["name"] == "legacy-name"
    assert mocked.call_args.kwargs["json"]["workload_type"] == "batch"


async def test_submit_rejects_invalid_workload_type() -> None:
    component = _component(JungleGridSubmitJobComponent, workload_type="unknown")
    with pytest.raises(JungleGridError, match="Workload Type must be one of"):
        await component.submit_job()


async def test_create_job_input_upload_calls_current_endpoint_and_redacts_status() -> None:
    payload = {
        "upload": {
            "input_id": "inp_audio123",
            "filename": "audio.wav",
            "method": "PUT",
            "upload_url": SIGNED_URL,
            "complete_url": f"{SIGNED_URL}/complete",
            "token": "temporary-token",
            "expires_at": "2030-01-01T00:00:00Z",
        }
    }
    component = _component(JungleGridCreateJobInputUploadComponent)
    result, mocked = await _run(component, payload)
    assert mocked.call_args.args[:2] == ("POST", "https://api.junglegrid.dev/v1/job-inputs")
    assert mocked.call_args.kwargs["json"] == {
        "filename": "audio.wav",
        "content_type": "audio/wav",
        "kind": "input",
    }
    assert result.data["upload"]["upload_url"] == SIGNED_URL
    assert SIGNED_URL not in str(component.status.data)
    assert "temporary-token" not in str(component.status.data)


async def test_create_job_input_upload_validates_kind() -> None:
    component = _component(JungleGridCreateJobInputUploadComponent, kind="archive")
    with pytest.raises(JungleGridError, match="Kind must be one of: input, script"):
        await component.create_job_input_upload()


async def test_list_job_inputs_calls_unfiltered_endpoint() -> None:
    component = _component(JungleGridListJobInputsComponent)
    _, mocked = await _run(component, {"inputs": []})
    assert mocked.call_args.args[:2] == ("GET", "https://api.junglegrid.dev/v1/job-inputs")
    assert mocked.call_args.kwargs["params"] is None


async def test_list_jobs_encodes_current_query_parameters() -> None:
    component = _component(JungleGridListJobsComponent, limit=150, cursor="20", status="running")
    _, mocked = await _run(component, {"jobs": [], "has_more": False})
    assert mocked.call_args.args[:2] == ("GET", "https://api.junglegrid.dev/v1/mcp/jobs")
    assert mocked.call_args.kwargs["params"] == {"limit": 100, "cursor": "20", "status": "running"}


async def test_get_job_status_preserves_phase_delay_and_artifact_information() -> None:
    payload = {
        "status": "queued",
        "execution_phase": "waiting_for_capacity",
        "phase_started_at": "2030-01-01T00:00:00Z",
        "phase_last_updated_at": "2030-01-01T00:01:00Z",
        "delayed_start": True,
        "delay_reason": {"code": "CAPACITY", "message": "Waiting"},
        "scheduling": {"state": "waiting_for_capacity"},
        "failure": None,
        "artifact_contract": {"expected": ["/workspace/artifacts/output.txt"]},
        "artifacts_ready": False,
    }
    component = _component(JungleGridGetJobStatusComponent)
    result, mocked = await _run(component, payload)
    assert mocked.call_args.args[1] == "https://api.junglegrid.dev/v1/mcp/jobs/job_test"
    assert result.data == payload


async def test_get_job_events_uses_lifecycle_endpoint_not_logs() -> None:
    component = _component(JungleGridGetJobEventsComponent)
    _, mocked = await _run(component, {"items": []})
    url = mocked.call_args.args[1]
    assert url == "https://api.junglegrid.dev/v1/jobs/job_test/events"
    assert not url.endswith("/logs")


async def test_get_job_runtime_uses_supported_endpoint() -> None:
    component = _component(JungleGridGetJobRuntimeComponent)
    result, mocked = await _run(component, {"runtime_availability": {"exit_code": {"state": "delayed"}}})
    assert mocked.call_args.args[1] == "https://api.junglegrid.dev/v1/jobs/job_test/runtime"
    assert result.data["runtime_availability"]["exit_code"]["state"] == "delayed"


async def test_get_job_runtime_unavailable_is_safe() -> None:
    component = _component(JungleGridGetJobRuntimeComponent)
    mocked = AsyncMock(
        return_value=_response(404, {"error": {"code": "NOT_FOUND", "message": "job runtime not available yet"}})
    )
    with (
        patch("httpx.AsyncClient.request", mocked),
        pytest.raises(JungleGridError, match=r"NOT_FOUND.*job runtime not available yet"),
    ):
        await component.get_job_runtime()


async def test_get_job_logs_uses_cursor_pagination_without_obsolete_parameters() -> None:
    component = _component(JungleGridGetJobLogsComponent, limit=2000, cursor="42")
    result, mocked = await _run(component, {"items": [], "next_cursor": None, "has_more": False})
    assert mocked.call_args.args[1] == "https://api.junglegrid.dev/v1/mcp/jobs/job_test/logs"
    assert mocked.call_args.kwargs["params"] == {"limit": 1000, "cursor": "42"}
    assert "tail" not in mocked.call_args.kwargs["params"]
    assert "stream" not in mocked.call_args.kwargs["params"]
    assert result.data["items"] == []


async def test_cancel_calls_verified_endpoint_and_body_once() -> None:
    component = _component(JungleGridCancelJobComponent)
    _, mocked = await _run(component)
    assert mocked.call_args.args[:2] == ("POST", "https://api.junglegrid.dev/v1/mcp/jobs/job_test/cancel")
    assert mocked.call_args.kwargs["json"] == {"reason": "test cancellation"}
    assert mocked.call_count == 1


async def test_list_job_artifacts_calls_verified_endpoint() -> None:
    component = _component(JungleGridListJobArtifactsComponent)
    result, mocked = await _run(component, {"artifacts": []})
    assert mocked.call_args.args[1] == "https://api.junglegrid.dev/v1/mcp/jobs/job_test/artifacts"
    assert result.data["artifacts"] == []


async def test_artifact_download_uses_artifact_id_and_redacts_component_status() -> None:
    component = _component(JungleGridCreateArtifactDownloadURLComponent, artifact_id="artifact/with space")
    result, mocked = await _run(component, {"download_url": SIGNED_URL, "expires_at": "2030-01-01T00:00:00Z"})
    assert (
        mocked.call_args.args[1]
        == "https://api.junglegrid.dev/v1/mcp/jobs/job_test/artifacts/artifact%2Fwith%20space/download"
    )
    assert result.data["download_url"] == SIGNED_URL
    assert component.status.data == {
        "summary": "Temporary artifact download information generated",
        "url": "<redacted>",
    }
