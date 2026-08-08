"""The bounded per-worker warm graph registry.

Each process-local entry contains a parsed structural ``Graph`` template, a
minimal execution/auth ``FlowRead`` snapshot, and the flow's ``updated_at``
revision. Component constructors are deliberately deferred until a request-local
copy is bound to the caller. Resident entries and in-flight builds share explicit
entry/byte budgets so warming cannot turn tenant data into unbounded worker work.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

import orjson
from lfx.log.logger import logger

if TYPE_CHECKING:
    from lfx.graph.graph.base import Graph

    from langflow.services.database.models.flow.model import FlowRead


def flow_version(updated_at: datetime | None) -> str:
    """Normalize a flow change marker for ordering and exact cache matching."""
    if updated_at is None:
        return ""
    normalized = (
        updated_at.replace(tzinfo=timezone.utc) if updated_at.tzinfo is None else updated_at.astimezone(timezone.utc)
    )
    return normalized.isoformat()


@dataclass(frozen=True, slots=True)
class WarmFlowEntry:
    """One atomically published graph and its isolated flow-resolution metadata."""

    graph: Graph
    version: str
    flow: FlowRead | None
    revision: tuple[object, ...]


class FlowStoreUnavailableError(Exception):
    """The flow store could not be reached while (lazily) warming a flow.

    Distinguishes a transient availability failure (DB down / pool exhausted) from a
    genuine not-found, so the API layer can answer 503 (retryable) instead of 404
    (permanent). Raised by ``warm_one``; translated to an HTTP 503 by the host.
    """


class WarmRegistryCapacityError(Exception):
    """A flow cannot fit within this worker's configured warm-cache bounds."""

    def __init__(self, message: str, *, transient: bool = False) -> None:
        super().__init__(message)
        self.transient = transient


