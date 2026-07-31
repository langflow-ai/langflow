"""Default OSS model-provider policy (allow all)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.model_provider_policy.base import BaseModelProviderPolicyService
from lfx.services.schema import ServiceType

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from lfx.services.model_provider_policy.base import ModelProviderPolicyContext, ModelProviderPolicyPurpose


@register_service(ServiceType.MODEL_PROVIDER_POLICY_SERVICE)
class ModelProviderPolicyService(BaseModelProviderPolicyService):
    """OSS default that preserves the historical allow-all behavior."""

    def __init__(self) -> None:
        super().__init__()
        self._approved_provider_ids: frozenset[str] = frozenset()
        self._policy_version: int | None = None
        self._policy_source_available = True
        self.set_ready()
        logger.debug("Model provider policy service initialized (allow all)")

    @property
    def name(self) -> str:
        return ServiceType.MODEL_PROVIDER_POLICY_SERVICE.value

    def get_allowed_provider_ids(
        self,
        *,
        context: ModelProviderPolicyContext,  # noqa: ARG002
        candidate_provider_ids: frozenset[str],
        purpose: ModelProviderPolicyPurpose,  # noqa: ARG002
    ) -> Collection[str]:
        with self._snapshot_cache_lock:
            if not self._policy_source_available:
                return frozenset()
            approved_provider_ids = self._approved_provider_ids
        if not approved_provider_ids:
            return candidate_provider_ids
        return candidate_provider_ids & approved_provider_ids

    @property
    def approved_provider_ids(self) -> frozenset[str]:
        """Return the install-wide deployment ceiling; empty means unrestricted."""
        return self._approved_provider_ids

    @property
    def policy_version(self) -> int | None:
        """Return the durable policy version last applied in this process."""
        return self._policy_version

    @property
    def policy_source_available(self) -> bool:
        """Return whether the durable ceiling was available on the last refresh."""
        return self._policy_source_available

    def fail_closed(self, *, deny_all_required: bool = False) -> bool:
        """Deny providers after a refresh failure only when a ceiling is active.

        An empty approved-provider set is the explicit OSS allow-all default. A
        transient refresh failure must not turn an unconfigured installation
        into deny-all, while an installation with a restrictive ceiling must
        keep failing closed until the durable source recovers. A caller sets
        ``deny_all_required`` when a newly read restrictive state failed during
        application or durable-source corruption makes the ceiling impossible
        to evaluate safely.
        """
        with self._snapshot_cache_lock:
            if not self._approved_provider_ids and not deny_all_required:
                return False
            if not self._policy_source_available:
                return False
            self._policy_source_available = False
            self._snapshot_cache.clear()
            self._snapshot_cache_generation += 1
            return True

    def set_approved_provider_ids(self, provider_ids: Iterable[str], *, version: int | None = None) -> bool:
        """Replace the deployment ceiling atomically, rejecting stale versions."""
        from lfx.base.models.provider_registry import resolve_provider_id

        approved_provider_ids = frozenset(resolve_provider_id(provider_id) for provider_id in provider_ids)
        with self._snapshot_cache_lock:
            if version is not None and self._policy_version is not None and version < self._policy_version:
                return False
            if (
                approved_provider_ids == self._approved_provider_ids
                and (version is None or version == self._policy_version)
                and self._policy_source_available
            ):
                return False
            self._approved_provider_ids = approved_provider_ids
            self._policy_source_available = True
            if version is not None:
                self._policy_version = version
            self._snapshot_cache.clear()
            self._snapshot_cache_generation += 1
            return True
