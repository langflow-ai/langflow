"""AG-UI durable replay must be byte-identical to the live frame.

The AG-UI live path serializes each event with pydantic ``model_dump_json`` —
compact separators (``{"type":"RUN_STARTED",...}``). The durable replay re-frames
the persisted payload dict; if it used Python's default ``json.dumps`` (spaced
separators ``{"type": "RUN_STARTED", ...}``) the replayed bytes would differ from
live, contradicting the byte-compatible reattach claim. This drives the REAL
AG-UI adapter to produce a live frame, persists the same payload the runner would
(parsed dict), and asserts the facade's replay bytes equal the live bytes for the
agui protocol — and that langflow stays byte-identical too (spaced separators).
"""

from __future__ import annotations

import json

import pytest
from fastapi.sse import format_sse_event
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.service import BackgroundExecutionService

pytestmark = pytest.mark.real_services


def _live_agui_run_started_bytes(seq: int) -> bytes:
    adapter = get_stream_adapter("agui", StreamAdapterContext(run_id="r1", thread_id="t1"))
    events = list(adapter.initial_events())
    # RUN_STARTED is the first initial event.
    run_started = events[0]
    return format_sse_event(data_str=run_started.data_json, id=str(seq))


def _row(seq: int, payload: dict):
    return type("JobEvent", (), {"seq": seq, "payload": payload})()


def test_agui_replay_bytes_equal_live_bytes():
    """The agui replay frame equals the live frame byte-for-byte."""
    seq = 1
    live = _live_agui_run_started_bytes(seq)

    # The runner persists the parsed dict (json.loads of the live data_json).
    live_data_json = live.decode("utf-8").split("data: ", 1)[1].split("\n", 1)[0]
    persisted_payload = json.loads(live_data_json)

    replay = BackgroundExecutionService._row_to_frame(_row(seq, persisted_payload), protocol="agui")
    assert replay == live, f"agui replay not byte-identical:\n live  ={live!r}\n replay={replay!r}"


def test_langflow_replay_bytes_equal_live_bytes():
    """The langflow replay frame stays byte-identical (spaced separators)."""
    seq = 3
    payload = {"event": "build_start", "data": {"id": "n1"}}
    live = format_sse_event(data_str=json.dumps(payload, default=str), id=str(seq))

    persisted_payload = json.loads(json.dumps(payload, default=str))
    replay = BackgroundExecutionService._row_to_frame(_row(seq, persisted_payload), protocol="langflow")
    assert replay == live, f"langflow replay not byte-identical:\n live  ={live!r}\n replay={replay!r}"
