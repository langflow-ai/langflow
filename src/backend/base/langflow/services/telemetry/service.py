import asyncio
import os
import platform
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx
from loguru import logger
from pydantic import BaseModel

from langflow.services.base import Service
from langflow.services.telemetry.schema import (
    ComponentPayload,
    PlaygroundPayload,
    RunPayload,
    ShutdownPayload,
    VersionPayload,
)
from langflow.utils.version import get_version_info

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class TelemetryService(Service):
    name = "telemetry_service"

    def __init__(self, settings_service: "SettingsService"):
        super().__init__()
        self.settings_service = settings_service
        self.base_url = settings_service.settings.telemetry_base_url
        self.telemetry_queue: asyncio.Queue = asyncio.Queue()
        self.client = httpx.AsyncClient(timeout=None)
        self.running = False
        self.package = get_version_info()["package"]

        # Check for do-not-track settings
        self.do_not_track = (
            os.getenv("DO_NOT_TRACK", "False").lower() == "true" or settings_service.settings.do_not_track
        )

    async def telemetry_worker(self):
        while self.running:
            func, payload, path = await self.telemetry_queue.get()
            try:
                await func(payload, path)
            except Exception as e:
                logger.error(f"Error sending telemetry data: {e}")
            finally:
                self.telemetry_queue.task_done()

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None):
        if self.do_not_track:
            logger.debug("Telemetry tracking is disabled.")
            return

        url = f"{self.base_url}/{self.package.lower()}"
        if path:
            url = f"{url}/{path}"
        try:
            response = await self.client.get(url, params=payload.model_dump())
            if response.status_code != 200:
                logger.error(f"Failed to send telemetry data: {response.status_code} {response.text}")
            else:
                logger.debug("Telemetry data sent successfully.")
        except Exception as e:
            logger.error(f"Failed to send telemetry data due to: {e}")

    async def log_package_run(self, payload: RunPayload):
        await self.telemetry_queue.put((self.send_telemetry_data, payload, "run"))

    async def log_package_shutdown(self):
        payload = ShutdownPayload(timeRunning=(datetime.now(timezone.utc) - self._start_time).seconds)
        await self.telemetry_queue.put((self.send_telemetry_data, payload, "shutdown"))

    async def log_package_version(self):
        python_version = ".".join(platform.python_version().split(".")[:2])
        version_info = get_version_info()
        architecture = platform.architecture()[0]
        payload = VersionPayload(
            version=version_info["version"],
            platform=platform.platform(),
            python=python_version,
            cacheType=self.settings_service.settings.cache_type,
            backendOnly=self.settings_service.settings.backend_only,
            arch=architecture,
            autoLogin=self.settings_service.auth_settings.AUTO_LOGIN,
        )
        await self.telemetry_queue.put((self.send_telemetry_data, payload, None))

    async def log_package_playground(self, payload: PlaygroundPayload):
        await self.telemetry_queue.put((self.send_telemetry_data, payload, "playground"))

    async def log_package_component(self, payload: ComponentPayload):
        await self.telemetry_queue.put((self.send_telemetry_data, payload, "component"))

    async def start(self):
        if self.running or self.do_not_track:
            return
        try:
            self.running = True
            self._start_time = datetime.now(timezone.utc)
            self.worker_task = asyncio.create_task(self.telemetry_worker())
            asyncio.create_task(self.log_package_version())
        except Exception as e:
            logger.error(f"Error starting telemetry service: {e}")

    async def flush(self):
        if self.do_not_track:
            return
        try:
            await self.telemetry_queue.join()
        except Exception as e:
            logger.error(f"Error flushing logs: {e}")

    async def stop(self):
        if self.do_not_track:
            return
        try:
            self.running = False
            await self.flush()
            self.worker_task.cancel()
            if self.worker_task:
                await self.worker_task
        except Exception as e:
            logger.error(f"Error stopping tracing service: {e}")
