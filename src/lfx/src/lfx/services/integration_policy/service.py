"""Default OSS integration policy read from the shared policy bundle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.integration_policy.base import BaseIntegrationPolicyService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection

    from lfx.services.integration_policy.base import IntegrationPolicyContext, IntegrationPolicyPurpose
    from lfx.services.policy_bundle import BasePolicyBundleService


@register_service(ServiceType.INTEGRATION_POLICY_SERVICE)
class IntegrationPolicyService(BaseIntegrationPolicyService):
    """OSS default: an empty ceiling is unrestricted, blocking nothing.

    This preserves pass-through behavior for every installation that never
    configures integration governance. An Enterprise plugin replaces the
    service through ``lfx.toml`` and may read the same empty ceiling as
    deny-all.
    """

    def __init__(self, policy_bundle_service: BasePolicyBundleService | None = None) -> None:
        super().__init__()
        self._policy_bundle_service = policy_bundle_service
        self.set_ready()
        logger.debug("Integration policy service initialized (unrestricted)")

    @property
    def name(self) -> str:
        return ServiceType.INTEGRATION_POLICY_SERVICE.value

    @property
    def policy_bundle_service(self) -> BasePolicyBundleService | None:
        """Return the shared bundle coordinator used by this service, if any."""
        return self._policy_bundle_service

    @property
    def approved_provider_ids(self) -> frozenset[str]:
        """Return the install-wide integration ceiling; empty means unrestricted."""
        if self._policy_bundle_service is None:
            return frozenset()
        return self._policy_bundle_service.snapshot.approved_integration_provider_ids

    @property
    def blocked_action_keys(self) -> frozenset[str]:
        """Return the install-wide denied action keys."""
        if self._policy_bundle_service is None:
            return frozenset()
        return self._policy_bundle_service.snapshot.blocked_integration_action_keys

    @property
    def policy_version(self) -> int | None:
        """Return the durable policy revision last applied in this process."""
        if self._policy_bundle_service is None:
            return None
        return self._policy_bundle_service.snapshot.revision

    @property
    def policy_source_available(self) -> bool:
        """Return whether the durable ceiling was available on the last refresh."""
        if self._policy_bundle_service is None:
            return True
        return self._policy_bundle_service.source_available

    def get_allowed_provider_ids(
        self,
        *,
        context: IntegrationPolicyContext,  # noqa: ARG002
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,  # noqa: ARG002
    ) -> Collection[str]:
        approved_provider_ids = self.approved_provider_ids
        if not approved_provider_ids:
            # An unconfigured installation must not become deny-all after a
            # transient refresh failure, matching the model-provider default.
            return candidate_provider_ids
        if not self.policy_source_available:
            return frozenset()
        return candidate_provider_ids & approved_provider_ids

    def get_blocked_action_keys(
        self,
        *,
        context: IntegrationPolicyContext,  # noqa: ARG002
        purpose: IntegrationPolicyPurpose,  # noqa: ARG002
    ) -> Collection[str]:
        """Surface the deployment-wide action deny-list from the shared bundle."""
        return self.blocked_action_keys
