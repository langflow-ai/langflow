"""Reconcile the warm registry against the shared ``flow`` table (no Redis).

The execution DB is the single source of truth and the only coordination channel:
each machine independently diffs its registry against it. There is no cross-machine
messaging: creates add rows, edits advance revisions, and deletes remove rows. Every
machine's next reconcile pass converges.

Rules:
- change-marker per flow = ``updated_at`` isoformat; a differing version rebuilds.
- registry key absent from the manifest -> evict (covers hard-delete).
- **fail-safe:** only reconcile when the manifest query SUCCEEDS. A DB error must
  never mass-evict the registry, so on failure we keep the current state.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from filelock import FileLock
from filelock import Timeout as FileLockTimeout
from lfx.log.logger import logger
from sqlmodel import col, select

from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.deps import get_settings_service, session_scope
from langflow.services.warm_registry.service import (
    FlowStoreUnavailableError,
    WarmRegistryCapacityError,
    flow_version,
    get_warm_registry,
)

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph
    from sqlmodel.ext.asyncio.session import AsyncSession


_WARM_ALL_LOCK_PATH = Path(tempfile.gettempdir()) / "langflow_warm_registry.lock"
_WARM_ALL_LOCK_POLL_SECONDS = 0.5


async def _fetch_flow(session: AsyncSession, flow_id: str, *, user_id: object | None = None) -> Flow | None:
    """Fetch by canonical UUID, or by endpoint name within one owner namespace."""
    try:
        uid: UUID | None = UUID(flow_id)
    except ValueError:
        uid = None
    if uid is not None:
        flow = (await session.exec(select(Flow).where(Flow.id == uid))).first()
        if flow is not None:
            return flow
    if user_id is None:
        return None
    try:
        owner_id = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
    except ValueError:
        return None
    return (await session.exec(select(Flow).where(Flow.endpoint_name == flow_id, Flow.user_id == owner_id))).first()


async def warm_one(flow_id: str, *, user_id: object | None = None) -> tuple[Graph, str] | None:
    """Lazy-warm a single flow into the registry on a cache miss.

    Returns the ``(template, version)`` entry, or ``None`` when the flow genuinely
    does not exist / has no data (caller maps that to a 404). A DB *availability*
    failure instead raises :class:`FlowStoreUnavailableError` so the caller can answer
    503 (retryable) rather than a permanent-looking 404 — important on a cold worker
    during pool exhaustion. Registered under the canonical UUID. Endpoint-name lookup
    requires ``user_id`` and is owner-scoped; share-aware cross-owner resolution must
    use the authorization-aware DB path instead of this local cache.
    """
    reg = get_warm_registry()
    try:
        async with session_scope() as session:
            flow = await _fetch_flow(session, flow_id, user_id=user_id)
            snapshot = FlowRead.model_validate(flow, from_attributes=True) if flow is not None else None
    except Exception as exc:
        # A transient store failure must be distinguishable from not-found: re-raise
        # as a typed availability error (host -> 503) instead of collapsing to None.
        logger.exception("warm_registry: warm_one query failed for %s", flow_id)
        raise FlowStoreUnavailableError(flow_id) from exc
    if snapshot is None or not snapshot.data:
        return None
    if snapshot.updated_at is None:
        # A nullable legacy timestamp cannot provide a monotonic cache revision.
        # Keep this flow on the cold path until a real writer advances it.
        return None
    canonical = str(snapshot.id)
    try:
        await reg.add(
            canonical,
            snapshot.name,
            snapshot.data,
            flow_version(snapshot.updated_at),
            flow=snapshot,
        )
    except WarmRegistryCapacityError:
        # Capacity is a cache decision, never an execution error. The caller
        # continues through its established cold build path.
        logger.info("warm_registry: flow %s is outside configured cache bounds", canonical)
        return None
    return reg.get(canonical)


async def _warm_all_unlocked() -> None:
    """Build this worker's registry while the machine-local startup lock is held."""
    reg = get_warm_registry()
    preload_limit = get_settings_service().settings.warm_registry_preload_limit
    limit = min(preload_limit, reg.remaining_entries())
    if limit <= 0:
        logger.info("warm_registry: eager preload disabled; flows will warm lazily")
        return

    async with session_scope() as session:
        flow_ids = (
            await session.exec(
                select(Flow.id)
                .where(col(Flow.updated_at).is_not(None))
                .order_by(col(Flow.updated_at).desc())
                .limit(limit)
            )
        ).all()
    warmed = 0
    # Fetch one full payload at a time. This keeps automatic preload bounded by
    # both ``preload_limit`` and the registry byte limits instead of materializing
    # every tenant row in one result set.
    for flow_id in flow_ids:
        try:
            async with session_scope() as session:
                row = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
            if row is None:
                continue
            flow = FlowRead.model_validate(row, from_attributes=True)
            if not flow.data or flow.updated_at is None:
                continue
            # Deliberately sequential: Graph.from_payload is CPU-heavy and an
            # unbounded gather here would merely move the startup spike in-process.
            await reg.add(
                str(flow.id),
                flow.name,
                flow.data,
                flow_version(flow.updated_at),
                flow=flow,
            )
            warmed += 1
        except WarmRegistryCapacityError:
            # Capacity is a cache decision, never an execution error (see class docstring).
            # Log at INFO without a stack trace — matches the resolver-side handling above —
            # so an operator holding oversized flows doesn't get a traceback per flow.
            logger.info("warm_registry: flow %s is outside configured cache bounds during warm_all", flow_id)
        except Exception:  # noqa: BLE001 — one bad flow must not abort warming the rest
            logger.exception("warm_registry: failed to build flow %s during warm_all", flow_id)
    logger.info("warm_registry: warmed %d flow(s) at startup", warmed)


