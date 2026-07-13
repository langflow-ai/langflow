"""Factory for the lean in-memory memory service used by bare lfx.

Registers ``InMemoryMemoryService`` as the zero-dependency default so a bare
``lfx run`` has working (ephemeral) chat memory. A host with a real database —
langflow, or ``lfx serve`` — selects the Tier 2 ``DatabaseMemoryService``
instead by registering it as a service class (which takes precedence over this
factory), injecting its Tier 1 ``database_service``. See
``lfx.services.memory.database.DatabaseMemoryService``.
"""

from __future__ import annotations

from typing_extensions import override

from lfx.services.factory import ServiceFactory
from lfx.services.memory.service import InMemoryMemoryService


class MemoryServiceFactory(ServiceFactory):
    """Registers the no-deps ``InMemoryMemoryService`` as the lean default."""

    def __init__(self) -> None:
        super().__init__()
        self.service_class = InMemoryMemoryService
        self.dependencies = []

    @override
    def create(self) -> InMemoryMemoryService:
        return InMemoryMemoryService()
