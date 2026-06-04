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
import json
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, Any

from lfx.log.logger import logger

from langflow.services.background_execution.live_bus import LiveFrame
from langflow.services.database.models.jobs.model import SignalType

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
    ) -> None:
        self._jobs = job_service
        self._bus = live_bus
        self._adapter = adapter
        self._frame_source = frame_source

    async def run(self, *, job_id: UUID, source_kwargs: dict[str, Any]) -> None:
        """Execute one background job to a terminal state."""

        # Bind job_id into the wrapped coroutine so ``execute_with_status``'s
        # own ``job_id`` parameter is not shadowed by a forwarded kwarg.
        async def _wrapped() -> None:
            await self._drive(job_id=job_id, source_kwargs=source_kwargs)

        try:
            await self._jobs.execute_with_status(job_id, _wrapped)
        except asyncio.CancelledError as exc:
            # execute_with_status already mapped status (CANCELLED on a
            # user-tagged cooperative stop, FAILED otherwise). A cooperative
            # stop we raised ourselves should end the run cleanly; only a REAL
            # external task cancel (executor stop()) must propagate so asyncio
            # cancellation semantics hold for the caller.
            user_tagged = bool(exc.args) and exc.args[0] == "LANGFLOW_USER_CANCELLED"
            task = asyncio.current_task()
            externally_cancelled = task is not None and task.cancelling() > 0
            if user_tagged and not externally_cancelled:
                await logger.adebug(f"Background job {job_id} stopped cooperatively")
            else:
                raise
        except Exception as exc:  # noqa: BLE001
            # Terminal error / runtime failure already routed to FAILED by
            # execute_with_status; log and swallow so the worker survives.
            await logger.aerror(f"Background job {job_id} runner error: {exc}", exc_info=True)
        finally:
            await self._bus.close(str(job_id))

    async def _drive(self, *, job_id: UUID, source_kwargs: dict[str, Any]) -> None:
        """The wrapped coroutine: stream frames, persist, publish, finalize result/error."""
        last_durable_seq = 0
        errored_payload: dict[str, Any] | None = None
        async for frame_bytes, event_type in self._frame_source(**source_kwargs):
            # Vertex-boundary cooperative cancel: a STOP written to the durable
            # signal table flips the job at the next frame.
            if await self._stop_requested(job_id):
                raise self._user_cancelled()

            if self._adapter.is_durable(event_type):
                payload = self._decode_payload(frame_bytes)
                seq = await self._jobs.append_event(job_id, event_type, payload)
                last_durable_seq = seq
                await self._bus.publish(str(job_id), LiveFrame(seq=seq, data=frame_bytes))
                if event_type == self._adapter.terminal_error_type:
                    errored_payload = payload
            else:
                await self._bus.publish(str(job_id), LiveFrame(seq=last_durable_seq, data=frame_bytes))

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