class WarmGraphRegistry:
    """In-memory canonical-flow registry for one worker process."""

    def __init__(
        self,
        *,
        max_entries: int = 128,
        max_flow_bytes: int = 2_000_000,
        max_total_bytes: int = 32_000_000,
        preload_limit: int = 0,
    ) -> None:
        # flow UUID (str) -> immutable entry. One dict per
        # worker process; nothing is shared across processes/machines — the
        # reconcile loop against the shared DB is what keeps them converged.
        self._flows: dict[str, WarmFlowEntry] = {}
        # (owner user UUID, endpoint name) -> canonical flow UUID. Endpoint names
        # are unique only within an owner, never process-global.
        self._endpoint_aliases: dict[tuple[str | None, str], str] = {}
        # Guards writers (add/evict) so concurrent reconcile/warm calls can't leave a
        # half-written dict. Reads (``get``) are plain dict lookups (atomic in CPython)
        # and take no lock, keeping the hot request path fast.
        self._lock = asyncio.Lock()
        # Serialize builds for one flow while still allowing unrelated flows to build
        # concurrently. The cache is rechecked after acquiring this lock, so concurrent
        # misses for the same version collapse to one ``Graph.from_payload`` call.
        self._build_locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        # Latest (version, full metadata revision) whose build failed. This tombstone
        # keeps a delayed observation of older DB state — including the same timestamp
        # with older aliases — from resurrecting the stale graph evicted on failure.
        # A failed revision is not retried every reconcile interval; a later
        # database revision clears the backoff and gets one fresh build attempt.
        self._failed_revisions: OrderedDict[str, tuple[str, tuple[object, ...]]] = OrderedDict()
        # Serialized JSON bytes are a stable accounting unit. Parsed graphs have
        # additional overhead, so the defaults intentionally leave headroom.
        self._max_entries = max_entries
        self._max_flow_bytes = max_flow_bytes
        self._max_total_bytes = max_total_bytes
        # Preload scan window. The tombstone budget is sized against this (the population
        # that can be selected and rejected), NOT against max_entries (an unrelated
        # resident-entry limit) — otherwise un-warmable flows above 2*max_entries rotate
        # their tombstones forever and are re-selected/re-read every reconcile pass.
        self._preload_limit = preload_limit
        self._flow_payload_bytes: dict[str, int] = {}
        self._total_payload_bytes = 0
        # Charge concurrent builds against the same budgets as resident entries.
        self._build_reservations: dict[str, int] = {}
        self._reserved_payload_bytes = 0
        # Bound CPU-heavy snapshot/parse work and the executor queue feeding it.
        self._build_semaphore = asyncio.Semaphore(max(1, min(max_entries, 4)))

    def _build_lock(self, flow_id: str) -> asyncio.Lock:
        """Return the stable per-flow build lock for this registry."""
        # There is no await between lookup and insertion, so this is atomic with respect
        # to other tasks on the event loop (all registry mutation is async/task-local).
        return self._build_locks.setdefault(flow_id, asyncio.Lock())

    def _record_failed_locked(self, flow_id: str, version: str, revision: tuple[object, ...]) -> None:
        """Record a bounded retry tombstone while the registry lock is held."""
        self._failed_revisions[flow_id] = (version, revision)
        self._failed_revisions.move_to_end(flow_id)
        # Budget must cover the flows preload can scan and reject, not the resident-entry
        # limit. Sizing it against max_entries alone let an un-warmable population larger
        # than 2*max_entries evict older tombstones, so those flows dropped out of the
        # backoff and were re-selected as "new" every pass — a full SELECT + deepcopy +
        # serialize per flow per interval, forever, with no cache benefit.
        #
        # Known limitation: if the preloadable set holds MORE un-warmable flows than this
        # budget, the oldest tombstone is still dropped and that flow can be re-attempted on
        # a later pass. The warning below surfaces that so an operator can raise
        # max_flow_bytes or lower preload_limit; a full fix (cheap size pre-check so
        # oversized flows are skipped without a tombstone) is tracked separately.
        max_tombstones = max(self._max_entries * 2, self._preload_limit)
        if len(self._failed_revisions) > max_tombstones:
            logger.warning(
                "warm_registry: tombstone budget (%d) reached; dropping the oldest failure marker. "
                "More flows are un-warmable than the budget can track, so some will be re-attempted "
                "each reconcile pass (extra DB reads for no cache benefit). Raise "
                "LANGFLOW_WARM_REGISTRY_MAX_FLOW_BYTES or lower LANGFLOW_WARM_REGISTRY_PRELOAD_LIMIT.",
                max_tombstones,
            )
        while len(self._failed_revisions) > max_tombstones:
            self._failed_revisions.popitem(last=False)

    @staticmethod
    def _revision(version: str, name: str | None, flow: FlowRead | None) -> tuple[object, ...]:
        """Return the build/resolution revision used for cache rechecks.

        ``updated_at`` remains the ordering marker. Resolution and route-gate fields
        join the equality revision so an add that carries changed metadata cannot be
        skipped merely because it observed the same timestamp representation.
        """
        if flow is None:
            return (version, name)
        return (
            version,
            flow.name,
            flow.user_id,
            flow.workspace_id,
            flow.folder_id,
            flow.endpoint_name,
            flow.webhook,
            flow.access_type,
            flow.mcp_enabled,
            flow.flow_type,
            flow.a2a_enabled,
        )

    @staticmethod
    def _endpoint_key(flow: FlowRead | None) -> tuple[str | None, str] | None:
        if flow is None or not flow.endpoint_name:
            return None
        owner_id = str(flow.user_id) if flow.user_id is not None else None
        return owner_id, flow.endpoint_name

    def _remove_entry_locked(self, flow_id: str) -> None:
        """Remove one entry and its alias while ``self._lock`` is held."""
        entry = self._flows.pop(flow_id, None)
        if entry is None:
            return
        endpoint_key = self._endpoint_key(entry.flow)
        if endpoint_key is not None and self._endpoint_aliases.get(endpoint_key) == flow_id:
            self._endpoint_aliases.pop(endpoint_key, None)
        self._total_payload_bytes -= self._flow_payload_bytes.pop(flow_id, 0)

    @staticmethod
    def _build(flow_id: str, name: str | None, data: dict) -> Graph:
        """Parse ``flow.data`` into a structural ``Graph`` template.

        ``data`` is deepcopied first because ``from_payload`` rewrites the payload
        in place (legacy component migration), and the caller's dict may be the DB
        row's own mapping. Components and extension events are deferred; the
        request-local ``copy_for_run`` binds identity and constructs components.
        """
        from lfx.graph.graph.base import Graph

        return Graph.from_payload(
            deepcopy(data),
            flow_id=flow_id,
            flow_name=name,
            instantiate_components=False,
            emit_extension_events=False,
        )

    @classmethod
    def _prepare_snapshot(
        cls,
        name: str | None,
        data: dict,
        version: str,
        flow: FlowRead | None,
    ) -> tuple[FlowRead | None, tuple[object, ...], str | None, dict, int]:
        """Create and measure the retained execution snapshot off-loop.

        Descriptive and A2A presentation fields are not used by the warm sync
        execution path and may be arbitrarily large, so retain only executable,
        authorization, routing, and revision fields. The measured JSON includes
        every retained field, not just ``flow.data``.
        """
        if flow is None:
            build_data = deepcopy(data)
            stored_flow = None
            build_name = name
            measured: object = build_data
        else:
            from langflow.services.database.models.flow.model import FlowRead

            snapshot_data = deepcopy(flow.data if flow.data is not None else data)
            stored_flow = FlowRead(
                id=flow.id,
                name=flow.name,
                data=snapshot_data,
                updated_at=flow.updated_at,
                user_id=flow.user_id,
                folder_id=flow.folder_id,
                workspace_id=flow.workspace_id,
                endpoint_name=flow.endpoint_name,
                webhook=flow.webhook,
                access_type=flow.access_type,
                mcp_enabled=flow.mcp_enabled,
                flow_type=flow.flow_type,
                a2a_enabled=flow.a2a_enabled,
            )
            build_data = snapshot_data
            build_name = stored_flow.name
            measured = stored_flow.model_dump(mode="json")
        revision = cls._revision(version, name, stored_flow)
        return stored_flow, revision, build_name, build_data, len(orjson.dumps(measured))

    @staticmethod
    async def _await_task_without_abandoning(task):
        """Wait for owned work to finish despite repeated caller cancellation."""
        caller_cancelled = False
        # ``asyncio.wait`` reports completion without propagating the owned
        # task's exception, letting cancellation retain precedence while the
        # resource-owning task is drained.
        completion = asyncio.create_task(asyncio.wait({task}))
        while not completion.done():
            try:
                await asyncio.shield(completion)
            except asyncio.CancelledError:
                # Each cancel request can interrupt a fresh await. Keep shielding
                # until the owned task is actually done; otherwise a native
                # ``to_thread`` worker can outlive its semaphore/byte reservation.
                caller_cancelled = True

        if caller_cancelled:
            # Observe a worker exception so asyncio does not report it as unhandled;
            # cancellation remains the request-visible outcome, as before.
            if not task.cancelled():
                with contextlib.suppress(Exception):
                    task.result()
            raise asyncio.CancelledError
        return task.result()

    @classmethod
    async def _to_thread_without_abandoning(cls, function, *args):
        """Keep the build slot held until thread work ends, even if cancelled."""
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        return await cls._await_task_without_abandoning(task)

    def _capacity_reason_locked(self, flow_id: str, entry_bytes: int) -> tuple[str | None, bool]:
        """Return a capacity reason and whether only competing builds cause it."""
        current_bytes = self._flow_payload_bytes.get(flow_id, 0)
        resident_flow_ids = set(self._flows)
        resident_flow_ids.add(flow_id)
        resident_total = self._total_payload_bytes + entry_bytes - current_bytes
        if len(resident_flow_ids) > self._max_entries:
            return "entry count", False
        if resident_total > self._max_total_bytes:
            return "total entry bytes", False

        # A reservation for a resident flow replaces that resident's bytes; it
        # does not consume an additional entry or a second full byte allocation.
        projected_flow_ids = resident_flow_ids.copy()
        projected_total = resident_total
        for reserved_id, reserved_bytes in self._build_reservations.items():
            if reserved_id == flow_id:
                continue
            projected_flow_ids.add(reserved_id)
            projected_total += reserved_bytes - self._flow_payload_bytes.get(reserved_id, 0)
        if len(projected_flow_ids) > self._max_entries:
            return "entry count", True
        if projected_total > self._max_total_bytes:
            return "total entry bytes", True
        return None, False

    def _reserve_build_locked(self, flow_id: str, entry_bytes: int) -> None:
        self._build_reservations[flow_id] = entry_bytes
        self._reserved_payload_bytes += entry_bytes

    def _release_build_locked(self, flow_id: str) -> None:
        self._reserved_payload_bytes -= self._build_reservations.pop(flow_id, 0)

    async def _release_build_cancellation_safe(self, flow_id: str) -> None:
        """Release a reservation even when the owning request is cancelled."""

        async def _release() -> None:
            async with self._lock:
                self._release_build_locked(flow_id)

        task = asyncio.create_task(_release())
        await self._await_task_without_abandoning(task)

    @contextlib.asynccontextmanager
    async def _build_reservation(self, flow_id: str, entry_bytes: int):
        """Atomically reserve capacity and always release it on context exit."""
        async with self._lock:
            reason, transient = self._capacity_reason_locked(flow_id, entry_bytes)
            if reason is not None:
                msg = f"warm registry {reason} limit reached while adding flow {flow_id}"
                raise WarmRegistryCapacityError(msg, transient=transient)
            self._reserve_build_locked(flow_id, entry_bytes)
        try:
            yield
        finally:
            await self._release_build_cancellation_safe(flow_id)

    def _publish_locked(
        self,
        *,
        flow_id: str,
        version: str,
        graph: Graph,
        stored_flow: FlowRead | None,
        revision: tuple[object, ...],
        entry_bytes: int,
    ) -> None:
        """Publish one completed build while ``self._lock`` is held."""
        current = self._flows.get(flow_id)
        if current is not None and current.version >= version:
            return
        failed = self._failed_revisions.get(flow_id)
        if failed is not None and failed[0] >= version:
            return
        reason, transient = self._capacity_reason_locked(flow_id, entry_bytes)
        if reason is not None:
            msg = f"warm registry {reason} limit reached while adding flow {flow_id}"
            raise WarmRegistryCapacityError(msg, transient=transient)

        current_payload_bytes = self._flow_payload_bytes.get(flow_id, 0)
        old_endpoint_key = self._endpoint_key(current.flow) if current is not None else None
        new_endpoint_key = self._endpoint_key(stored_flow)
        if old_endpoint_key is not None and self._endpoint_aliases.get(old_endpoint_key) == flow_id:
            self._endpoint_aliases.pop(old_endpoint_key, None)
        self._flows[flow_id] = WarmFlowEntry(
            graph=graph,
            version=version,
            flow=stored_flow,
            revision=revision,
        )
        self._total_payload_bytes -= current_payload_bytes
        self._flow_payload_bytes[flow_id] = entry_bytes
        self._total_payload_bytes += entry_bytes
        if new_endpoint_key is not None:
            self._endpoint_aliases[new_endpoint_key] = flow_id
        if failed is not None and (failed[0] < version or (failed[0] == version and failed[1] == revision)):
            self._failed_revisions.pop(flow_id, None)

    async def add(
        self,
        flow_id: str,
        name: str | None,
        data: dict,
        version: str,
        *,
        flow: FlowRead | None = None,
    ) -> None:
        """Build ``data`` into a template and store it under ``flow_id`` at ``version``.

        Duplicate misses are singleflighted per flow. Snapshotting and parsing run
        off-loop behind a small global semaphore, and each in-flight build reserves
        its entry/byte budget before parsing. ``flow`` is complete in runtime callers,
        but only the fields required for sync execution are retained.

        Versions are ISO-formatted ``updated_at`` values, so their lexical order is
        chronological. A cached/tombstoned newer version always wins over a delayed
        older request. If a newer payload fails to build, any resident older template
        is evicted and the failed revision is tombstoned: serving no graph is safer
        than continuing to serve a graph known not to match the database.
        """
        async with self._build_lock(flow_id):
            # Reject known/current revisions before copying or serializing tenant
            # data. Tombstones therefore back off all cache-side CPU work.
            current = self._flows.get(flow_id)
            # Equal timestamps are not orderable. Keep the already-published entry;
            # request-side metadata validation evicts it before a legitimate same-time
            # replacement is rebuilt. This also prevents a delayed old alias/scope
            # snapshot from overwriting the current entry at the same timestamp.
            if current is not None and current.version >= version:
                return
            failed = self._failed_revisions.get(flow_id)
            if failed is not None:
                failed_version, _failed_revision = failed
                if failed_version >= version:
                    return

            async with self._build_semaphore:
                cheap_revision = self._revision(version, name, flow)
                try:
                    (
                        stored_flow,
                        revision,
                        build_name,
                        build_data,
                        entry_bytes,
                    ) = await self._to_thread_without_abandoning(self._prepare_snapshot, name, data, version, flow)
                except Exception:
                    async with self._lock:
                        current = self._flows.get(flow_id)
                        if current is not None and current.version < version:
                            self._remove_entry_locked(flow_id)
                        self._record_failed_locked(flow_id, version, cheap_revision)
                    raise

                if entry_bytes > self._max_flow_bytes:
                    async with self._lock:
                        current = self._flows.get(flow_id)
                        if current is not None and (
                            current.version < version or (current.version == version and current.revision != revision)
                        ):
                            self._remove_entry_locked(flow_id)
                        self._record_failed_locked(flow_id, version, revision)
                    msg = f"flow {flow_id} entry is {entry_bytes} bytes; warm limit is {self._max_flow_bytes} bytes"
                    raise WarmRegistryCapacityError(msg)

                try:
                    async with self._build_reservation(flow_id, entry_bytes):
                        try:
                            graph = await self._to_thread_without_abandoning(
                                self._build, flow_id, build_name, build_data
                            )
                        except asyncio.CancelledError:
                            raise
                        except Exception:
                            async with self._lock:
                                current = self._flows.get(flow_id)
                                if current is not None and (
                                    current.version < version
                                    or (current.version == version and current.revision != revision)
                                ):
                                    self._remove_entry_locked(flow_id)
                                failed = self._failed_revisions.get(flow_id)
                                if failed is None or failed[0] <= version:
                                    self._record_failed_locked(flow_id, version, revision)
                            raise

                        async with self._lock:
                            self._publish_locked(
                                flow_id=flow_id,
                                version=version,
                                graph=graph,
                                stored_flow=stored_flow,
                                revision=revision,
                                entry_bytes=entry_bytes,
                            )
                except WarmRegistryCapacityError as exc:
                    # Capacity rejection is a cache decision. Tombstone every
                    # intrinsically rejected revision so requests and reconcile
                    # do not repeat snapshot/serialization work. Pressure caused
                    # only by another in-flight build is retryable because that
                    # competing build may still fail or be cancelled.
                    async with self._lock:
                        current = self._flows.get(flow_id)
                        if current is not None and (
                            current.version < version or (current.version == version and current.revision != revision)
                        ):
                            self._remove_entry_locked(flow_id)
                        if not exc.transient:
                            self._record_failed_locked(flow_id, version, revision)
                    raise

    def get(self, flow_id: str) -> tuple[Graph, str] | None:
        """Return the shared ``(template, version)`` for ``flow_id`` or ``None``.

        The template is NOT copied here — the caller deepcopies before running.
        """
        entry = self._flows.get(flow_id)
        return (entry.graph, entry.version) if entry is not None else None

    def get_flow(self, flow_id: str) -> FlowRead | None:
        """Return an isolated ``FlowRead`` snapshot for a canonical UUID."""
        resolved = self.get_flow_with_revision(flow_id)
        return resolved[0] if resolved is not None else None

    def get_flow_with_revision(self, flow_id: str) -> tuple[FlowRead, tuple[object, ...]] | None:
        """Return one entry's isolated flow snapshot and matching revision.

        Reading both values from the same immutable entry is important for shared-flow
        resolution, which can await authorization-service checks before validating the
        revision. Separate lookups could otherwise pair an old snapshot with a newly
        reconciled revision.
        """
        entry = self._flows.get(str(flow_id))
        if entry is None or entry.flow is None:
            return None
        return entry.flow.model_copy(deep=True), entry.revision

    def get_flow_by_endpoint(self, user_id: object | None, endpoint_name: str) -> FlowRead | None:
        """Resolve an endpoint name only within the caller owner's namespace."""
        resolved = self.get_flow_by_endpoint_with_revision(user_id, endpoint_name)
        return resolved[0] if resolved is not None else None

    def get_flow_by_endpoint_with_revision(
        self,
        user_id: object | None,
        endpoint_name: str,
    ) -> tuple[FlowRead, tuple[object, ...]] | None:
        """Resolve an owner-qualified alias and return one coherent entry snapshot."""
        owner_id = str(user_id) if user_id is not None else None
        flow_id = self._endpoint_aliases.get((owner_id, endpoint_name))
        return self.get_flow_with_revision(flow_id) if flow_id is not None else None

    def revision_of(self, flow_id: str) -> tuple[object, ...] | None:
        """Return the immutable resolution/build revision for metadata validation."""
        entry = self._flows.get(str(flow_id))
        return entry.revision if entry is not None else None

    def get_entry_revision(self, flow_id: str) -> tuple[object, ...] | None:
        """Backward-compatible descriptive alias for :meth:`revision_of`."""
        return self.revision_of(flow_id)

    def version_of(self, flow_id: str) -> str | None:
        """Return just the cached version for ``flow_id`` (or ``None``) without the graph."""
        hit = self._flows.get(flow_id)
        return hit.version if hit is not None else None

    def rejects_version(self, flow_id: str, version: str) -> bool:
        """Return whether a failed/newer revision should stay on the cold path."""
        failed = self._failed_revisions.get(flow_id)
        return failed is not None and failed[0] >= version

    def rejection_count(self) -> int:
        """Return the bounded number of revisions reconcile may need to scan past."""
        return len(self._failed_revisions)

    async def reject_revision(
        self,
        flow_id: str,
        version: str,
        *,
        name: str | None = None,
        flow: FlowRead | None = None,
    ) -> None:
        """Keep a known non-runnable revision cold and evict any older template."""
        revision = self._revision(version, name, flow)
        async with self._build_lock(flow_id), self._lock:
            current = self._flows.get(flow_id)
            if current is not None and current.version > version:
                return
            if current is not None:
                self._remove_entry_locked(flow_id)
            failed = self._failed_revisions.get(flow_id)
            if failed is None or failed[0] <= version:
                self._record_failed_locked(flow_id, version, revision)

    async def evict(self, flow_id: str) -> None:
        """Drop ``flow_id`` from the cache (no-op if already gone)."""
        # Wait for an in-flight build of this flow before evicting it. Otherwise a
        # delete/empty-data reconcile could pop the old entry and have the delayed
        # build immediately resurrect it.
        async with self._build_lock(flow_id), self._lock:
            self._remove_entry_locked(flow_id)

    async def evict_if_revision(self, flow_id: str, revision: tuple[object, ...]) -> bool:
        """Evict only if ``flow_id`` still has the caller-observed revision.

        Request-side metadata validation can race a reconcile rebuild. Comparing under
        the per-flow writer lock prevents a stale validator from deleting the newer
        graph/snapshot/alias that won that race.
        """
        async with self._build_lock(flow_id), self._lock:
            current = self._flows.get(flow_id)
            if current is None or current.revision != revision:
                return False
            self._remove_entry_locked(flow_id)
            return True

    def active_ids(self) -> set[str]:
        """Snapshot of the currently cached flow ids (reconcile diffs this vs the DB manifest)."""
        return set(self._flows)

    def remaining_entries(self) -> int:
        """Return entry slots not occupied or reserved by an in-flight build."""
        reserved_new_ids = set(self._build_reservations).difference(self._flows)
        return max(0, self._max_entries - len(self._flows) - len(reserved_new_ids))

    def __len__(self) -> int:
        return len(self._flows)


