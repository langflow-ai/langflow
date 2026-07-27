"""Reconcile the warm registry against the shared ``flow`` table (no Redis).

The execution DB is the single source of truth and the only coordination channel:
each machine independently diffs its registry against it. There is no cross-machine
messaging — a deploy adds a row, a delete removes it, and every machine's next
reconcile pass converges.

Rules:
- change-marker per flow = ``updated_at`` isoformat; a differing version rebuilds.
- registry key absent from the manifest -> evict (covers hard-delete).
- **fail-safe:** only reconcile when the manifest query SUCCEEDS. A DB error must
  never mass-evict the registry, so on failure we keep the current state.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from uuid import UUID

from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.warm_registry.service import get_warm_registry

if TYPE_CHECKING:
    from datetime import datetime

    from lfx.graph.graph.base import Graph
    from sqlmodel.ext.asyncio.session import AsyncSession


def _version(updated_at: datetime | None) -> str:
    return updated_at.isoformat() if updated_at is not None else ""


async def _fetch_flow(session: AsyncSession, flow_id: str) -> Flow | None:
    """Fetch a single flow by UUID id, falling back to endpoint name."""
    try:
        uid: UUID | None = UUID(flow_id)
    except ValueError:
        uid = None
    if uid is not None:
        flow = (await session.exec(select(Flow).where(Flow.id == uid))).first()
        if flow is not None:
            return flow
    return (await session.exec(select(Flow).where(Flow.endpoint_name == flow_id))).first()


async def warm_one(flow_id: str) -> tuple[Graph, str] | None:
    """Lazy-warm a single flow into the registry on a cache miss.

    Returns the ``(template, version)`` entry, or ``None`` when the flow does not
    exist / has no data (caller maps that to a 404). Registered under the canonical
    UUID; callers that looked up by endpoint name should use the returned entry
    directly rather than re-reading the registry by the requested id.
    """
    reg = get_warm_registry()
    try:
        async with session_scope() as session:
            flow = await _fetch_flow(session, flow_id)
    except Exception:  # noqa: BLE001 — a DB blip must not surface as a 500 here
        logger.exception("warm_registry: warm_one query failed for %s", flow_id)
        return None
    if flow is None or not flow.data:
        return None
    canonical = str(flow.id)
    await reg.add(canonical, flow.name, flow.data, _version(flow.updated_at))
    return reg.get(canonical)


async def warm_all() -> None:
    """Eager-load every flow into the registry at startup (hot before serving)."""
    reg = get_warm_registry()
    async with session_scope() as session:
        flows = (await session.exec(select(Flow))).all()
    warmed = 0
    for flow in flows:
        if not flow.data:
            continue
        try:
            await reg.add(str(flow.id), flow.name, flow.data, _version(flow.updated_at))
            warmed += 1
        except Exception:  # noqa: BLE001 — one bad flow must not abort warming the rest
            logger.exception("warm_registry: failed to build flow %s during warm_all", flow.id)
    logger.info("warm_registry: warmed %d flow(s) at startup", warmed)


async def reconcile_once() -> None:
    """One reconcile pass: add new/changed, evict deleted. Fail-safe on DB error."""
    reg = get_warm_registry()
    # Pull a cheap manifest (id, updated_at for every flow) — no ``data`` blobs.
    try:
        async with session_scope() as session:
            manifest = (await session.exec(select(Flow.id, Flow.updated_at))).all()
    except Exception:  # noqa: BLE001
        # Critical safety rail: never run the evict step on a failed manifest query,
        # or an empty/partial result would wipe the whole registry. Keep current
        # state and let the next pass retry.
        logger.exception("warm_registry: manifest query failed; keeping current registry")
        return

    # Diff the manifest against the cache: NEW (absent), CHANGED (version differs).
    manifest_ids: set[str] = set()
    new_ids: list[UUID] = []
    changed_ids: list[UUID] = []
    for flow_id, updated_at in manifest:
        sid = str(flow_id)
        manifest_ids.add(sid)
        cached = reg.version_of(sid)
        if cached is None:
            new_ids.append(flow_id)
        elif cached != _version(updated_at):
            changed_ids.append(flow_id)

    # Deletion propagation: cached minus live = upstream-deleted -> evict.
    evicted = reg.active_ids() - manifest_ids
    for sid in evicted:
        await reg.evict(sid)
        logger.info("warm_registry: evicted deleted flow %s", sid)

    # Fetch ``data`` only for new+changed flows and (re)build them.
    to_build = new_ids + changed_ids
    if to_build:
        try:
            async with session_scope() as session:
                rows = (await session.exec(select(Flow).where(col(Flow.id).in_(to_build)))).all()
        except Exception:  # noqa: BLE001
            logger.exception("warm_registry: change fetch failed; will retry next pass")
            return
        for flow in rows:
            if not flow.data:
                continue
            try:
                await reg.add(str(flow.id), flow.name, flow.data, _version(flow.updated_at))
                verb = "added new" if flow.id in new_ids else "rebuilt changed"
                logger.info("warm_registry: %s flow %s (%r)", verb, flow.id, flow.name)
            except Exception:  # noqa: BLE001
                logger.exception("warm_registry: rebuild failed for %s", flow.id)

    if new_ids or changed_ids or evicted:
        logger.info(
            "warm_registry: reconcile pass — +%d new, ~%d changed, -%d deleted (registry now %d)",
            len(new_ids),
            len(changed_ids),
            len(evicted),
            len(reg),
        )
    else:
        logger.debug("warm_registry: reconcile pass — no changes (registry %d)", len(reg))


async def reconcile_loop(interval: float | None = None) -> None:
    """Run :func:`reconcile_once` forever every ``interval`` seconds.

    ``interval`` defaults to ``settings.warm_reconcile_interval``
    (env ``LANGFLOW_WARM_RECONCILE_INTERVAL``, 20s).
    """
    if interval is None:
        interval = get_settings_service().settings.warm_reconcile_interval
    logger.info("warm_registry: reconcile loop started (interval=%ss)", interval)
    while True:
        # Sleep before the first pass: warm_all() already filled the registry at startup.
        await asyncio.sleep(interval)
        try:
            await reconcile_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — the loop must survive a bad pass
            logger.exception("warm_registry: reconcile pass errored; continuing")
