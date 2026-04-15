"""Unit tests for langflow_sdk.testing and RunResponse helpers.

Uses respx to mock HTTP so no live Langflow instance is needed.
"""
# pragma: allowlist secret -- all credentials in this file are fake test data

from __future__ import annotations

import httpx
import respx
from langflow_sdk.client import AsyncLangflowClient, LangflowClient
from langflow_sdk.models import RunOutput, RunResponse
from langflow_sdk.testing import AsyncFlowRunner, FlowRunner

_BASE = "http://langflow.test"

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Minimal RunResponse payload matching the standard Langflow chat shape
_CHAT_RUN_RESPONSE = {
    "session_id": "sess-abc",
    "outputs": [
        {
            "results": {},
            "artifacts": {},
            "outputs": [
                {
                    "results": {
                        "message": {
                            "text": "Hello back!",
                            "sender": "Machine",
                        }
                    },
                    "artifacts": {},
                    "outputs": {},
                }
            ],
            "session_id": None,
            "timedelta": None,
        }
    ],
}

# RunResponse with a direct "text" result (custom component pattern)
_TEXT_RUN_RESPONSE = {
    "session_id": "sess-xyz",
    "outputs": [
        {
            "results": {},
            "artifacts": {},
            "outputs": [
                {
                    "results": {"text": "Direct text output"},
                    "artifacts": {},
                    "outputs": {},
                }
            ],
            "session_id": None,
            "timedelta": None,
        }
    ],
}

# RunResponse with two output blocks
_MULTI_RUN_RESPONSE = {
    "session_id": "sess-multi",
    "outputs": [
        {
            "results": {},
            "artifacts": {},
            "outputs": [{"results": {"message": {"text": "First"}}, "artifacts": {}, "outputs": {}}],
            "session_id": None,
            "timedelta": None,
        },
        {
            "results": {},
            "artifacts": {},
            "outputs": [{"results": {"message": {"text": "Second"}}, "artifacts": {}, "outputs": {}}],
            "session_id": None,
            "timedelta": None,
        },
    ],
}

# Empty RunResponse (no outputs at all)
_EMPTY_RUN_RESPONSE = {"session_id": None, "outputs": []}


def _sync_client() -> LangflowClient:
    return LangflowClient(base_url=_BASE, api_key="test-key")  # pragma: allowlist secret


def _async_client() -> AsyncLangflowClient:
    return AsyncLangflowClient(base_url=_BASE, api_key="test-key")  # pragma: allowlist secret


# ---------------------------------------------------------------------------
# RunOutput.first_text()
# ---------------------------------------------------------------------------


def test_run_output_first_text_message_path():
    """Extracts text from the standard chat message path."""
    out = RunOutput.model_validate(_CHAT_RUN_RESPONSE["outputs"][0])
    assert out.first_text() == "Hello back!"


def test_run_output_first_text_direct_text_path():
    """Extracts text from the direct results.text path."""
    out = RunOutput.model_validate(_TEXT_RUN_RESPONSE["outputs"][0])
    assert out.first_text() == "Direct text output"


def test_run_output_first_text_none_when_empty():
    """Returns None when outputs list is empty."""
    out = RunOutput()
    assert out.first_text() is None


def test_run_output_first_text_none_when_no_text_key():
    """Returns None when results has no message or text key."""
    out = RunOutput(outputs=[{"results": {"other": "value"}, "artifacts": {}, "outputs": {}}])
    assert out.first_text() is None


# ---------------------------------------------------------------------------
# RunResponse.first_text_output()
# ---------------------------------------------------------------------------


def test_run_response_first_text_output_chat():
    """first_text_output extracts text from a chat response."""
    resp = RunResponse.model_validate(_CHAT_RUN_RESPONSE)
    assert resp.first_text_output() == "Hello back!"


def test_run_response_first_text_output_direct_text():
    """first_text_output works with the direct text result path."""
    resp = RunResponse.model_validate(_TEXT_RUN_RESPONSE)
    assert resp.first_text_output() == "Direct text output"


def test_run_response_first_text_output_empty():
    """Returns None when there are no outputs."""
    resp = RunResponse.model_validate(_EMPTY_RUN_RESPONSE)
    assert resp.first_text_output() is None


# ---------------------------------------------------------------------------
# RunResponse.all_text_outputs()
# ---------------------------------------------------------------------------


def test_run_response_all_text_outputs_multiple():
    """all_text_outputs collects text from every output block."""
    resp = RunResponse.model_validate(_MULTI_RUN_RESPONSE)
    assert resp.all_text_outputs() == ["First", "Second"]


def test_run_response_all_text_outputs_empty():
    """Returns an empty list when there are no outputs."""
    resp = RunResponse.model_validate(_EMPTY_RUN_RESPONSE)
    assert resp.all_text_outputs() == []


