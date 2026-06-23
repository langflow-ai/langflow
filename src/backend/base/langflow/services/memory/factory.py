"""Factory for langflow's DB-backed memory service."""

from langflow.services.factory import ServiceFactory
from langflow.services.memory.service import LangflowMemoryService


class MemoryServiceFactory(ServiceFactory):
    """Registers ``LangflowMemoryService`` over lfx's in-memory default.

    No dependencies: the service resolves its backend lazily on first use from the
    registered database service, so it must not force the DB service to be created
    eagerly at factory time. ``create`` deliberately carries no parameter or return
    annotations — ``infer_service_types`` evaluates them against the service-class
    namespace, where ``LangflowMemoryService`` is not present.
    """

    def __init__(self) -> None:
        super().__init__(LangflowMemoryService)

    def create(self):
        return LangflowMemoryService()
