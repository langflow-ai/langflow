"""Drive a background workflow run through a StreamAdapter.

The runner consumes ``(frame_bytes, event_type)`` pairs from a frame source
(the v1 build-vertex loop wrapped by ``_stream_event_frames``), and for each:

* durable frame   -> ``JobService.append_event`` (assigns a seq) + publish live
* ephemeral frame -> publish live only, tagged with the last durable seq

Between frames it polls the durable STOP signal at the vertex boundary and
cooperatively cancels. Terminal handling writes durable ``result``/``error``,
closes the live bus, and routes the status transition through
``JobService.execute_with_status`` so TIMED_OUT / CANCELLED / FAILED mapping is
reused from the single source of truth.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.background_execution.live_bus import LiveFrame
from langflow.services.database.models.jobs.model import JobStatus, SignalType

if TYPE_CHECKING:
    from uuid import UUID

    from langflow.api.v2.adapters import StreamAdapter
    from langflow.services.background_execution.live_bus import InMemoryLiveBus
    from langflow.services.jobs.service import JobService

# A frame source yields (sse_frame_bytes, protocol_event_type) pairs.
FrameSource = Callable[..., AsyncIterator[tuple[bytes, str]]]


class JobRunner:
    def __init__(
        self,
        *,
        job_service: JobService,
        live_bus: InMemoryLiveBus,
        adapter: StreamAdapter,
        frame_source: FrameSource,
        job_timeout: float | None = None,
        owner: str | None = None,
        heartbeat_interval_s: float = 15.0,
    ) -> None:
        self._jobs = job_service
        self._bus = live_bus
        self._adapter = adapter
        self._frame_source = frame_source
        # When set, the whole run is bounded by this wall-clock budget; an overrun
        # surfaces as asyncio.TimeoutError, which execute_with_status maps to
        # TIMED_OUT. None means unbounded (the prior behaviour).
        self._job_timeout = job_timeout
        # Liveness: while a run is in flight, a background task refreshes the
        # job-row heartbeat so a reconciler can tell this live run from a
        # genuinely orphaned one. ``owner`` is a process-unique token; when None
        # (scripted tests that don't care about liveness) the heartbeat is off.
        self._owner = owner
        self._heartbeat_interval_s = max(heartbeat_interval_s, 0.1)

    async def run(self, *, job_id: UUID, source_kwargs: dict[str, Any]) -> None:
        """Execute one background job to a terminal state."""

        # Bind job_id into the wrapped coroutine so ``execute_with_status``'s
        # own ``job_id`` parameter is not shadowed by a forwarded kwarg. When a
        # job timeout is configured, bound the drive with ``asyncio.wait_for`` so
        # an overrun raises ``asyncio.TimeoutError``; ``execute_with_status``
        # turns that into TIMED_OUT (the single source of truth for the mapping).
        async def _wrapped() -> None:
            if self._job_timeout is not None:
                await asyncio.wait_for(
                    self._drive(job_id=job_id, source_kwargs=source_kwargs),
                    timeout=self._job_timeout,
                )
            else:
                await self._drive(job_id=job_id, source_kwargs=source_kwargs)

        heartbeat_task = self._start_heartbeat(job_id)
        try:
            await self._jobs.execute_with_status(job_id, _wrapped)
        except asyncio.CancelledError as exc:
            # A cooperative STOP that we raised ourselves ends the run cleanly
            # (execute_with_status already wrote CANCELLED). A genuine system
            # cancel with no STOP signal re-raises so asyncio semantics hold; a
            # cancel that carries a STOP signal is a user stop and is reconciled
            # to CANCELLED in the finally below.
            user_tagged = bool(exc.args) and exc.args[0] == "LANGFLOW_USER_CANCELLED"
            if not user_tagged and not await self._stop_requested(job_id):
                raise
            await logger.adebug(f"Background job {job_id} stopped")
        except Exception as exc:  # noqa: BLE001
            # Terminal error / runtime failure already routed to FAILED by
            # execute_with_status; log and swallow so the worker survives.
            await logger.aerror(f"Background job {job_id} runner error: {exc}", exc_info=True)
        finally:
            # Stop refreshing the heartbeat: the run has reached a terminal
            # state, so a reconciler should now see it as no-longer-live.
            await self._stop_heartbeat(heartbeat_task)
            # Last-writer reconcile: a ``/stop`` that raced terminal finalization
            # (execute_with_status writes COMPLETED/FAILED unconditionally) must
            # not be silently overwritten. If a durable STOP signal exists, force
            # CANCELLED as the runner's final write. Shielded so an executor task
            # cancel cannot abort the correction. Mirrors the old
            # _finalize_job_status "never overwrite CANCELLED" guard.
            with contextlib.suppress(Exception):
                if await asyncio.shield(self._reconcile_stop(job_id)):
                    await logger.adebug(f"Background job {job_id} reconciled to CANCELLED after a racing stop")
            # Every terminal path writes result/error + a terminal job_events row
            # (design §8). COMPLETED/FAILED already do via _drive; TIMED_OUT and
            # CANCELLED do not, so backfill their error blob + terminal milestone
            # here (after the stop reconcile so a late-stop CANCELLED is included).
            with contextlib.suppress(Exception):
                await asyncio.shield(self._finalize_terminal_event(job_id))
            await self._bus.close(str(job_id))

    async def _finalize_terminal_event(self, job_id: UUID) -> None:
        """Backfill the error blob + terminal event for TIMED_OUT / CANCELLED.

        ``execute_with_status`` writes the TIMED_OUT/CANCELLED status but no
        durable error blob or terminal ``job_events`` row, so a consumer keying
        on a terminal event TYPE (not just stream close) would not find one. This
        appends ``run_timed_out`` / ``run_cancelled`` and, for a CANCELLED row
        that a racing completion left with a populated ``result``, clears the
        result and sets ``error={type: cancelled}`` so the terminal state is
        internally consistent (no CANCELLED row carrying a completed-run result).
        """
        job = await self._jobs.get_job_by_job_id(job_id)
        if job is None:
            return
        if job.status == JobStatus.TIMED_OUT:
            if job.error is None:
                await self._jobs.set_error(job_id, {"type": "timed_out"})
            await self._jobs.append_event(job_id, "run_timed_out", {"type": "timed_out"})
        elif job.status == JobStatus.CANCELLED:
            # A late stop that won over a genuine completion may have left a
            # completed-run result behind — overwrite it so the row is consistent.
            if job.result is not None:
                await self._jobs.set_result(job_id, None)
            if job.error is None:
                await self._jobs.set_error(job_id, {"type": "cancelled"})
            await self._jobs.append_event(job_id, "run_cancelled", {"type": "cancelled"})

    def _start_heartbeat(self, job_id: UUID) -> asyncio.Task | None:
        """Spawn the periodic heartbeat task for a run (None when owner unset).

        The task writes the owner + a fresh timestamp immediately, then refreshes
        on the interval until cancelled in ``run``'s finally. A heartbeat write
        failure is swallowed so a transient DB hiccup never kills the run.
        """
        if self._owner is None:
            return None

        async def _beat() -> None:
            while True:
                with contextlib.suppress(Exception):
                    await self._jobs.heartbeat(job_id, self._owner)
                await asyncio.sleep(self._heartbeat_interval_s)

        return asyncio.create_task(_beat())

    @staticmethod
    async def _stop_heartbeat(task: asyncio.Task | None) -> None:
        if task is None:
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task

    async def _reconcile_stop(self, job_id: UUID) -> bool:
        """Force CANCELLED when a STOP signal exists. Returns True if it acted.

        Also stamps the STOP signal ``consumed_at`` so it does not linger: an
        unconsumed STOP would grow the signals table and make a later re-enqueued
        run of the same job self-cancel off the stale signal. This runs in the
        runner's ``finally`` (shielded), so it is the single point where a stop is
        finalized — the right place to mark it consumed.
        """
        if not await self._stop_requested(job_id):
            return False
        await self._jobs.update_job_status(job_id, JobStatus.CANCELLED, finished_timestamp=True)
        await self._jobs.consume_signals(job_id, SignalType.STOP)
        return True

    async def _drive(self, *, job_id: UUID, source_kwargs: dict[str, Any]) -> None:
        """The wrapped coroutine: stream frames, persist, publish, finalize result/error."""
        last_durable_seq = 0
        errored_payload: dict[str, Any] | None = None
        async for frame_bytes, event_type in self._frame_source(**source_kwargs):
            if self._adapter.is_durable(event_type):
                # Vertex/milestone-boundary cooperative cancel: a STOP written to
                # the durable signal table flips the job at the next durable
                # frame. Poll only here (not on every ephemeral token): a stop is
                # honored at boundaries anyway, so a per-token DB read is wasted
                # work that scales with the token stream.
                if await self._stop_requested(job_id):
                    raise self._user_cancelled()
                payload = self._decode_payload(frame_bytes)
                seq = await self._jobs.append_event(job_id, event_type, payload)
                last_durable_seq = seq
                await self._bus.publish(str(job_id), LiveFrame(seq=seq, data=self._restamp_id(frame_bytes, seq)))
                if event_type == self._adapter.terminal_error_type:
                    errored_payload = payload
            else:
                await self._bus.publish(
                    str(job_id),
                    LiveFrame(seq=last_durable_seq, data=self._restamp_id(frame_bytes, last_durable_seq)),
                )

        # Final cooperative-stop check: a STOP that lands after the last frame
        # (or while a fast flow was finishing) must still win over a clean
        # completion, so a user's stop intent is never silently overwritten with
        # COMPLETED. Mirrors the old _finalize_job_status "never overwrite
        # CANCELLED" guard.
        if await self._stop_requested(job_id):
            raise self._user_cancelled()

        if errored_payload is not None:
            await self._jobs.set_error(job_id, errored_payload.get("data", errored_payload))
            # Surface as a failure so execute_with_status writes FAILED.
            msg = "Background job emitted a terminal error event"
            raise RuntimeError(msg)
        await self._jobs.set_result(job_id, {"status": "completed"})

    async def _stop_requested(self, job_id: UUID) -> bool:
        signals = await self._jobs.unconsumed_signals(job_id)
        return any(s.signal_type == SignalType.STOP for s in signals)

    @staticmethod
    def _user_cancelled() -> asyncio.CancelledError:
        # Tagging the cancel as user-initiated makes execute_with_status write
        # CANCELLED (not FAILED). Same convention the queue service uses.
        exc = asyncio.CancelledError()
        exc.args = ("LANGFLOW_USER_CANCELLED",)
        return exc

    @staticmethod
    def _restamp_id(frame_bytes: bytes, seq: int) -> bytes:
        r"""Rewrite the SSE ``id:`` line so the live id == the durable ``seq``.

        The frame source (``_stream_event_frames``) bakes its OWN per-frame stream
        counter into ``id:`` — counting ephemeral tokens and initial frames too —
        so those ids live in a DIFFERENT namespace than ``job_events.seq``. A
        client's ``Last-Event-ID`` (a live id) is later fed to
        ``read_events(after_seq=...)`` (a durable seq), so the two MUST share one
        namespace or a reattach gaps/duplicates milestones. We re-stamp every live
        frame's id with its durable cursor (the row seq for a milestone, the last
        milestone's seq for an ephemeral token) so live ids and durable replay ids
        are one cursor. ``_row_to_frame`` already stamps replayed rows with
        ``id=row.seq``, so live and replay now agree byte-for-byte on the id line.

        Bare-JSON frames (scripted tests, no ``id:`` line) get one appended; a
        frame that already carries an ``id:`` line has it replaced.
        """
        from fastapi.sse import format_sse_event

        text = frame_bytes.decode("utf-8", errors="replace")
        data_str: str | None = None
        for line in text.splitlines():
            if line.startswith("data:"):
                data_str = line[len("data:") :].strip()
                break
        if data_str is None:
            # Not SSE-framed (bare JSON from scripted tests): frame it now with id.
            data_str = text.strip()
        return format_sse_event(data_str=data_str, id=str(seq))

    @staticmethod
    def _decode_payload(frame_bytes: bytes) -> dict[str, Any]:
        r"""Extract the durable JSON payload from a frame.

        The frame may be either a plain JSON object (scripted tests) or a real
        SSE-framed body from ``_stream_event_frames`` shaped like
        ``b"data: {...}\nid: 3\n\n"``. We pull the ``data:`` line's JSON when
        present, else parse the whole frame as JSON. On the off chance a frame
        is neither, persist a string fallback rather than crash the run.
        """
        text = frame_bytes.decode("utf-8", errors="replace")
        data_str = text
        if "data:" in text:
            for line in text.splitlines():
                if line.startswith("data:"):
                    data_str = line[len("data:") :].strip()
                    break
        try:
            return json.loads(data_str)
        except (ValueError, TypeError):
            return {"raw": text}
