"""Default fail-open catalog-policy service for standalone LFX."""

from __future__ import annotations

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.catalog_policy.base import BaseCatalogPolicyService, CatalogPolicySnapshot
from lfx.services.schema import ServiceType


@register_service(ServiceType.CATALOG_POLICY_SERVICE)
class CatalogPolicyService(BaseCatalogPolicyService):
    """Standalone default with an immutable empty, allow-all snapshot."""

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = CatalogPolicySnapshot()
        self.set_ready()
        logger.debug("Catalog policy service initialized (allow all)")

    @property
    def name(self) -> str:
        """Return the canonical service-type name."""
        return ServiceType.CATALOG_POLICY_SERVICE.value

    @property
    def snapshot(self) -> CatalogPolicySnapshot:
        """Return the immutable allow-all snapshot."""
        return self._snapshot
