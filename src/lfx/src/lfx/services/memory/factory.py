"""Factory for the lean in-memory memory service used by bare lfx."""

from __future__ import annotations

from typing_extensions import override

from lfx.services.factory import ServiceFactory
from lfx.services.memory.service import InMemoryMemoryService


class MemoryServiceFactory(ServiceFactory):
    """Registers the no-deps ``InMemoryMemoryService`` as the lean default.

    The backend is chosen once, at creation time, from the registered database
    service: with a real (non-noop) DB a DB-backed backend is appropriate, while
    bare lfx without a database gets the round-tripping in-memory store. A heavier
    backend (e.g. langflow's DB-backed memory service) overrides this through the
    same service manager.
    """

    def __init__(self) -> None:
        super().__init__()
        self.service_class = InMemoryMemoryService
        self.dependencies = []

    @override
    def create(self) -> InMemoryMemoryService:
        from lfx.services.database.service import NoopDatabaseService
        from lfx.services.deps import get_db_service

        if isinstance(get_db_service(), NoopDatabaseService):
            return InMemoryMemoryService()
        # TODO(follow-up): return DatabaseBackedMemoryService() for LFX executors
        # (Postgres) once it lands. The seam is here so a non-noop DB — including a
        # PG-configured bare-lfx run — resolves to the persistent backend without
        # touching the ABC or the deps getter.
        return InMemoryMemoryService()
