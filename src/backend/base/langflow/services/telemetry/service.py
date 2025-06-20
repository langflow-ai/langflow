"""Telemetry and analytics service for Langflow.

This module provides the TelemetryService that handles usage analytics
and telemetry data collection for Langflow, including:
- Usage metrics collection and reporting
- Performance monitoring and analytics
- Error tracking and diagnostics
- Feature usage statistics
- OpenTelemetry integration for distributed tracing
- Privacy-respecting telemetry with opt-out support
- System information and version tracking
- Component usage analytics

The TelemetryService helps improve Langflow by collecting anonymous
usage data while respecting user privacy preferences and providing
insights for product development.
"""

from __future__ import annotations

import asyncio
import os
import platform
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger

from langflow.services.base import Service
from langflow.services.telemetry.opentelemetry import OpenTelemetry
from langflow.services.telemetry.schema import (
    ComponentPayload,
    PlaygroundPayload,
    RunPayload,
    ShutdownPayload,
    VersionPayload,
)
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from pydantic import BaseModel

    from langflow.services.settings.service import SettingsService


class TelemetryService(Service):
    name = "telemetry_service"

    def __init__(self, settings_service: SettingsService):
        super().__init__()
        self.settings_service = settings_service
        self.base_url = settings_service.settings.telemetry_base_url
        self.telemetry_queue: asyncio.Queue = asyncio.Queue()
        self.client = httpx.AsyncClient(timeout=10.0)  # Set a reasonable timeout
        self.running = False
        self._stopping = False

        self.ot = OpenTelemetry(prometheus_enabled=settings_service.settings.prometheus_enabled)
        self.architecture: str | None = None
        self.worker_task: asyncio.Task | None = None
        # Check for do-not-track settings
        self.do_not_track = (
            os.getenv("DO_NOT_TRACK", "False").lower() == "true" or settings_service.settings.do_not_track
        )
        self.log_package_version_task: asyncio.Task | None = None

    async def telemetry_worker(self) -> None:
        while self.running:
            func, payload, path = await self.telemetry_queue.get()
            try:
                await func(payload, path)
            except Exception:  # noqa: BLE001
                logger.error("Error sending telemetry data")
            finally:
                self.telemetry_queue.task_done()

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None) -> None:
        if self.do_not_track:
            logger.debug("Telemetry tracking is disabled.")
            return

        url = f"{self.base_url}"
        if path:
            url = f"{url}/{path}"
        try:
            payload_dict = payload.model_dump(by_alias=True, exclude_none=True, exclude_unset=True)
            response = await self.client.get(url, params=payload_dict)
            if response.status_code != httpx.codes.OK:
                logger.error(f"Failed to send telemetry data: {response.status_code} {response.text}")
            else:
                logger.debug("Telemetry data sent successfully.")
        except httpx.HTTPStatusError:
            logger.error("HTTP error occurred")
        except httpx.RequestError:
            logger.error("Request error occurred")
        except Exception:  # noqa: BLE001
            logger.error("Unexpected error occurred")

    async def log_package_run(self, payload: RunPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "run"))

    async def log_package_shutdown(self) -> None:
        payload = ShutdownPayload(time_running=(datetime.now(timezone.utc) - self._start_time).seconds)
        await self._queue_event(payload)

    async def _queue_event(self, payload) -> None:
        if self.do_not_track or self._stopping:
            return
        await self.telemetry_queue.put(payload)

    def _get_langflow_desktop(self) -> bool:
        # Coerce to bool, could be 1, 0, True, False, "1", "0", "True", "False"
        return str(os.getenv("LANGFLOW_DESKTOP", "False")).lower() in {"1", "true"}

    async def log_package_version(self) -> None:
        python_version = ".".join(platform.python_version().split(".")[:2])
        version_info = get_version_info()
        if self.architecture is None:
            self.architecture = (await asyncio.to_thread(platform.architecture))[0]
        payload = VersionPayload(
            package=version_info["package"].lower(),
            version=version_info["version"],
            platform=platform.platform(),
            python=python_version,
            cache_type=self.settings_service.settings.cache_type,
            backend_only=self.settings_service.settings.backend_only,
            arch=self.architecture,
            auto_login=self.settings_service.auth_settings.AUTO_LOGIN,
            desktop=self._get_langflow_desktop(),
        )
        await self._queue_event((self.send_telemetry_data, payload, None))

    async def log_package_playground(self, payload: PlaygroundPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "playground"))

    async def log_package_component(self, payload: ComponentPayload) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "component"))

    def start(self) -> None:
        if self.running or self.do_not_track:
            return
        try:
            self.running = True
            self._start_time = datetime.now(timezone.utc)
            self.worker_task = asyncio.create_task(self.telemetry_worker())
            self.log_package_version_task = asyncio.create_task(self.log_package_version())
        except Exception:  # noqa: BLE001
            logger.exception("Error starting telemetry service")

    async def flush(self) -> None:
        if self.do_not_track:
            return
        try:
            await self.telemetry_queue.join()
        except Exception:  # noqa: BLE001
            logger.exception("Error flushing logs")

    @staticmethod
    async def _cancel_task(task: asyncio.Task, cancel_msg: str) -> None:
        task.cancel(cancel_msg)
        await asyncio.wait([task])
        if not task.cancelled():
            exc = task.exception()
            if exc is not None:
                raise exc

    async def stop(self) -> None:
        if self.do_not_track or self._stopping:
            return
        try:
            self._stopping = True
            # flush all the remaining events and then stop
            await self.flush()
            self.running = False
            if self.worker_task:
                await self._cancel_task(self.worker_task, "Cancel telemetry worker task")
            if self.log_package_version_task:
                await self._cancel_task(self.log_package_version_task, "Cancel telemetry log package version task")
            await self.client.aclose()
        except Exception:  # noqa: BLE001
            logger.exception("Error stopping tracing service")

    async def teardown(self) -> None:
        await self.stop()