def test_run_response_all_text_outputs_skips_none():
    """Blocks with no text are silently skipped."""
    resp = RunResponse.model_validate(
        {
            "session_id": None,
            "outputs": [
                # block with text
                {
                    "results": {},
                    "artifacts": {},
                    "outputs": [{"results": {"message": {"text": "Found"}}, "artifacts": {}, "outputs": {}}],
                    "session_id": None,
                    "timedelta": None,
                },
                # block without text
                {
                    "results": {},
                    "artifacts": {},
                    "outputs": [{"results": {"other": 42}, "artifacts": {}, "outputs": {}}],
                    "session_id": None,
                    "timedelta": None,
                },
            ],
        }
    )
    assert resp.all_text_outputs() == ["Found"]


# ---------------------------------------------------------------------------
# FlowRunner (sync) with mocked HTTP
# ---------------------------------------------------------------------------


@respx.mock
def test_flow_runner_calls_run_flow():
    """FlowRunner.__call__ hits POST /api/v1/run/<endpoint>."""
    respx.post(f"{_BASE}/api/v1/run/my-endpoint").mock(return_value=httpx.Response(200, json=_CHAT_RUN_RESPONSE))
    runner = FlowRunner(_sync_client())
    response = runner("my-endpoint", "Hello!")

    assert isinstance(response, RunResponse)
    assert response.session_id == "sess-abc"
    assert response.first_text_output() == "Hello back!"


@respx.mock
def test_flow_runner_passes_tweaks():
    """FlowRunner forwards tweaks inside the JSON body."""
    route = respx.post(f"{_BASE}/api/v1/run/ep").mock(return_value=httpx.Response(200, json=_CHAT_RUN_RESPONSE))
    runner = FlowRunner(_sync_client())
    runner("ep", "Q", tweaks={"MyComponent": {"param": "value"}})

    body = route.calls.last.request.content
    import json

    parsed = json.loads(body)
    assert parsed["tweaks"] == {"MyComponent": {"param": "value"}}


@respx.mock
def test_flow_runner_default_input_type():
    """FlowRunner defaults to input_type='chat' and output_type='chat'."""
    route = respx.post(f"{_BASE}/api/v1/run/ep").mock(return_value=httpx.Response(200, json=_CHAT_RUN_RESPONSE))
    runner = FlowRunner(_sync_client())
    runner("ep")

    import json

    parsed = json.loads(route.calls.last.request.content)
    assert parsed["input_type"] == "chat"
    assert parsed["output_type"] == "chat"


# ---------------------------------------------------------------------------
# AsyncFlowRunner with mocked HTTP
# ---------------------------------------------------------------------------


@respx.mock
async def test_async_flow_runner_calls_run_flow():
    """AsyncFlowRunner.__call__ hits POST /api/v1/run/<endpoint> asynchronously."""
    respx.post(f"{_BASE}/api/v1/run/async-ep").mock(return_value=httpx.Response(200, json=_TEXT_RUN_RESPONSE))
    runner = AsyncFlowRunner(_async_client())
    response = await runner("async-ep", "Hi async!")

    assert isinstance(response, RunResponse)
    assert response.first_text_output() == "Direct text output"


@respx.mock
async def test_async_flow_runner_multi_output():
    """AsyncFlowRunner returns all outputs correctly."""
    respx.post(f"{_BASE}/api/v1/run/multi-ep").mock(return_value=httpx.Response(200, json=_MULTI_RUN_RESPONSE))
    runner = AsyncFlowRunner(_async_client())
    response = await runner("multi-ep", "Query")

    assert response.all_text_outputs() == ["First", "Second"]


# ---------------------------------------------------------------------------
# FlowRunner with UUID flow ID
# ---------------------------------------------------------------------------


@respx.mock
def test_flow_runner_accepts_uuid():
    """FlowRunner works with a UUID flow ID, not just an endpoint string."""
    from uuid import UUID

    flow_id = UUID("dddddddd-0000-0000-0000-000000000001")
    respx.post(f"{_BASE}/api/v1/run/{flow_id}").mock(return_value=httpx.Response(200, json=_CHAT_RUN_RESPONSE))
    runner = FlowRunner(_sync_client())
    response = runner(flow_id, "Hello by UUID")

    assert response.first_text_output() == "Hello back!"


# ---------------------------------------------------------------------------
# Plugin import sanity check
# ---------------------------------------------------------------------------


def test_flow_runner_and_async_runner_are_importable():
    """FlowRunner and AsyncFlowRunner can be imported from langflow_sdk.testing."""
    from langflow_sdk.testing import AsyncFlowRunner as ImportedAsync
    from langflow_sdk.testing import FlowRunner as ImportedSync

    assert ImportedSync is FlowRunner
    assert ImportedAsync is AsyncFlowRunner


def test_pytest_addoption_registers_options(pytestconfig):
    """The plugin registers all --langflow-* options (verified via public getoption API)."""
    # getoption() returns None for unset options; raises ValueError if the
    # option was never registered -- so a clean return proves registration.
    for name in (
        "--langflow-url",
        "--langflow-env",
        "--langflow-api-key",
        "--langflow-environments-file",
    ):
        assert pytestconfig.getoption(name) is None, f"Option {name!r} missing or has unexpected default"
