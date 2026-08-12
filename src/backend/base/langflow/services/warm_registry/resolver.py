"""Metadata-validated flow resolution for warm workflow execution.

The registry keeps a complete :class:`FlowRead` snapshot next to each graph so
an execution request does not need to select the (potentially large) ``data``
column again.  Before returning that snapshot, this module reads only the
small set of metadata columns that affect ownership, authorization, routing,
or the registry version.  A changed or deleted row is evicted with a
compare-and-evict operation and the caller falls back to the normal full-flow
resolver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

from sqlmodel import select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import (
    get_authorization_service,
    get_settings_service,
    session_scope,
)
from langflow.services.warm_registry.service import flow_version, get_warm_registry

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from langflow.services.database.models.flow.model import FlowRead


def _warm_registry_active() -> bool:
    """Return whether warm execution is enabled for this process."""
    return bool(getattr(get_settings_service().settings, "warm_registry_enabled", False))


def _metadata_revision(row: Sequence[object]) -> tuple[object, ...]:
    """Convert the narrow metadata row to the registry revision shape."""
    values: tuple[object, ...] = tuple(row)
    return (flow_version(cast("datetime | None", values[0])), *values[1:])


async def resolve_warm_flow_for_execution(
    identifier: str,
    user_id: UUID | str | None,
    *,
    widen_for_shares: bool = False,
) -> FlowRead | None:
    """Return a current, isolated cached ``FlowRead`` or ``None`` to fetch cold.

    Endpoint aliases are always resolved in the caller owner's namespace.
    Cross-owner widening is allowed only for canonical UUIDs and only when the
    active authorization service explicitly enables share-aware fetching.
    This mirrors ``get_flow_by_id_or_endpoint_name`` without making ambiguous
    endpoint names process-global.

    The validation query intentionally excludes ``Flow.data``.  A cache miss,
    a stale/deleted snapshot, or an identifier that cannot safely use the
    cache returns ``None``; the API layer then invokes its existing full-row
    helper and retains the established 404/503 error mapping.
    """
    if not _warm_registry_active() or user_id is None:
        return None

    try:
        caller_id = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
    except (TypeError, ValueError, AttributeError):
        return None

    registry = get_warm_registry()
    try:
        flow_key = str(UUID(str(identifier)))
    except (TypeError, ValueError, AttributeError):
        # Endpoint names are unique per owner only.  Never search another
        # owner's aliases, even when share-aware fetching is enabled.
        resolved = registry.get_flow_by_endpoint_with_revision(caller_id, str(identifier))
        owner_scoped = True
        if resolved is not None and resolved[0].user_id != caller_id:
            return None
    else:
        resolved = registry.get_flow_with_revision(flow_key)
        if resolved is None:
            return None
        snapshot = resolved[0]
        owner_scoped = snapshot.user_id == caller_id
        if not owner_scoped:
            if not widen_for_shares:
                return None
            authz = get_authorization_service()
            if not await authz.is_enabled() or not await authz.supports_cross_user_fetch():
                return None

    if resolved is None:
        return None
    snapshot, observed_revision = resolved

    flow_id = str(snapshot.id)

    # Select only the fields that can invalidate the cached resolution and
    # execution-route decision.  In particular, Flow.data is not selected.
    stmt = select(
        Flow.updated_at,
        Flow.name,
        Flow.user_id,
        Flow.workspace_id,
        Flow.folder_id,
        Flow.endpoint_name,
        Flow.webhook,
        Flow.access_type,
        Flow.mcp_enabled,
        Flow.flow_type,
        Flow.a2a_enabled,
    ).where(Flow.id == snapshot.id)
    if owner_scoped:
        stmt = stmt.where(Flow.user_id == caller_id)

    async with session_scope() as session:
        row = (await session.exec(stmt)).first()

    if row is None or _metadata_revision(row) != observed_revision:
        await registry.evict_if_revision(flow_id, observed_revision)
        return None

    # Reconcile may have published a newer snapshot while the metadata query
    # awaited the DB.  Never return the older object in that race; the caller's
    # cold fallback is safe and the next request can use the new revision.
    if registry.get_entry_revision(flow_id) != observed_revision:
        return None

    # get_flow_with_revision already returned an isolated deep copy.
    return snapshot
