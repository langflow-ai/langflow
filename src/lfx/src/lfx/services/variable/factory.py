"""Factory for the lean env-only variable service used by bare lfx."""

from __future__ import annotations

from typing_extensions import override

from lfx.services.factory import ServiceFactory
from lfx.services.variable.service import VariableService


class VariableServiceFactory(ServiceFactory):
    """Registers the env-only ``VariableService`` as the no-deps default.

    This is the lean default for bare lfx: it has no dependencies and provides
    in-memory + environment-variable resolution so variable-using components get
    a real service instead of ``None``. A heavier backend (e.g. langflow) can
    override it through the same service manager with a database-backed variant.
    """

    def __init__(self) -> None:
        super().__init__()
        self.service_class = VariableService
        self.dependencies = []

    @override
    def create(self) -> VariableService:
        return VariableService()