async def warm_all() -> None:
    """Preload a configured bounded flow set, serializing work across local workers.

    The default preload limit is zero, so shared deployments warm lazily after an
    authorized request. Dedicated execution workers may opt into bounded preload.
    Registries are process-local; the machine-local lock prevents workers from
    preloading simultaneously. Lock acquisition runs in a thread so a waiting worker
    keeps its event loop responsive; release is guaranteed on every error path.
    """
    # ``to_thread`` may acquire and release on different executor threads, so the
    # lock context must be shared rather than FileLock's thread-local default.
    lock = FileLock(_WARM_ALL_LOCK_PATH, thread_local=False)
    logger.info("warm_registry: waiting for machine-local startup warm lock")
    while True:
        try:
            # A finite poll both avoids FileLock's same-process deadlock guard in
            # tests and gives cancellation regular checkpoints during a long warm.
            await asyncio.to_thread(lock.acquire, timeout=_WARM_ALL_LOCK_POLL_SECONDS)
            break
        except FileLockTimeout:
            continue
    try:
        await _warm_all_unlocked()
    finally:
        await asyncio.to_thread(lock.release)


async def reconcile_once() -> None:
    """One reconcile pass: add new/changed, evict deleted. Fail-safe on DB error."""
    reg = get_warm_registry()
    active_ids = reg.active_ids()
    active_uuids: list[UUID] = []
    for sid in active_ids:
        try:
            active_uuids.append(UUID(sid))
        except ValueError:
            # Registry runtime keys are canonical UUIDs. A malformed legacy/test
            # key has no matching DB row and is treated as deleted below.
            continue

    preload_limit = get_settings_service().settings.warm_registry_preload_limit
    preload_slots = max(0, min(reg.remaining_entries(), preload_limit - len(reg)))

    # Query only resident entries (bounded by max_entries) plus a bounded newest
    # set when explicit preload has spare slots. A tenant-wide manifest every 20s
    # would make shared-cluster DB work grow without bound.
    try:
        async with session_scope() as session:
            manifest = []
            if active_uuids:
                active_stmt = select(Flow.id, Flow.updated_at).where(col(Flow.id).in_(active_uuids))
                manifest.extend((await session.exec(active_stmt)).all())
            if preload_slots:
                # Failed revisions are filtered after their timestamp is read so
                # a later revision of the same flow remains eligible. Overfetch by
                # the bounded tombstone count to keep rejected newest rows from
                # permanently starving older valid candidates.
                preload_scan_limit = preload_slots + reg.rejection_count()
                preload_stmt = (
                    select(Flow.id, Flow.updated_at)
                    .where(col(Flow.updated_at).is_not(None))
                    .order_by(col(Flow.updated_at).desc())
                    .limit(preload_scan_limit)
                )
                if active_uuids:
                    preload_stmt = preload_stmt.where(col(Flow.id).not_in(active_uuids))
                manifest.extend((await session.exec(preload_stmt)).all())
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
    unversioned_ids: list[str] = []
    for flow_id, updated_at in manifest:
        sid = str(flow_id)
        manifest_ids.add(sid)
        cached = reg.version_of(sid)
        if updated_at is None:
            if cached is not None:
                unversioned_ids.append(sid)
            continue
        version = flow_version(updated_at)
        if cached is None:
            # A failed/oversized revision is already known to be unsuitable.
            # Skip it before selecting the full ``data`` row so the tombstone
            # backs off database transfer as well as graph parsing.
            if reg.rejects_version(sid, version):
                continue
            if len(new_ids) < preload_slots:
                new_ids.append(flow_id)
        elif cached != version:
            changed_ids.append(flow_id)

    # Deletion propagation: cached minus live = upstream-deleted -> evict.
    evicted = active_ids - manifest_ids
    for sid in evicted:
        await reg.evict(sid)
        logger.info("warm_registry: evicted deleted flow %s", sid)
    for sid in unversioned_ids:
        await reg.evict(sid)
        logger.info("warm_registry: evicted unversioned flow %s", sid)

    # Fetch ``data`` only for new+changed flows and (re)build them.
    to_build = new_ids + changed_ids
    if to_build:
        for flow_id in to_build:
            try:
                async with session_scope() as session:
                    row = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
                if row is None:
                    continue
                flow = FlowRead.model_validate(row, from_attributes=True)
            except Exception:  # noqa: BLE001
                logger.exception("warm_registry: change fetch failed for %s; will retry", flow_id)
                continue
            sid = str(flow.id)
            if not flow.data or flow.updated_at is None:
                # A (re)deployed flow whose executable data is now empty is not runnable.
                # Tombstone a versioned empty row as well as evicting an older
                # template. Otherwise a newest empty flow consumes the same bounded
                # preload slot on every pass and starves older runnable candidates.
                if flow.updated_at is None:
                    await reg.evict(sid)
                else:
                    await reg.reject_revision(
                        sid,
                        flow_version(flow.updated_at),
                        name=flow.name,
                        flow=flow,
                    )
                continue
            try:
                await reg.add(
                    sid,
                    flow.name,
                    flow.data,
                    flow_version(flow.updated_at),
                    flow=flow,
                )
                verb = "added new" if flow.id in new_ids else "rebuilt changed"
                logger.info("warm_registry: %s flow %s (%r)", verb, flow.id, flow.name)
            except WarmRegistryCapacityError:
                # Capacity is a cache decision, never an execution error (see class docstring).
                # INFO, no stack trace — matches the resolver-side handling at the top of this
                # module — so an oversized flow doesn't emit a traceback every reconcile pass.
                logger.info("warm_registry: flow %s is outside configured cache bounds", flow.id)
            except Exception:  # noqa: BLE001
                logger.exception("warm_registry: rebuild failed for %s", flow.id)

    if new_ids or changed_ids or evicted or unversioned_ids:
        logger.info(
            "warm_registry: reconcile pass — +%d new, ~%d changed, -%d deleted (registry now %d)",
            len(new_ids),
            len(changed_ids),
            len(evicted) + len(unversioned_ids),
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
