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
    from uuid import UUID

    from pydantic import BaseModel
    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.models.user.model import User
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

    async def is_telemetry_enabled(self, user_id: "UUID | None" = None, session: "AsyncSession | None" = None) -> bool:
        """Check if telemetry is enabled based on global settings and user preferences."""
        # Global do-not-track setting takes precedence
        if self.do_not_track:
            return False
        
        # If no user provided, default to enabled (for system-level telemetry)
        if user_id is None:
            return True
            
        # Check user's telemetry preference using the variable system
        if session is None:
            # If no session is provided, we can't check user preferences, default to enabled
            return True
            
        try:
            from langflow.services.deps import get_variable_service
            
            variable_service = get_variable_service()
            # Try to get the telemetry setting from user variables
            telemetry_enabled = await variable_service.get_variable(
                user_id=user_id,
                name="enable_telemetry",
                field="value",
                session=session
            )
            return telemetry_enabled.lower() == "true"
        except ValueError:
            # Variable not found, default to enabled for backward compatibility
            return True
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Error checking telemetry setting for user {user_id}: {e}")
            # On any error, default to enabled
            return True

    async def save_telemetry_preference(self, user_id: "UUID", enabled: bool, session: "AsyncSession") -> None:
        """Save user's telemetry preference as a variable in the Settings category."""
        try:
            from langflow.services.deps import get_variable_service
            from langflow.services.variable.constants import CATEGORY_SETTINGS, GENERIC_TYPE
            
            variable_service = get_variable_service()
            
            # Try to update existing variable, or create if it doesn't exist
            try:
                await variable_service.update_variable(
                    user_id=user_id,
                    name="enable_telemetry",
                    value="true" if enabled else "false",
                    session=session,
                    category=CATEGORY_SETTINGS
                )
            except ValueError:
                # Variable doesn't exist, create it
                await variable_service.create_variable(
                    user_id=user_id,
                    name="enable_telemetry",
                    value="true" if enabled else "false",
                    default_fields=[],
                    type_=GENERIC_TYPE,
                    category=CATEGORY_SETTINGS,
                    session=session,
                )
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error saving telemetry preference for user {user_id}: {e}")

    async def telemetry_worker(self) -> None:
        while self.running:
            event = await self.telemetry_queue.get()
            try:
                if len(event) == 4:  # (func, payload, path, user_id, session)
                    func, payload, path, user_id, session = event
                    await func(payload, path, user_id, session)
                elif len(event) == 3:  # (func, payload, path) - backward compatibility
                    func, payload, path = event
                    await func(payload, path)
                else:  # Simple payload
                    payload = event
                    await self.send_telemetry_data(payload)
            except Exception:  # noqa: BLE001
                logger.error("Error sending telemetry data")
            finally:
                self.telemetry_queue.task_done()

    async def send_telemetry_data(self, payload: BaseModel, path: str | None = None, user_id: "UUID | None" = None, session: "AsyncSession | None" = None) -> None:
        if not await self.is_telemetry_enabled(user_id, session):
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

    async def log_package_run(self, payload: RunPayload, user_id: "UUID | None" = None, session: "AsyncSession | None" = None) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "run", user_id, session), user_id, session)

    async def log_package_shutdown(self) -> None:
        payload = ShutdownPayload(time_running=(datetime.now(timezone.utc) - self._start_time).seconds)
        await self._queue_event(payload)

    async def _queue_event(self, payload, user_id: "UUID | None" = None, session: "AsyncSession | None" = None) -> None:
        if not await self.is_telemetry_enabled(user_id, session) or self._stopping:
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

    async def log_package_playground(self, payload: PlaygroundPayload, user_id: "UUID | None" = None, session: "AsyncSession | None" = None) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "playground", user_id, session), user_id, session)

    async def log_package_component(self, payload: ComponentPayload, user_id: "UUID | None" = None, session: "AsyncSession | None" = None) -> None:
        await self._queue_event((self.send_telemetry_data, payload, "component", user_id, session), user_id, session)

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

    async def migrate_telemetry_preferences(self, session: "AsyncSession") -> None:
        """Migrate existing telemetry preferences from user optins to variables system."""
        try:
            from sqlmodel import select

            from langflow.services.database.models.user.model import User
            from langflow.services.deps import get_variable_service
            from langflow.services.variable.constants import CATEGORY_SETTINGS, GENERIC_TYPE
            
            # Get all users with optins
            stmt = select(User).where(User.optins.is_not(None))
            users = (await session.exec(stmt)).all()
            
            variable_service = get_variable_service()
            
            for user in users:
                if user.optins and "enable_telemetry" in user.optins:
                    try:
                        # Check if variable already exists
                        await variable_service.get_variable(
                            user_id=user.id,
                            name="enable_telemetry",
                            field="value",
                            session=session
                        )
                        logger.debug(f"Telemetry preference already migrated for user {user.id}")
                    except ValueError:
                        # Variable doesn't exist, create it
                        telemetry_enabled = user.optins.get("enable_telemetry", True)
                        await variable_service.create_variable(
                            user_id=user.id,
                            name="enable_telemetry",
                            value="true" if telemetry_enabled else "false",
                            default_fields=[],
                            type_=GENERIC_TYPE,
                            category=CATEGORY_SETTINGS,
                            session=session,
                        )
                        logger.info(f"Migrated telemetry preference for user {user.id}: {telemetry_enabled}")
                        
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error migrating telemetry preferences: {e}")
