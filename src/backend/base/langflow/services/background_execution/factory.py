"""Factory for BackgroundExecutionService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from typing_extensions import override

from langflow.services.background_execution.service import BackgroundExecutionService
from langflow.services.factory import ServiceFactory

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from lfx.services.settings.service import SettingsService


class BackgroundBackend(Protocol):
    """Contract a scaled background-execution backend must satisfy.

    The facade owns submit/resume/validate semantics and the durable job row;
    a backend supplies transport: how a persisted QUEUED row reaches a worker
    (``enqueue``/``claim``), how a stop request travels (``stop``), how lost
    in-flight work is reconciled (``requeue_lost``), and how durable events
    reach a reattaching client (``events``). The durable job table stays the
    single system of record in every implementation — a broker backend may
    dispatch and fan out, but the DB conditional-UPDATE remains the claim.
    """

    async def enqueue(self, job_id: str) -> None: ...

    async def claim(self, *, block_ms: int = 1000) -> str | None: ...

    async def stop(self, job_id: str) -> None: ...

    async def requeue_lost(self, *, lease_ttl_s: float = 45.0) -> list[str]: ...

    def events(self, job_id: str, last_event_id: int = 0) -> AsyncIterator[Any]: ...

    async def teardown(self) -> None: ...


class BackgroundExecutionServiceFactory(ServiceFactory):
    def __init__(self) -> None:
        super().__init__(BackgroundExecutionService)

    @override
    def create(self, settings_service: SettingsService):
        return BackgroundExecutionService(settings_service)


def select_background_backend(settings, *, job_service, owner=None) -> BackgroundBackend | None:
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
            claim_candidates=settings.background_claim_candidates,
        )
    return None
