"""Last-Event-ID reattach contract: live id: and durable replay share ONE namespace.

The live SSE stream tags every frame with an ``id:`` line. A client that
disconnects mid-run reconnects with ``Last-Event-ID: <that id>``; the facade then
resumes from ``read_events(after_seq=<that id>)``. For that resume to be correct,
the ``id:`` the client saw live MUST be the same namespace as the durable
``job_events.seq`` the replay filters on.

The realistic frame source (``_stream_event_frames``) bakes its OWN per-frame
counter into the ``id:`` line — counting initial/ephemeral/durable frames alike —
so a naive runner that passes those bytes through publishes a DIFFERENT id
namespace than the durable seq. A reattach with a live id then gaps or duplicates
milestones. These tests drive the REAL runner + REAL facade with a source shaped
exactly like ``_stream_event_frames`` (baked stream-seq ids, a token between two
milestones) and assert the continuation after a mid-run Last-Event-ID starts
exactly at the next milestone — no miss, no repeat — on real SQLite and Postgres.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi.sse import format_sse_event
from langflow.api.v2.adapters import StreamAdapterContext, get_stream_adapter
from langflow.services.background_execution.live_bus import InMemoryLiveBus
from langflow.services.background_execution.runner import JobRunner

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.hard_proof


class _StubUser:
    """Minimal user carrying only ``id`` (all the facade reads on validate)."""

    def __init__(self, user_id) -> None:
        self.id = user_id


def _stream_seq_frame(event_type: str, data: dict, stream_seq: int) -> tuple[bytes, str]:
    """Mimic ``_stream_event_frames``: bake a STREAM-seq id into the frame bytes.

    The stream seq counts every yielded frame (initial, ephemeral, durable),
    so it deliberately diverges from the durable ``job_events.seq`` namespace.
    """
    import json

    body = json.dumps({"event": event_type, "data": data})
    return (format_sse_event(data_str=body, id=str(stream_seq)), event_type)


def _id_line(frame: bytes) -> int:
    for line in frame.decode("utf-8").splitlines():
        if line.startswith("id:"):
            return int(line[len("id:") :].strip())
    msg = f"frame has no id: line: {frame!r}"
    raise AssertionError(msg)


def _milestone_ids(frames: list[bytes]) -> dict[str, int]:
    """Map each durable milestone event_type -> the id: the client saw live."""
    import json

    out: dict[str, int] = {}
    for frame in frames:
        for line in frame.decode("utf-8").splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[len("data:") :].strip())
                evt = payload.get("event")
                if evt in {"build_start", "vertices_sorted", "end_vertex", "output", "end"}:
                    out[evt] = _id_line(frame)
    return out


async def _run_token_flow(job_service, job_id, bus) -> None:
    """A run that emits a token BETWEEN two milestones so stream-seq != durable-seq."""

    async def source(**_kwargs) -> AsyncIterator[tuple[bytes, str]]:
        # stream-seq baked in; durable seq advances only on durable frames.
        yield _stream_seq_frame("build_start", {}, 0)  # durable -> db seq 1
        yield _stream_seq_frame("vertices_sorted", {"ids": ["n1"]}, 1)  # durable -> db seq 2
        yield _stream_seq_frame("token", {"chunk": "a"}, 2)  # ephemeral
        yield _stream_seq_frame("token", {"chunk": "b"}, 3)  # ephemeral
        yield _stream_seq_frame("end_vertex", {"id": "n1"}, 4)  # durable -> db seq 3
        yield _stream_seq_frame("end", {}, 5)  # durable -> db seq 4

    adapter = get_stream_adapter("langflow", StreamAdapterContext(run_id=str(job_id), thread_id="t"))
    runner = JobRunner(job_service=job_service, live_bus=bus, adapter=adapter, frame_source=source)
    await runner.run(job_id=job_id, source_kwargs={})


async def test_live_id_matches_durable_seq_default(hard_proof_job_service):
    """The live id: a client sees == the durable seq the replay resumes after.

    Drives the real runner (default in-memory bus), captures the live frames, then
    proves that for EACH milestone the live id equals the durable job_events.seq.
    Pre-fix the live id is the stream-seq (0,1,4,5) while the durable seq is
    (1,2,3,4), so they diverge and a Last-Event-ID resume is wrong.
    """
    job_service = hard_proof_job_service
    user_id = uuid4()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=user_id)

    bus = InMemoryLiveBus()

    # Subscribe BEFORE the run so we capture the live frames the client would see.
    live_frames: list[bytes] = []
    sub = bus.subscribe(str(job_id))

    import asyncio

    async def _collect() -> None:
        async for frame in sub:
            live_frames.append(frame.data)  # noqa: PERF401

    collector = asyncio.create_task(_collect())
    await _run_token_flow(job_service, job_id, bus)
    await asyncio.wait_for(collector, timeout=5.0)

    live_ids = _milestone_ids(live_frames)

    # Durable seq order: build_start=1, vertices_sorted=2, end_vertex=3, end=4.
    rows = await job_service.read_events(job_id, after_seq=0)
    durable_seq = {r.event_type: r.seq for r in rows}

    # The live id for each milestone MUST equal its durable seq (one namespace).
    for evt, seq in durable_seq.items():
        assert live_ids.get(evt) == seq, (
            f"live id namespace mismatch for {evt}: live id={live_ids.get(evt)} durable seq={seq}"
        )


async def test_reattach_no_gap_no_dup_default(hard_proof_job_service):
    """Mid-run Last-Event-ID resume starts exactly at the next milestone.

    Captures the live id of the ``vertices_sorted`` milestone, reconnects with it
    as Last-Event-ID, and asserts the continuation replays exactly the milestones
    AFTER it (end_vertex, end) with no missing and no repeated milestone. Pre-fix
    the live id is a stream-seq (1) so read_events(after_seq=1) returns durable
    rows 2,3,4 (incl vertices_sorted again) -> duplicate.
    """
    import asyncio

    from langflow.services.background_execution.service import BackgroundExecutionService
    from langflow.services.deps import get_settings_service

    job_service = hard_proof_job_service
    user_id = uuid4()
    job_id = uuid4()
    await job_service.create_job(job_id=job_id, flow_id=uuid4(), user_id=user_id)

    bus = InMemoryLiveBus()
    live_frames: list[bytes] = []
    sub = bus.subscribe(str(job_id))

    async def _collect() -> None:
        async for frame in sub:
            live_frames.append(frame.data)  # noqa: PERF401

    collector = asyncio.create_task(_collect())
    await _run_token_flow(job_service, job_id, bus)
    await asyncio.wait_for(collector, timeout=5.0)

    live_ids = _milestone_ids(live_frames)
    # Client disconnects right after seeing the vertices_sorted milestone live.
    last_event_id = str(live_ids["vertices_sorted"])

    svc = BackgroundExecutionService(settings_service=get_settings_service())
    svc._bus = bus
    user = _StubUser(user_id)

    async def _reattach() -> list[bytes]:
        return [frame async for frame in svc.events(job_id, last_event_id, user)]

    cont_frames = await asyncio.wait_for(_reattach(), timeout=5.0)
    cont_ids = _milestone_ids(cont_frames)

    # The continuation must contain end_vertex and end (the milestones AFTER the
    # disconnect) and must NOT re-deliver vertices_sorted (already seen live).
    assert "vertices_sorted" not in cont_ids, f"duplicate milestone on reattach: {cont_ids}"
    assert "end_vertex" in cont_ids, f"missing milestone on reattach: {cont_ids}"
    assert "end" in cont_ids, f"missing milestone on reattach: {cont_ids}"
