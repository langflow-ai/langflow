"""Opt-in live smoke for the V1 performance suite (three protocols).

Skipped unless ``PERF_LIVE=1`` and a provisioned state file exists.
Exercises clients against the live target (MCP, workflow sync/stream/background,
webhook). A separate opt-in Locust headless smoke can be enabled with
``PERF_LIVE_LOCUST=1``.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.locust.langflow_runtime.paths import state_path_for

pytestmark = [
    pytest.mark.performance_integration,
    pytest.mark.skipif(os.environ.get("PERF_LIVE") != "1", reason="set PERF_LIVE=1 for live perf smoke"),
]

_LOCUST_ROOT = Path(__file__).resolve().parents[2]
_STATE_PATH = Path(
    os.environ.get(
        "PERF_STATE_PATH",
        str(state_path_for(os.environ.get("PERF_ENV_ID", "perf-local"))),
    )
)
_BACKEND_ROOT = _LOCUST_ROOT.parents[2]


@pytest.fixture(scope="module")
def provision_state() -> dict:
    if not _STATE_PATH.exists():
        pytest.skip(f"missing provision state at {_STATE_PATH}; run provision.cli apply first")
    return json.loads(_STATE_PATH.read_text(encoding="utf-8"))


def test_live_mcp_workflow_webhook_smoke(provision_state: dict) -> None:
    """One pass each: MCP, workflow sync/stream/background, webhook subscribe-before-POST."""
    import httpx

    from tests.locust.langflow_runtime.clients.mcp_streamable import McpStreamableClient
    from tests.locust.langflow_runtime.clients.webhooks import WebhookCopy, WebhooksClient
    from tests.locust.langflow_runtime.clients.workflows import WorkflowsClient
    from tests.locust.langflow_runtime.flows.defaults import DEFAULT_PASSTHROUGH_INPUT, DEFAULT_WEBHOOK_PAYLOAD

    host = str(provision_state.get("host") or os.environ.get("PERF_HOST") or "http://127.0.0.1:7860").rstrip("/")
    api_key = provision_state.get("api_key")
    assert api_key, "provision state missing api_key"

    flows = provision_state.get("flows") or {}
    passthrough = flows.get("perf_passthrough")
    webhook = flows.get("perf_webhook_passthrough")
    if not passthrough or not webhook:
        pytest.skip("smoke flows not present in provision state")

    project_id = passthrough.get("project_id") or provision_state.get("project_id")
    assert project_id, "missing project_id for MCP"

    with httpx.Client(base_url=host, timeout=60.0) as http:
        mcp = McpStreamableClient(
            http,
            base_url=host,
            project_id=str(project_id),
            api_key=str(api_key),
            workload="protocol_calibration",
            flow_class="passthrough",
        )
        tool = str(passthrough.get("mcp_action_name") or "perf_passthrough")
        mcp.full_lifecycle_call(tool, {"input_value": DEFAULT_PASSTHROUGH_INPUT})

        workflows = WorkflowsClient(http, base_url=host, api_key=str(api_key))
        flow_id = str(passthrough["flow_id"])
        workflows.run_sync(
            flow_id=flow_id,
            input_value=DEFAULT_PASSTHROUGH_INPUT,
            session_id="perf-live-smoke-sync",
        )
        # Stream: consume until terminal (client raises on hard failure).
        stream_text = workflows.run_stream(
            flow_id=flow_id,
            input_value=DEFAULT_PASSTHROUGH_INPUT,
            session_id="perf-live-smoke-stream",
        )
        assert stream_text
        assert "event: end" in stream_text or "event: error" in stream_text

        job_id = workflows.submit_background(
            flow_id=flow_id,
            input_value=DEFAULT_PASSTHROUGH_INPUT,
            session_id="perf-live-smoke-bg",
        )
        terminal = workflows.wait_until_terminal(job_id, poll_interval_s=0.5, deadline_s=60.0)
        assert terminal.terminal is True

        copies = webhook.get("copies") or [{"flow_id": webhook["flow_id"], "endpoint_name": webhook["endpoint_name"]}]
        copy_row = copies[0]
        client = WebhooksClient(http, base_url=host, api_key=str(api_key))
        result = client.subscribe_post_complete(
            WebhookCopy(
                flow_id=str(copy_row["flow_id"]),
                endpoint_name=str(copy_row["endpoint_name"]),
            ),
            DEFAULT_WEBHOOK_PAYLOAD,
            timeout_s=60.0,
        )
        assert result.accepted is True
        assert result.completed is True


@pytest.mark.skipif(
    os.environ.get("PERF_LIVE_LOCUST") != "1",
    reason="set PERF_LIVE_LOCUST=1 to run a short headless Locust smoke",
)
def test_live_locust_smoke_headless(provision_state: dict) -> None:
    """One-user headless Locust run for the smoke profile (opt-in)."""
    host = str(provision_state.get("host") or os.environ.get("PERF_HOST") or "http://127.0.0.1:7860").rstrip("/")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(_BACKEND_ROOT), env["PYTHONPATH"]] if env.get("PYTHONPATH") else [str(_BACKEND_ROOT)]
    )
    env["PERF_HOST"] = host
    env["PERF_STATE_PATH"] = str(_STATE_PATH)
    env["PERF_ENV_ID"] = str(provision_state.get("env_id") or "perf-local")
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.locust.langflow_runtime.run",
            "run",
            "--profile",
            "smoke/all_protocols_v1",
            "--host",
            host,
            "--env-id",
            env["PERF_ENV_ID"],
            "--run-id",
            "live-smoke",
        ],
        cwd=_BACKEND_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert completed.returncode == 0, completed.stdout + "\n" + completed.stderr
