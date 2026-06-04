"""In-process live event bus for background workflow runs.

Publishers (the runner) push ``LiveFrame``s for a job; live subscribers receive
them through a bounded per-subscriber queue. ``reattach`` first replays the
durable log (via the injected ``read_durable``) from the caller's last seen seq,
then switches to the live tail — deduplicating any seq already replayed so a
frame straddling the replay/tail boundary is emitted exactly once.

This bus is process-local; the redis backend (Phase 3) swaps it for redis
Streams behind the same facade method (``events``). Nothing else changes.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import OrderedDict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

# Per-subscriber buffer cap. A slow client falling behind a fast producer drops
# the oldest live frame rather than growing without bound; the durable log is
# the source of truth for anything the client missed, reachable via reattach.
_SUBSCRIBER_MAXSIZE = 1000

# Cap on the closed-marker map. ``close()`` records each finished job so a later
# direct reattach/subscribe to it terminates immediately instead of blocking on a
# live tail that will never produce. The map is evicted eagerly when a job's last
# subscriber drops; this LRU cap is the backstop for jobs that close and are
# never reattached, so a long-lived API process cannot leak one key per job
# without bound. The facade also gates terminal jobs on the persisted JobStatus,
# so an evicted marker never causes a missed/blocked production reattach.
_CLOSED_MARKER_MAXSIZE = 4096


@dataclass(frozen=True)
class LiveFrame:
    """One framed event on the live bus.

    ``seq`` is the durable cursor used for ``Last-Event-ID``. For a durable
    milestone it is the row's ``job_events.seq``; for an ephemeral frame it is
    the seq of the most recent durable milestone (so ordering stays monotonic).
    ``data`` is the already-formatted SSE frame bytes.
    """

    seq: int
    data: bytes


ReadDurable = Callable[[int], Awaitable[list[LiveFrame]]]

# Sentinel pushed into a subscriber queue to signal end-of-stream.
_CLOSED = object()


class InMemoryLiveBus:
    def __init__(self) -> None:
        # job_id -> set of subscriber queues.
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        # job_id -> True once closed; late subscribers end immediately. Bounded
        # LRU (OrderedDict) so a long-lived process cannot leak one key per job;
        # see ``_mark_closed`` / ``_CLOSED_MARKER_MAXSIZE``.
        self._closed: OrderedDict[str, bool] = OrderedDict()

    def _new_queue(self, job_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=_SUBSCRIBER_MAXSIZE)
        self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    def _drop_queue(self, job_id: str, queue: asyncio.Queue) -> None:
        subs = self._subscribers.get(job_id)
        if subs is not None:
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(job_id, None)

    async def publish(self, job_id: str, frame: LiveFrame) -> None:
        """Push ``frame`` to every live subscriber for ``job_id``."""
        for queue in list(self._subscribers.get(job_id, set())):
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(frame)

    def _mark_closed(self, job_id: str) -> None:
        """Record a job as closed, bounding the map to an LRU of recent jobs.

        Always recorded (even with no subscribers) so a later direct reattach to
        the finished job terminates instead of blocking on a tail that will never
        produce. The OrderedDict is the LRU: re-mark moves the key to the end, and
        the oldest entry is dropped once the cap is exceeded. Eviction of a very
        old marker is safe — the facade gates terminal jobs on the persisted
        JobStatus, so a production reattach never depends on this in-process flag.
        """
        self._closed[job_id] = True
        self._closed.move_to_end(job_id)
        while len(self._closed) > _CLOSED_MARKER_MAXSIZE:
            self._closed.popitem(last=False)

    async def close(self, job_id: str) -> None:
        """Mark the job's stream ended and wake every subscriber."""
        self._mark_closed(job_id)
        for queue in list(self._subscribers.get(job_id, set())):
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(_CLOSED)

    def subscribe(self, job_id: str) -> AsyncIterator[LiveFrame]:
        """Live-only subscription: frames published from now until close.

        The subscriber queue is registered eagerly here (not inside the
        generator) so a frame published between ``subscribe(...)`` and the
        first ``__anext__`` is not lost — the queue already exists to catch it.
        """
        if self._closed.get(job_id):

            async def _empty() -> AsyncIterator[LiveFrame]:
                return
                yield  # pragma: no cover - makes this an async generator

            return _empty()

        queue = self._new_queue(job_id)

        async def _gen() -> AsyncIterator[LiveFrame]:
            try:
                while True:
                    item = await queue.get()
                    if item is _CLOSED:
                        return
                    yield item
            finally:
                self._drop_queue(job_id, queue)

        return _gen()

    def reattach(
        self,
        job_id: str,
        last_seq: int,
        read_durable: ReadDurable,
    ) -> AsyncIterator[LiveFrame]:
        """Replay the durable log after ``last_seq``, then tail the live bus.

        A subscriber queue is registered BEFORE the durable read so no live
        frame published during replay is lost. Frames whose seq was already
        replayed (or already <= last_seq) are skipped so the boundary emits
        each seq exactly once.
        """
        # Register eagerly (not inside the generator) so frames published
        # between ``reattach(...)`` and the first ``__anext__`` are captured.
        queue = self._new_queue(job_id)

        async def _gen() -> AsyncIterator[LiveFrame]:
            highest = last_seq
            try:
                for frame in await read_durable(last_seq):
                    highest = max(highest, frame.seq)
                    yield frame
                # If the job closed before/while we replayed, drain nothing more.
                if self._closed.get(job_id) and queue.empty():
                    return
                while True:
                    item = await queue.get()
                    if item is _CLOSED:
                        return
                    if item.seq <= highest:
                        continue
                    highest = item.seq
                    yield item
            finally:
                self._drop_queue(job_id, queue)

        return _gen()
