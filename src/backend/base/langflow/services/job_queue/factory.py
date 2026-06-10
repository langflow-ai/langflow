from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override

from langflow.services.factory import ServiceFactory
from langflow.services.job_queue.service import JobQueueService, RedisJobQueueService

if TYPE_CHECKING:
    from lfx.services.settings.service import SettingsService


class JobQueueServiceFactory(ServiceFactory):
    def __init__(self):
        super().__init__(JobQueueService)

    @override
    def create(self, settings_service: SettingsService):
        settings = settings_service.settings
        if settings.job_queue_type == "redis":
            host = settings.redis_queue_host or settings.redis_host
            port = settings.redis_queue_port or settings.redis_port
            return RedisJobQueueService(
                host=host,
                port=port,
                db=settings.redis_queue_db,
                url=settings.redis_queue_url,
                ttl=settings.redis_queue_ttl,
                startup_grace_s=settings.redis_queue_startup_grace_s,
                cancel_marker_ttl=settings.redis_queue_cancel_marker_ttl,
                cancel_channel_enabled=settings.redis_queue_cancel_channel_enabled,
                polling_stale_threshold_s=settings.redis_queue_polling_stale_threshold_s,
                polling_watchdog_interval_s=settings.redis_queue_polling_watchdog_interval_s,
            )
        return JobQueueService()
