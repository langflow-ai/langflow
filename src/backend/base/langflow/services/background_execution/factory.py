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


def select_background_backend(settings, *, job_service, owner=None):
    """Pick the scaled background backend per settings, or None for the default.

    Scaled when ``settings.background_backend == "scaled"``: the durable job
    table is the work queue and separate ``langflow worker`` processes
    lease-claim rows off the shared database. Otherwise return None: the facade
    owns the in-process executor + in-memory bus path directly (no separate
    backend object).
    """
    if settings.background_backend_is_scaled:
        from langflow.services.background_execution.db_backend import DBBackgroundQueue

        return DBBackgroundQueue(
            job_service=job_service,
            owner=owner,
            lease_ttl_s=settings.background_lease_ttl_s,
            poll_interval_s=settings.background_poll_interval_s,
        )
    return None
