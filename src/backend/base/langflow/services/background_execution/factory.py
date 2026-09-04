"""Factory for BackgroundExecutionService."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class BackgroundExecutionServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(BackgroundExecutionService)

    @override
    def create(self, settings_service: SettingsService):
        return BackgroundExecutionService(settings_service)


def select_background_backend(settings, *, client, job_service):
    """Pick the scaled background backend per settings, or None for the default.

    Scaled (redis) when ``settings.background_backend_is_scaled`` is True — a
    separate ``langflow worker`` process drains the claim queue and publishes
    live frames to redis Streams. Otherwise return None: the facade owns the
    in-process executor + in-memory bus path directly (no separate backend
    object). Backend selection follows the existing job_queue_type/redis
    settings; see ``Settings.background_backend_is_scaled``.
    """
    if settings.background_backend_is_scaled:
        from langflow.services.background_execution.redis_backend import RedisBackgroundQueue

        return RedisBackgroundQueue(client=client, job_service=job_service)
    return None
