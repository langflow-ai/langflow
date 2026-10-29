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
    """Contract every background-execution backend satisfies.

    The facade owns submit/resume/validate semantics and the durable job row;
    a backend supplies execution transport: lifecycle (``start``/``teardown``),
    how a persisted job runs (``dispatch`` in-process, or ``enqueue``/``claim``
    across worker processes), how a resumed row travels back to execution
    (``hand_back``), how a stop request reaches the run (``stop``), how lost
    in-flight work is reconciled (``requeue_lost``), and how a client follows
    the live event stream (``tail``). ``external_workers`` says whether jobs
    run outside the API process, which gates API-side recovery sweeps. The
    durable job table stays the single system of record in every
    implementation — a broker backend may dispatch and fan out, but the DB
    conditional-UPDATE remains the claim.
    """

    external_workers: bool

    async def start(self) -> None: ...

    async def teardown(self) -> None: ...

    async def enqueue(self, job_id: str) -> None: ...

    async def claim(self, *, block_ms: int = 1000) -> str | None: ...

    async def dispatch(self, job_id: Any, *, flow_id: Any, request: dict[str, Any], user: Any) -> None: ...

    async def hand_back(self, job_id: Any, *, flow_id: Any, request: dict[str, Any], user: Any, owner: str) -> bool: ...

    async def stop(self, job_id: str) -> None: ...

    async def requeue_lost(self, *, lease_ttl_s: float = 45.0) -> list[str]: ...

    def tail(self, job_id: str, *, last_seq: int, frame_row: Any) -> AsyncIterator[Any]: ...


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