_warm_registry: WarmGraphRegistry | None = None


def get_warm_registry() -> WarmGraphRegistry:
    """Return the process-local warm registry singleton, creating it on first use."""
    global _warm_registry  # noqa: PLW0603
    if _warm_registry is None:
        from langflow.services.deps import get_settings_service

        settings = get_settings_service().settings
        max_entries = settings.warm_registry_max_entries
        preload_limit = settings.warm_registry_preload_limit
        # A preload_limit above max_entries is a misconfiguration: the cache can hold at
        # most max_entries resident templates, so preload effectively fills no more than
        # that (preload_slots is min()'d against remaining capacity). Warn — don't clamp —
        # so the operator can fix the config; the value is still passed through so the
        # tombstone budget can size against the operator's stated preload intent.
        if preload_limit > max_entries:
            logger.warning(
                "warm_registry: LANGFLOW_WARM_REGISTRY_PRELOAD_LIMIT (%d) exceeds "
                "LANGFLOW_WARM_REGISTRY_MAX_ENTRIES (%d); at most %d flows can stay resident, "
                "so preload cannot warm more than that. Set preload_limit <= max_entries.",
                preload_limit,
                max_entries,
                max_entries,
            )
        _warm_registry = WarmGraphRegistry(
            max_entries=max_entries,
            max_flow_bytes=settings.warm_registry_max_flow_bytes,
            max_total_bytes=settings.warm_registry_max_total_bytes,
            preload_limit=preload_limit,
        )
        logger.debug("warm_registry: initialized process-local registry")
    return _warm_registry
