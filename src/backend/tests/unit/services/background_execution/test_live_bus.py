"""In-memory live bus: publish to live subscribers, reattach replays then tails."""

from __future__ import annotations

import asyncio

import pytest
from langflow.services.background_execution.live_bus import InMemoryLiveBus, LiveFrame


async def test_subscriber_receives_published_frame():
    bus = InMemoryLiveBus()
    sub = bus.subscribe("job-1")
    await bus.publish("job-1", LiveFrame(seq=1, data=b"hello"))
    frame = await asyncio.wait_for(sub.__anext__(), timeout=2)
    assert frame.seq == 1
    assert frame.data == b"hello"
    await bus.close("job-1")


async def test_close_ends_subscription():
    bus = InMemoryLiveBus()
    sub = bus.subscribe("job-1")
    await bus.close("job-1")
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(sub.__anext__(), timeout=2)


async def test_multiple_subscribers_each_get_frame():
    bus = InMemoryLiveBus()
    sub_a = bus.subscribe("job-1")
    sub_b = bus.subscribe("job-1")
    await bus.publish("job-1", LiveFrame(seq=1, data=b"x"))
    fa = await asyncio.wait_for(sub_a.__anext__(), timeout=2)
    fb = await asyncio.wait_for(sub_b.__anext__(), timeout=2)
    assert fa.data == fb.data == b"x"
    await bus.close("job-1")


async def test_reattach_replays_durable_then_tails_live():
    bus = InMemoryLiveBus()

    # Fake durable store: seq->data already persisted before reattach.
    persisted = [LiveFrame(seq=1, data=b"a"), LiveFrame(seq=2, data=b"b")]

    async def read_durable(after_seq: int) -> list[LiveFrame]:
        return [f for f in persisted if f.seq > after_seq]

    # Reattach from seq 0: should replay seq 1,2 from durable, then live seq 3.
    stream = bus.reattach("job-1", last_seq=0, read_durable=read_durable)

    f1 = await asyncio.wait_for(stream.__anext__(), timeout=2)
    f2 = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert [f1.seq, f2.seq] == [1, 2]

    # Now a live frame arrives; the tail picks it up.
    await bus.publish("job-1", LiveFrame(seq=3, data=b"c"))
    f3 = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert f3.seq == 3
    await bus.close("job-1")


async def test_closed_marker_is_bounded_not_leaked():
    """``_closed`` must not grow one permanent entry per completed job.

    The bus is a single long-lived per-process object; close(job_id) used to set
    ``_closed[job_id]=True`` and never evict it, leaking one key per job for the
    process lifetime. Close many MORE jobs than the LRU cap and assert the marker
    map stays bounded (does not grow with the number of finished jobs) and that a
    reattach to a still-tracked closed job still terminates immediately.
    """
    from langflow.services.background_execution.live_bus import _CLOSED_MARKER_MAXSIZE

    bus = InMemoryLiveBus()
    total = _CLOSED_MARKER_MAXSIZE + 500
    for i in range(total):
        await bus.close(f"job-{i}")

    # Bounded: the map never exceeds the LRU cap no matter how many jobs finish.
    assert len(bus._closed) <= _CLOSED_MARKER_MAXSIZE, f"_closed leaked {len(bus._closed)} entries"

    # A reattach to a recently-closed job (still in the LRU) terminates at once,
    # not blocking on a live tail that will never produce.
    async def read_durable(after_seq: int) -> list[LiveFrame]:  # noqa: ARG001
        return []

    recent = f"job-{total - 1}"
    seqs = [f.seq async for f in bus.reattach(recent, last_seq=0, read_durable=read_durable)]
    assert seqs == []


async def test_reattach_dedupes_overlap_between_durable_and_live():
    """A frame that lands in live while we replay durable must not double-emit."""
    bus = InMemoryLiveBus()
    persisted = [LiveFrame(seq=1, data=b"a")]

    async def read_durable(after_seq: int) -> list[LiveFrame]:
        return [f for f in persisted if f.seq > after_seq]

    stream = bus.reattach("job-1", last_seq=0, read_durable=read_durable)
    f1 = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert f1.seq == 1
    # Publish seq 1 again (already replayed) and seq 2 (new). Only seq 2 should pass.
    await bus.publish("job-1", LiveFrame(seq=1, data=b"a"))
    await bus.publish("job-1", LiveFrame(seq=2, data=b"b"))
    f = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert f.seq == 2
    await bus.close("job-1")


async def test_reattach_keeps_ephemeral_frames_sharing_last_durable_seq():
    """Ephemeral token frames carry the last durable seq, so seq-dedupe must not eat them.

    The runner publishes ephemeral frames tagged with ``last_durable_seq`` (they have
    no row of their own). After replay leaves ``highest`` at that same seq, a plain
    ``seq <= highest`` skip would silently drop every token delta until the next
    durable milestone bumps the seq.
    """
    bus = InMemoryLiveBus()
    persisted = [LiveFrame(seq=1, data=b"milestone-1")]

    async def read_durable(after_seq: int) -> list[LiveFrame]:
        return [f for f in persisted if f.seq > after_seq]

    stream = bus.reattach("job-1", last_seq=0, read_durable=read_durable)
    replayed = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert replayed.seq == 1

    # Two token deltas emitted before the next durable milestone: both ride seq 1.
    await bus.publish("job-1", LiveFrame(seq=1, data=b"tok-a", durable=False))
    await bus.publish("job-1", LiveFrame(seq=1, data=b"tok-b", durable=False))
    # ...then the next durable milestone.
    await bus.publish("job-1", LiveFrame(seq=2, data=b"milestone-2"))

    got = [(await asyncio.wait_for(stream.__anext__(), timeout=2)).data for _ in range(3)]
    assert got == [b"tok-a", b"tok-b", b"milestone-2"]
    await bus.close("job-1")
