"""Database-backed catalog-policy service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lfx.services.catalog_policy import BaseCatalogPolicyService, CatalogPolicySnapshot, CatalogPolicyUpdate
from lfx.services.deps import session_scope, session_scope_readonly
from lfx.services.schema import ServiceType
from sqlmodel import col, select

from langflow.services.database.models.catalog_policy import (
    CatalogPolicyMode,
    CatalogPolicyRule,
    CatalogPolicyScope,
    CatalogResourceKind,
)

if TYPE_CHECKING:
    from collections.abc import Collection
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from langflow.services.database.service import DatabaseService


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
    """Durable global catalog policy backed by an immutable local snapshot.

    Each Langflow process owns its snapshot. Startup hydration and successful
    writes update that process; coordinating snapshots across multiple workers
    requires an external invalidation mechanism and is outside this service.
    Before hydration, the empty snapshot deliberately allows every resource.
    """

    def __init__(self, database_service: DatabaseService) -> None:
        super().__init__()
        self.database_service = database_service
        self._snapshot = CatalogPolicySnapshot()
        self._hydrated = False
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
        return self._snapshot

    @property
    def hydrated(self) -> bool:
        """Return whether durable policy has been loaded successfully."""
        return self._hydrated

    async def hydrate(self) -> CatalogPolicySnapshot:
        """Load global block rules and atomically publish a complete snapshot.

        A failed load leaves the previous snapshot untouched. Callers may log
        the failure and continue with its fail-open decision surface.
        """
        async with self._write_lock:
            async with session_scope_readonly() as session:
                snapshot, _rows = await self._read_policy(session)
            self._snapshot = snapshot
            self._hydrated = True
            return snapshot

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

            # A single reference swap publishes both frozensets together, and
            # occurs only after the durable transaction has committed.
            self._snapshot = committed_snapshot
            self._hydrated = True
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
