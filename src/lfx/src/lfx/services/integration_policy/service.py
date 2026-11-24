"""Default OSS integration policy read from the shared policy bundle."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.integration_policy.base import BaseIntegrationPolicyService
from lfx.services.policy_bundle.base import PolicyBundleSnapshot
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection, Iterator

    from lfx.services.integration_policy.base import IntegrationPolicyContext, IntegrationPolicyPurpose
    from lfx.services.policy_bundle import BasePolicyBundleService


@register_service(ServiceType.INTEGRATION_POLICY_SERVICE)
class IntegrationPolicyService(BaseIntegrationPolicyService):
    """OSS default: an empty ceiling is unrestricted, blocking nothing.

    This preserves pass-through behavior for every installation that never
    configures integration governance. An Enterprise plugin replaces the
    service through ``lfx.toml``. Installing it must preserve persisted empty
    ceilings; deny-all requires an explicitly configured external ceiling.
    """

    def __init__(self, policy_bundle_service: BasePolicyBundleService | None = None) -> None:
        super().__init__()
        self._policy_bundle_service = policy_bundle_service
        self._resolution_state: ContextVar[tuple[PolicyBundleSnapshot, bool] | None] = ContextVar(
            "integration_policy_resolution_state", default=None
        )
        self.set_ready()
        logger.debug("Integration policy service initialized (unrestricted)")

    @property
    def name(self) -> str:
        return ServiceType.INTEGRATION_POLICY_SERVICE.value

    @property
    def policy_bundle_service(self) -> BasePolicyBundleService | None:
        """Return the shared bundle coordinator used by this service, if any."""
        return self._policy_bundle_service

    def _current_bundle_state(self) -> tuple[PolicyBundleSnapshot, bool]:
        captured = self._resolution_state.get()
        if captured is not None:
            return captured
        if self._policy_bundle_service is None:
            return PolicyBundleSnapshot(), True
        return self._policy_bundle_service.read_state()

    @contextmanager
    def _resolution_scope(self) -> Iterator[None]:
        # Context-local capture preserves plugin hooks across awaits without
        # sharing an in-flight revision with another request or thread.
        token = self._resolution_state.set(self._current_bundle_state())
        try:
            yield
        finally:
            self._resolution_state.reset(token)

    @property
    def approved_provider_ids(self) -> frozenset[str]:
        """Return the install-wide integration ceiling; empty means unrestricted."""
        return self._current_bundle_state()[0].approved_integration_provider_ids

    @property
    def blocked_action_keys(self) -> frozenset[str]:
        """Return the install-wide denied action keys."""
        return self._current_bundle_state()[0].blocked_integration_action_keys

    @property
    def policy_version(self) -> int | None:
        """Return the durable policy revision last applied in this process."""
        if self._policy_bundle_service is None:
            return None
        return self._current_bundle_state()[0].revision

    @property
    def policy_source_available(self) -> bool:
        """Return whether the durable ceiling was available on the last refresh."""
        return self._current_bundle_state()[1]

    def get_allowed_provider_ids(
        self,
        *,
        context: IntegrationPolicyContext,  # noqa: ARG002
        candidate_provider_ids: frozenset[str],
        purpose: IntegrationPolicyPurpose,  # noqa: ARG002
    ) -> Collection[str]:
        approved_provider_ids = self.approved_provider_ids
        if not self.policy_source_available and (approved_provider_ids or self.blocked_action_keys):
            return frozenset()
        if not approved_provider_ids:
            # An unconfigured installation must not become deny-all after a
            # transient refresh failure, matching the model-provider default.
            return candidate_provider_ids
        return candidate_provider_ids & approved_provider_ids

    def get_blocked_action_keys(
        self,
        *,
        context: IntegrationPolicyContext,  # noqa: ARG002
        purpose: IntegrationPolicyPurpose,  # noqa: ARG002
    ) -> Collection[str]:
        """Surface the deployment-wide action deny-list from the shared bundle."""
        return self.blocked_action_keys
