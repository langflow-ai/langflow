"""Telemetry service for lfx.

Emits lightweight analytics as OpenTelemetry span events.
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
from typing import TYPE_CHECKING, Any

import orjson

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

try:
    from opentelemetry import trace
    from opentelemetry.trace import SpanKind, Status, StatusCode
except ImportError:  # pragma: no cover - lfx can run without OpenTelemetry installed
    trace = None
    SpanKind = Status = StatusCode = None

_TRACER_NAME = "langflow.telemetry"
_EVENT_PREFIX = "langflow.telemetry"


class TelemetryService(BaseTelemetryService):
    """Async telemetry service that emits events through OpenTelemetry."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        do_not_track: bool | None = None,
    ):
        super().__init__()
        self.base_url = base_url  # Deprecated compatibility hook; OpenTelemetry uses standard OTEL_* config.

        if do_not_track is None:
            do_not_track = os.environ.get("DO_NOT_TRACK", "false").lower() in {"1", "true"}
        self.do_not_track = do_not_track

        self._queue: asyncio.Queue[tuple] = asyncio.Queue()
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
        self._force_flush()
        self._stopping = False

    async def flush(self) -> None:
        if self.do_not_track:
            return
        with contextlib.suppress(Exception):
            await asyncio.wait_for(self._queue.join(), timeout=5.0)
            self._force_flush()

    async def teardown(self) -> None:
        await self.stop()

    # ------------------------------------------------------------------
    # Core send
    # ------------------------------------------------------------------

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        if self.do_not_track:
            return
        try:
            if hasattr(payload, "client_type") and payload.client_type is None:
                payload.client_type = "mcp"
            params = payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
            if not isinstance(payload, VersionPayload):
                params.update(self._common_fields)
            params.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
            params["telemetryPayload"] = payload.__class__.__name__
            if path:
                params["telemetryPath"] = path

            self._emit_event(
                self._get_event_name(payload, path),
                params,
                error=self._payload_represents_error(payload, params),
            )
        except Exception:  # noqa: BLE001
            await logger.adebug("Telemetry emit failed")

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

    def _get_event_name(self, payload: BaseModel, path: str | None) -> str:
        if path:
            return path
        return payload.__class__.__name__.removesuffix("Payload").lower()

    def _payload_represents_error(self, payload: BaseModel, attributes: dict[str, Any]) -> bool:
        if isinstance(payload, ExceptionPayload):
            return True
        return any(
            (key.endswith("Success") or key == "success") and value is False for key, value in attributes.items()
        )

    def _normalize_attribute_value(self, value: Any) -> bool | str | bytes | int | float | list[Any]:
        if isinstance(value, bool | str | bytes | int | float):
            return value
        if isinstance(value, tuple | list):
            return [self._normalize_attribute_value(item) for item in value]
        return orjson.dumps(value, default=str).decode("utf-8")

    def _normalize_attributes(
        self, attributes: dict[str, Any]
    ) -> dict[str, bool | str | bytes | int | float | list[Any]]:
        return {key: self._normalize_attribute_value(value) for key, value in attributes.items() if value is not None}

    def _emit_event(self, event_name: str, attributes: dict[str, Any], *, error: bool = False) -> None:
        if trace is None:
            return

        normalized_attributes = self._normalize_attributes(attributes)
        normalized_attributes[f"{_EVENT_PREFIX}.event"] = event_name
        tracer = trace.get_tracer(_TRACER_NAME)
        with tracer.start_as_current_span(
            f"{_EVENT_PREFIX}.{event_name}",
            kind=SpanKind.INTERNAL,
            attributes=normalized_attributes,
        ) as span:
            span.add_event(event_name, attributes=normalized_attributes)
            if error:
                span.set_status(Status(StatusCode.ERROR))

    def _force_flush(self) -> None:
        if trace is None:
            return
        force_flush = getattr(trace.get_tracer_provider(), "force_flush", None)
        if force_flush is None:
            return
        with contextlib.suppress(Exception):
            force_flush(timeout_millis=5000)
