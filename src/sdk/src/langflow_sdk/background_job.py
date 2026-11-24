"""BackgroundJob — non-blocking flow execution via asyncio.

Wraps an :class:`asyncio.Task` so callers can start a flow run and poll or
await it without blocking the event loop.  Mirrors the ``BackgroundJob`` API
from langflow-ai/sdk PR #1 (Janardan Singh Kavia, IBM Corp., Apache 2.0)
adapted for the Langflow V1 ``/api/v1/run/{id}`` endpoint.

Typical usage::

    async with AsyncClient("https://langflow.example.com", api_key="...") as client:
        job = await client.run_background("my-flow", input_value="Hello!")

        # Option 1 — poll status without blocking
        if job.is_running():
            print("still going…")

        # Option 2 — await completion with a timeout
        response = await job.wait_for_completion(timeout=60.0)
        print(response.get_chat_output())
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

from langflow_sdk.exceptions import LangflowTimeoutError

if TYPE_CHECKING:
    from langflow_sdk.models import RunResponse


class BackgroundJob:
    """Non-blocking handle for an in-flight :meth:`AsyncLangflowClient.run` call.

    Returned by :meth:`AsyncLangflowClient.run_background`.  The underlying
    network request runs in an :class:`asyncio.Task` so the caller's event
    loop remains free.

    Adapted from ``BackgroundJob`` in langflow-ai/sdk PR #1
    (Janardan Singh Kavia, IBM Corp., Apache 2.0).
    """

    def __init__(self, task: asyncio.Task[RunResponse]) -> None:
        self._task = task

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def is_running(self) -> bool:
        """Return ``True`` while the flow run is still in flight."""
        return not self._task.done()

    def is_completed(self) -> bool:
        """Return ``True`` when the run finished successfully (no exception, not cancelled)."""
        return self._task.done() and not self._task.cancelled() and self._task.exception() is None

    def is_failed(self) -> bool:
        """Return ``True`` when the run raised an exception or was cancelled."""
        return self._task.done() and (self._task.cancelled() or self._task.exception() is not None)

    # ------------------------------------------------------------------
    # Awaiting / cancellation
    # ------------------------------------------------------------------

    async def wait_for_completion(
        self,
        *,
        timeout: float | None = None,
    ) -> RunResponse:
        """Await the background run and return the :class:`RunResponse`.

        Args:
            timeout: Maximum seconds to wait.  ``None`` (default) means wait
                     indefinitely.  Raises :exc:`LangflowTimeoutError` on
                     expiry.

        Returns:
            The :class:`RunResponse` from the completed flow run.

        Raises:
            LangflowTimeoutError: If *timeout* elapses before the run finishes.
            Exception: Any exception raised by the underlying flow run is
                re-raised as-is.
        """
        try:
            return await asyncio.wait_for(asyncio.shield(self._task), timeout=timeout)
        except asyncio.TimeoutError as exc:
            msg = (
                f"Background job did not complete within {timeout}s. "
                "The run is still in flight — call wait_for_completion() again "
                "or cancel() to abort."
            )
            raise LangflowTimeoutError(msg) from exc

    async def cancel(self) -> bool:
        """Request cancellation of the background task.

        Returns:
            ``True`` if the cancellation was successfully delivered,
            ``False`` if the task had already finished.
        """
        if self._task.done():
            return False
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        return True
