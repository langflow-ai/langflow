"""Catalog-policy service factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from langflow.services.factory import ServiceFactory
from langflow.services.schema import ServiceType

if TYPE_CHECKING:
    from lfx.services.catalog_policy import BaseCatalogPolicyService

    from langflow.services.catalog_policy.service import LangflowCatalogPolicyService
    from langflow.services.database.service import DatabaseService


class CatalogPolicyServiceFactory(ServiceFactory):
    """Create the Langflow database-backed catalog-policy service."""

    name = ServiceType.CATALOG_POLICY_SERVICE.value

    service_class: type[LangflowCatalogPolicyService]

    def __init__(self) -> None:
        from langflow.services.catalog_policy.service import LangflowCatalogPolicyService

        super().__init__(LangflowCatalogPolicyService)

    def create(self, database_service: DatabaseService) -> BaseCatalogPolicyService:
        """Build a catalog-policy service using the injected database service."""
        from lfx.services.deps import get_policy_bundle_service

        return self.service_class(database_service, get_policy_bundle_service())
