"""Database-backed catalog-policy service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lfx.services.catalog_policy import BaseCatalogPolicyService, CatalogPolicySnapshot, CatalogPolicyUpdate
from lfx.services.deps import session_scope, session_scope_readonly
from lfx.services.policy_bundle import BasePolicyBundleService, PolicyBundleSnapshot
from lfx.services.schema import ServiceType
from sqlmodel import col, select

from langflow.services.database.models.catalog_policy import (
    CatalogPolicyMode,
    CatalogPolicyRule,
    CatalogPolicyScope,
    CatalogResourceKind,
)
from langflow.services.policy_bundle import (
    PolicyBundleRevisionConflictError,
    apply_policy_bundle_state,
    get_policy_bundle_state,
    replace_policy_bundle_state,
)

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.service import DatabaseService


_CATALOG_POLICY_CAS_ATTEMPTS = 3


def _normalize_keys(keys: Collection[str]) -> frozenset[str]:
    """Trim and deduplicate keys while preserving their case."""
    normalized: set[str] = set()
    for raw_key in keys:
        key = raw_key.strip()
        if not key:
            msg = "Catalog policy keys must not be empty"
            raise ValueError(msg)
        normalized.add(key)
    return frozenset(normalized)


class LangflowCatalogPolicyService(BaseCatalogPolicyService):
    """Catalog projection of the process-wide immutable policy bundle."""

    def __init__(
        self,
        database_service: DatabaseService | None,
        policy_bundle_service: BasePolicyBundleService | None = None,
    ) -> None:
        super().__init__()
        self.database_service = database_service
        self._policy_bundle_service = policy_bundle_service
        self._legacy_snapshot = CatalogPolicySnapshot()
        self._legacy_hydrated = False
        self._projected_snapshot: tuple[PolicyBundleSnapshot, CatalogPolicySnapshot] | None = None
        self._write_lock = asyncio.Lock()
        # Direct service-class registration does not call set_ready(), unlike
        # factory creation. The fail-open snapshot is usable immediately.
        self.set_ready()

    @property
    def name(self) -> str:
        """Return the canonical service-type name."""
        return ServiceType.CATALOG_POLICY_SERVICE.value

    @property
    def snapshot(self) -> CatalogPolicySnapshot:
        """Return the current immutable process-local snapshot."""
        if self._policy_bundle_service is None:
            return self._legacy_snapshot
        bundle = self._policy_bundle_service.snapshot
        projected = self._projected_snapshot
        if projected is None or projected[0] is not bundle:
            projected = (
                bundle,
                CatalogPolicySnapshot(
                    blocked_component_keys=bundle.blocked_component_keys,
                    blocked_template_keys=bundle.blocked_template_keys,
                ),
            )
            self._projected_snapshot = projected
        return projected[1]

    @property
    def policy_bundle_snapshot(self) -> PolicyBundleSnapshot:
        if self._policy_bundle_service is None:
            return PolicyBundleSnapshot(
                blocked_component_keys=self._legacy_snapshot.blocked_component_keys,
                blocked_template_keys=self._legacy_snapshot.blocked_template_keys,
            )
        return self._policy_bundle_service.snapshot

    @property
    def supports_policy_bundle_updates(self) -> bool:
        return self._policy_bundle_service is not None

    def apply_policy_bundle(self, snapshot: PolicyBundleSnapshot) -> bool:
        if self._policy_bundle_service is None:
            return False
        return self._policy_bundle_service.publish(snapshot)

    @property
    def hydrated(self) -> bool:
        """Return whether durable policy has been loaded successfully."""
        if self._policy_bundle_service is None:
            return self._legacy_hydrated
        return self._policy_bundle_service.hydrated

    async def hydrate(self) -> CatalogPolicySnapshot:
        """Load global block rules and atomically publish a complete snapshot.

        A failed load leaves the previous snapshot untouched. Callers may log
        the failure and continue with its fail-open decision surface.
        """
        async with self._write_lock:
            if self._policy_bundle_service is None:
                async with session_scope_readonly() as session:
                    snapshot, _rows = await self._read_policy(session)
                self._legacy_snapshot = snapshot
                self._legacy_hydrated = True
                return snapshot

            async with session_scope_readonly() as session:
                bundle = await get_policy_bundle_state(session)
            apply_policy_bundle_state(bundle)
            return self.snapshot

    async def replace_blocked_component_keys(
        self,
        keys: Collection[str],
        *,
        actor_user_id: UUID | None,
    ) -> CatalogPolicyUpdate:
        """Replace the global component block set and publish it after commit."""
        return await self._replace_blocked_keys(
            CatalogResourceKind.COMPONENT,
            keys,
            actor_user_id=actor_user_id,
        )

    async def replace_blocked_template_keys(
        self,
        keys: Collection[str],
        *,
        actor_user_id: UUID | None,
    ) -> CatalogPolicyUpdate:
        """Replace the global template block set and publish it after commit."""
        return await self._replace_blocked_keys(
            CatalogResourceKind.TEMPLATE,
            keys,
            actor_user_id=actor_user_id,
        )

    async def _replace_blocked_keys(
        self,
        resource_kind: CatalogResourceKind,
        keys: Collection[str],
        *,
        actor_user_id: UUID | None,
    ) -> CatalogPolicyUpdate:
        desired = _normalize_keys(keys)

        async with self._write_lock:
            if self._policy_bundle_service is None:
                return await self._replace_legacy_blocked_keys(
                    resource_kind,
                    desired,
                    actor_user_id=actor_user_id,
                )

            for attempt in range(_CATALOG_POLICY_CAS_ATTEMPTS):
                async with session_scope() as session:
                    current = await get_policy_bundle_state(session)
                    if resource_kind == CatalogResourceKind.COMPONENT:
                        current_keys = current.blocked_component_keys
                        components = desired
                        templates = current.blocked_template_keys
                    else:
                        current_keys = current.blocked_template_keys
                        components = current.blocked_component_keys
                        templates = desired
                    try:
                        committed = await replace_policy_bundle_state(
                            session,
                            expected_revision=current.revision,
                            approved_provider_ids=current.approved_provider_ids,
                            blocked_component_keys=components,
                            blocked_template_keys=templates,
                            blocked_model_keys=current.blocked_model_keys,
                            actor_user_id=actor_user_id,
                            reason=f"Replace blocked {resource_kind.value} catalog keys",
                        )
                    except PolicyBundleRevisionConflictError:
                        if attempt == _CATALOG_POLICY_CAS_ATTEMPTS - 1:
                            raise
                        continue
                    break

            apply_policy_bundle_state(committed)
            return CatalogPolicyUpdate(
                snapshot=CatalogPolicySnapshot(
                    blocked_component_keys=committed.blocked_component_keys,
                    blocked_template_keys=committed.blocked_template_keys,
                ),
                added=desired - current_keys,
                removed=current_keys - desired,
            )

    async def _replace_legacy_blocked_keys(
        self,
        resource_kind: CatalogResourceKind,
        desired: frozenset[str],
        *,
        actor_user_id: UUID | None,
    ) -> CatalogPolicyUpdate:
        """Preserve the pre-bundle service seam for direct/plugin construction."""
        async with session_scope() as session:
            current_snapshot, rows = await self._read_policy(session)
            current_rows = {row.resource_key: row for row in rows if row.resource_kind == resource_kind.value}
            current = frozenset(current_rows)
            added = desired - current
            removed = current - desired

            for key in removed:
                await session.delete(current_rows[key])
            for key in added:
                session.add(
                    CatalogPolicyRule(
                        resource_kind=resource_kind.value,
                        resource_key=key,
                        mode=CatalogPolicyMode.BLOCK.value,
                        scope=CatalogPolicyScope.GLOBAL.value,
                        domain_id=None,
                        created_by=actor_user_id,
                    )
                )

        if resource_kind == CatalogResourceKind.COMPONENT:
            committed_snapshot = CatalogPolicySnapshot(
                blocked_component_keys=desired,
                blocked_template_keys=current_snapshot.blocked_template_keys,
            )
        else:
            committed_snapshot = CatalogPolicySnapshot(
                blocked_component_keys=current_snapshot.blocked_component_keys,
                blocked_template_keys=desired,
            )

        self._legacy_snapshot = committed_snapshot
        self._legacy_hydrated = True
        return CatalogPolicyUpdate(
            snapshot=committed_snapshot,
            added=frozenset(added),
            removed=frozenset(removed),
        )

    @staticmethod
    async def _read_policy(
        session: AsyncSession,
    ) -> tuple[CatalogPolicySnapshot, list[CatalogPolicyRule]]:
        stmt = select(CatalogPolicyRule).where(
            CatalogPolicyRule.mode == CatalogPolicyMode.BLOCK.value,
            CatalogPolicyRule.scope == CatalogPolicyScope.GLOBAL.value,
            col(CatalogPolicyRule.domain_id).is_(None),
        )
        rows = list((await session.exec(stmt)).all())
        return (
            CatalogPolicySnapshot(
                blocked_component_keys=frozenset(
                    row.resource_key for row in rows if row.resource_kind == CatalogResourceKind.COMPONENT.value
                ),
                blocked_template_keys=frozenset(
                    row.resource_key for row in rows if row.resource_kind == CatalogResourceKind.TEMPLATE.value
                ),
            ),
            rows,
        )
