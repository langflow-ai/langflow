"""Telemetry service for lfx.

Sends lightweight analytics via GET requests to a Scarf pixel endpoint.
All data goes through an async queue so tool calls are never blocked.
Respects DO_NOT_TRACK env var and the settings flag.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import os
import platform
import traceback
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from lfx.log.logger import logger
from lfx.services.telemetry.base import BaseTelemetryService
from lfx.services.telemetry.schema import (
    ExceptionPayload,
    MCPToolPayload,
    ShutdownPayload,
    VersionPayload,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

_DEFAULT_BASE_URL = "https://langflow.gateway.scarf.sh"


class TelemetryService(BaseTelemetryService):
    """Async telemetry service that sends events to Scarf via query params."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        do_not_track: bool | None = None,
    ):
        super().__init__()
        self.base_url = base_url or os.environ.get("LANGFLOW_TELEMETRY_BASE_URL", _DEFAULT_BASE_URL)

        if do_not_track is None:
            do_not_track = os.environ.get("DO_NOT_TRACK", "false").lower() in {"1", "true"}
        self.do_not_track = do_not_track

        self._queue: asyncio.Queue[tuple] = asyncio.Queue()
        self._client: httpx.AsyncClient | None = None
        self._worker_task: asyncio.Task | None = None
        self._running = False
        self._stopping = False
        self._start_time = datetime.now(timezone.utc)

        self._common_fields = {
            "langflow_version": self._get_version(),
            "platform": "mcp",
            "os": platform.system().lower(),
        }
        self.set_ready()

    @property
    def name(self) -> str:
        return "telemetry_service"

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._running or self.do_not_track:
            return
        self._running = True
        self._start_time = datetime.now(timezone.utc)
        self._client = httpx.AsyncClient(timeout=10.0)
        self._worker_task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if not self._running or self._stopping:
            return
        self._stopping = True
        await self.flush()
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._worker_task
        if self._client:
            await self._client.aclose()
            self._client = None
        self._stopping = False

    async def flush(self) -> None:
        if self.do_not_track:
            return
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._queue.join(), timeout=5.0)

    async def teardown(self) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        if self.do_not_track or self._client is None:
            return
        try:
            url = f"{self.base_url}/{path}" if path else self.base_url
            params = payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
            if not isinstance(payload, VersionPayload):
                params.update(self._common_fields)
            params.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

            resp = await self._client.get(url, params=params)
            if resp.status_code != httpx.codes.OK:
                await logger.adebug(f"Telemetry response {resp.status_code}")
        except Exception:  # noqa: BLE001
            await logger.adebug("Telemetry send failed")

    # ------------------------------------------------------------------
    # Public log methods
    # ------------------------------------------------------------------

    async def log_package_run(self, payload: BaseModel) -> None:
        await self._enqueue(payload, "run")

    async def log_package_shutdown(self) -> None:
        elapsed = int((datetime.now(timezone.utc) - self._start_time).total_seconds())
        await self._enqueue(ShutdownPayload(time_running=elapsed), "shutdown")

    async def log_package_version(self) -> None:
        python_version = ".".join(platform.python_version().split(".")[:2])
        payload = VersionPayload(
            package="lfx",
            version=self._get_version(),
            platform=platform.platform(),
            python=python_version,
            arch=platform.machine(),
            client_type="mcp",
        )
        await self._enqueue(payload, None)

    async def log_package_playground(self, payload: BaseModel) -> None:
        await self._enqueue(payload, "playground")

    async def log_package_component(self, payload: BaseModel) -> None:
        await self._enqueue(payload, "component")

    async def log_exception(self, exc: Exception, context: str) -> None:
        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        payload = ExceptionPayload(
            exception_type=exc.__class__.__name__,
            exception_message=str(exc)[:500],
            exception_context=context,
            stack_trace_hash=hashlib.sha256(stack.encode()).hexdigest()[:16],
        )
        await self._enqueue(payload, "exception")

    async def log_mcp_tool(self, payload: MCPToolPayload) -> None:
        await self._enqueue(payload, "mcp_tool")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _enqueue(self, payload: BaseModel, path: str | None) -> None:
        if self.do_not_track or self._stopping:
            return
        await self._queue.put((payload, path))

    async def _worker(self) -> None:
        while self._running:
            got_item = False
            try:
                payload, path = await self._queue.get()
                got_item = True
                await self.send_telemetry_data(payload, path)
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001
                with contextlib.suppress(Exception):
                    await logger.adebug("Telemetry worker error")
            finally:
                if got_item:
                    self._queue.task_done()

    @staticmethod
    def _get_version() -> str:
        try:
            from importlib.metadata import version

            return version("lfx")
        except Exception:  # noqa: BLE001
            return "unknown"
