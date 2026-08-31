"""Default in-process coordinator for deployment policy bundles."""

from __future__ import annotations

import threading

from lfx.log.logger import logger
from lfx.services import register_service
from lfx.services.policy_bundle.base import BasePolicyBundleService, PolicyBundleSnapshot
from lfx.services.schema import ServiceType


@register_service(ServiceType.POLICY_BUNDLE_SERVICE)
class PolicyBundleService(BasePolicyBundleService):
    """Thread-safe owner of one immutable provider-and-catalog snapshot."""

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = PolicyBundleSnapshot()
        self._hydrated = False
        self._source_available = True
        self._lock = threading.RLock()
        self.set_ready()
        logger.debug("Policy bundle service initialized")

    @property
    def name(self) -> str:
        return ServiceType.POLICY_BUNDLE_SERVICE.value

    @property
    def snapshot(self) -> PolicyBundleSnapshot:
        return self._snapshot

    @property
    def hydrated(self) -> bool:
        return self._hydrated

    @property
    def source_available(self) -> bool:
        return self._source_available

    def publish(self, snapshot: PolicyBundleSnapshot) -> bool:
        with self._lock:
            current = self._snapshot
            if snapshot.revision < current.revision:
                return False
            if snapshot.revision == current.revision:
                current_identity = (
                    current.initialized,
                    current.source,
                    current.approved_provider_ids,
                    current.blocked_component_keys,
                    current.blocked_template_keys,
                    current.blocked_model_keys,
                    current.content_hash,
                    current.reason,
                    current.rollback_of_revision,
                )
                snapshot_identity = (
                    snapshot.initialized,
                    snapshot.source,
                    snapshot.approved_provider_ids,
                    snapshot.blocked_component_keys,
                    snapshot.blocked_template_keys,
                    snapshot.blocked_model_keys,
                    snapshot.content_hash,
                    snapshot.reason,
                    snapshot.rollback_of_revision,
                )
                if snapshot_identity != current_identity:
                    msg = f"Policy bundle revision {snapshot.revision} has conflicting content"
                    raise ValueError(msg)
                changed = not self._source_available or not self._hydrated
                self._snapshot = snapshot
                self._source_available = True
                self._hydrated = snapshot.revision > 0
                return changed
            self._snapshot = snapshot
            self._hydrated = True
            self._source_available = True
            return True

    def mark_source_unavailable(self) -> bool:
        with self._lock:
            if not self._source_available:
                return False
            self._source_available = False
            return True

    async def teardown(self) -> None:
        with self._lock:
            self._snapshot = PolicyBundleSnapshot()
            self._hydrated = False
            self._source_available = True
