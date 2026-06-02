"""FastAPI application factory for serving **multiple** LFX graphs at once.

This module is used by the CLI *serve* command when the provided path is a
folder containing multiple ``*.json`` flow files.  Each flow is exposed under
its own router prefix::

    /flows/{flow_id}/run  - POST - execute the flow
    /flows/{flow_id}/info - GET  - metadata

A global ``/flows`` endpoint lists all available flows and returns a JSON array
of metadata objects, allowing API consumers to discover IDs without guessing.

Authentication behaves exactly like the single-flow serving: all execution
endpoints require the ``x-api-key`` header (or query parameter) validated by
:func:`lfx.cli.commands.verify_api_key`.
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from copy import deepcopy
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Response, Security
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import BaseModel, ConfigDict, Field, field_validator

from lfx.cli.common import (
    execute_graph_with_capture,
    extract_result_data,
    get_api_key,
)
from lfx.cli.runtime_variables import apply_global_vars_to_graph
from lfx.load import load_flow_from_json
from lfx.log.logger import logger
from lfx.utils.flow_validation import validate_flow_for_current_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from lfx.cli.flow_store import FlowStore
    from lfx.graph import Graph

# Security - use the same pattern as Langflow main API
API_KEY_NAME = "x-api-key"

# Constants for app factory env vars (used by uvicorn worker processes)
_SERVE_ENV_PREFIX = "LFX_SERVE_"
_SERVE_FLOW_DIR_ENV = f"{_SERVE_ENV_PREFIX}FLOW_DIR"
_SERVE_NO_ENV_FALLBACK_ENV = f"{_SERVE_ENV_PREFIX}NO_ENV_FALLBACK"
_SERVE_STARTUP_PATHS_ENV = f"{_SERVE_ENV_PREFIX}STARTUP_PATHS"
api_key_query = APIKeyQuery(name=API_KEY_NAME, scheme_name="API key query", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, scheme_name="API key header", auto_error=False)


def verify_api_key(
    query_param: Annotated[str | None, Security(api_key_query)],
    header_param: Annotated[str | None, Security(api_key_header)],
) -> str:
    """Verify API key from query parameter or header."""
    provided_key = query_param or header_param
    if not provided_key:
        raise HTTPException(status_code=401, detail="API key required")

    try:
        expected_key = get_api_key()
        if provided_key != expected_key:
            raise HTTPException(status_code=401, detail="Invalid API key")
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    return provided_key


class FlowAlreadyRegisteredError(ValueError):
    """Raised by FlowRegistry.add() when a flow ID is already registered and overwrite=False."""


class FlowMeta(BaseModel):
    """Metadata returned by the ``/flows`` endpoint."""

    id: str = Field(..., description="Flow identifier (UUID)")
    relative_path: str = Field(..., description="Path of the flow JSON relative to the deployed folder")
    title: str = Field(..., description="Human-readable title (filename stem if unknown)")
    description: str | None = Field(None, description="Optional flow description")


class RunRequest(BaseModel):
    """Request model for executing a LFX flow."""

    input_value: str = Field(..., description="Input value passed to the flow")
    session_id: str | None = Field(default=None, description="Session ID for maintaining conversation state")
    global_vars: dict[str, str] | None = Field(
        default=None,
        description="Per-request variables injected into graph.context['request_variables'] on the deepcopy. "
        "Use this to supply credentials or other scoped values without touching os.environ.",
    )


class StreamRequest(BaseModel):
    """Request model for streaming execution of a LFX flow."""

    input_value: str = Field(..., description="Input value passed to the flow")
    input_type: str = Field(default="chat", description="Type of input (chat, text)")
    output_type: str = Field(default="chat", description="Type of output (chat, text, debug, any)")
    output_component: str | None = Field(default=None, description="Specific output component to stream from")
    session_id: str | None = Field(default=None, description="Session ID for maintaining conversation state")
    tweaks: dict[str, Any] | None = Field(default=None, description="Optional tweaks to modify flow behavior")
    global_vars: dict[str, str] | None = Field(
        default=None,
        description="Per-request variables injected into graph.context['request_variables'] on the deepcopy. "
        "Use this to supply credentials or other scoped values without touching os.environ.",
    )


class RunResponse(BaseModel):
    """Response model mirroring the single-flow server."""

    result: str = Field(..., description="The output result from the flow execution")
    success: bool = Field(..., description="Whether execution was successful")
    logs: str = Field("", description="Captured logs from execution")
    type: str = Field("message", description="Type of result")
    component: str = Field("", description="Component that generated the result")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")
    success: bool = Field(default=False, description="Always false for errors")


class FlowRegistry:
    """Mutable in-process registry of loaded flows.

    The in-memory dict is a per-worker cache. Backing persistence is provided
    by a :class:`~lfx.cli.flow_store.FlowStore`; the default ``NullFlowStore``
    keeps everything in memory only.

    - ``NullFlowStore`` (default): single-worker, no disk I/O.
    - ``FilesystemFlowStore("/tmp/lfx-flows")``: all uvicorn workers in the
      same pod share flows via ``/tmp``.
    - ``FilesystemFlowStore("/mnt/lfx-flows")``: same code, cross-pod if the
      path is a PVC mount.

    **Per-request stale check (FilesystemFlowStore only)**

    Every call to :meth:`get` for a store-backed flow does one
    ``FlowStore.read()`` to verify the file still exists.  This is how DELETE
    propagates across workers: the deleting worker removes the file; the next
    inbound request on any other worker calls ``get()``, finds ``None``, evicts
    the cached entry, and returns 404.

    On a local SSD this overhead is a single ``stat``-equivalent and is
    negligible.  On a **network volume** (NFS, CIFS, or a Kubernetes PVC backed
    by a networked storage class) each read call crosses the network, which can
    add measurable latency per request.  If you are running on such a mount and
    latency matters, prefer ``/tmp/lfx-flows`` (local tmpfs) for single-pod
    worker sharing and accept that cross-pod DELETE propagation is eventual
    (next request per pod) rather than immediate.

    When ``no_env_fallback=True``, every graph registered via ``add()`` has
    ``graph.context['no_env_fallback']`` set to ``True`` at registration time,
    preventing credential resolution from falling back to ``os.environ``.
    """

    # TTL for the cached result of store.list_ids() (a filesystem glob).
    # Avoids one glob per /health call while still reflecting changes within ~1 s.
    # Mutations (add / remove) invalidate the cache immediately.
    _STORE_IDS_TTL: float = 1.0

    def __init__(self, *, no_env_fallback: bool = False, store: FlowStore | None = None) -> None:
        from lfx.cli.flow_store import NullFlowStore

        # Key invariant: a flow may be stored under TWO keys simultaneously —
        # its JSON UUID *and* a filename stem (e.g. "prompt_one") when the
        # pre-placed file's stem differs from the UUID in the JSON.  Both keys
        # map to the *same* (graph, meta) tuple.  All deduplication logic
        # (list_metas, __len__, remove) uses meta.id as the canonical identity.
        self._flows: dict[str, tuple[Graph, FlowMeta]] = {}
        self._no_env_fallback = no_env_fallback
        self._store = store if store is not None else NullFlowStore()
        # Maps meta.id → store key when they differ (pre-placed files with human-readable names).
        self._store_keys: dict[str, str] = {}
        # Lightweight metadata cache for store flows not yet fully loaded into _flows.
        # Avoids re-reading JSON on every list_metas() call for multi-worker uploads.
        self._store_meta_cache: dict[str, FlowMeta] = {}
        # Flow IDs whose source of truth is the store. These are re-verified against
        # the store in get() / list_metas() to catch cross-worker deletes.
        self._store_sourced: set[str] = set()
        # TTL cache for store.list_ids() to avoid one filesystem glob per /health call.
        self._store_ids_cache: list[str] | None = None
        self._store_ids_cache_ts: float = 0.0

    def stamp(self, graph: Graph) -> None:
        """Apply the registry's env-fallback policy to ``graph.context``.

        Called again after ``deepcopy`` in the run/stream endpoints, since
        ``Graph.__deepcopy__`` does not carry ``context`` over.
        """
        if self._no_env_fallback:
            graph.context["no_env_fallback"] = True

    def _get_cached_store_ids(self) -> list[str]:
        """Return store.list_ids(), refreshing at most once per _STORE_IDS_TTL seconds."""
        now = time.monotonic()
        if self._store_ids_cache is None or now - self._store_ids_cache_ts > self._STORE_IDS_TTL:
            self._store_ids_cache = self._store.list_ids()
            self._store_ids_cache_ts = now
        return self._store_ids_cache

    def _invalidate_store_ids_cache(self) -> None:
        self._store_ids_cache = None

    def add(self, graph: Graph, meta: FlowMeta, *, overwrite: bool = False, raw_json: dict | None = None) -> None:
        if not overwrite and meta.id in self._flows:
            msg = f"Flow '{meta.id}' is already registered. Pass overwrite=True to replace it."
            raise FlowAlreadyRegisteredError(msg)
        # If overwriting a flow that was loaded from a differently-named store file
        # (e.g. prompt_one.json whose JSON id is a UUID), delete the old file and
        # clear the alias so the new file becomes the single source of truth.
        if overwrite:
            old_store_key = self._store_keys.pop(meta.id, None)
            if old_store_key is not None:
                self._store.delete(old_store_key)
                self._flows.pop(old_store_key, None)
            else:
                # No alias recorded — the replace path skips the get() that would have
                # learned it. A pre-placed file (e.g. my-flow.json) may still carry meta.id
                # in its JSON "id" under a differently-named key; delete it so the new
                # {uuid}.json becomes the single source of truth.
                self._delete_aliased_store_files(meta.id)
        if raw_json is not None:
            self._store.write(meta.id, raw_json)
            if getattr(self._store, "is_persistent", False):
                self._store_sourced.add(meta.id)
        self.stamp(graph)
        self._flows[meta.id] = (graph, meta)
        self._store_meta_cache.pop(meta.id, None)
        self._invalidate_store_ids_cache()

    def _evict(self, meta_id: str) -> None:
        """Remove all in-memory traces of a store-sourced flow (e.g. deleted by another worker)."""
        store_key = self._store_keys.pop(meta_id, meta_id)
        for k in {meta_id, store_key}:
            self._flows.pop(k, None)
            self._store_meta_cache.pop(k, None)
        self._store_sourced.discard(meta_id)

    def _delete_aliased_store_files(self, canonical_id: str) -> None:
        """Delete stem-keyed store files that are aliases of *canonical_id*.

        Targets persistent-store files whose JSON ``id`` equals *canonical_id* but are
        keyed under a different stem (e.g. a pre-placed ``my-flow.json`` alongside
        ``{uuid}.json``), so the canonical key stays the single source of truth. Also
        drops any in-memory cache entries for those stems. No-op for non-persistent
        stores (NullFlowStore has no other files). Uses a live ``list_ids()`` rather than
        the TTL cache so a listing taken right after a delete is current.
        """
        if not getattr(self._store, "is_persistent", False):
            return
        for stem_id in self._store.list_ids():
            if stem_id == canonical_id:
                continue
            stem_raw = self._store.read(stem_id)
            if stem_raw and stem_raw.get("id") == canonical_id:
                self._store.delete(stem_id)
                self._flows.pop(stem_id, None)
                self._store_meta_cache.pop(stem_id, None)

    def get(self, flow_id: str) -> tuple[Graph, FlowMeta] | None:
        if flow_id in self._flows:
            _, meta = self._flows[flow_id]
            # Cross-worker stale check: if this flow came from the store, verify it
            # hasn't been deleted by another worker since we cached it.
            # Use _store_keys to find the real store key (which may be a filename stem
            # rather than the JSON UUID for pre-placed flows).
            if meta.id in self._store_sourced:
                store_key = self._store_keys.get(meta.id, meta.id)
                if self._store.read(store_key) is None:
                    self._evict(meta.id)
                    return None
            return self._flows[flow_id]
        raw_json = self._store.read(flow_id)
        if raw_json is None:
            return None
        graph, meta = self._reconstruct(flow_id, raw_json)
        # Cache under the authoritative JSON id so requests by UUID find it.
        self._flows[meta.id] = (graph, meta)
        self._store_meta_cache.pop(meta.id, None)
        if flow_id != meta.id:
            # Also keep the filename-stem alias so warm_from_store lookups hit.
            self._flows[flow_id] = (graph, meta)
            # Remember the store key so remove() can delete the right file.
            self._store_keys[meta.id] = flow_id
        return graph, meta

    @staticmethod
    def _meta_from_raw_json(flow_id: str, raw_json: dict) -> FlowMeta:
        actual_id = raw_json.get("id") or flow_id
        return FlowMeta(
            id=actual_id,
            relative_path="<filesystem>",
            title=raw_json.get("name", actual_id),
            description=raw_json.get("description"),
        )

    def _reconstruct(self, flow_id: str, raw_json: dict) -> tuple[Graph, FlowMeta]:
        meta = self._meta_from_raw_json(flow_id, raw_json)
        graph = load_flow_from_json(raw_json)
        graph.prepare()
        graph.flow_id = meta.id
        self.stamp(graph)
        if getattr(self._store, "is_persistent", False):
            self._store_sourced.add(meta.id)
        return graph, meta

    def warm_from_store(self) -> None:
        """Load all flows from the backing store into the in-memory cache.

        Called once at startup so every worker can serve any flow that was
        previously uploaded (by another worker or a prior run) without a
        cache-miss penalty on the first request.
        """
        # Bypass the TTL cache — startup must always see the current store state.
        for flow_id in self._store.list_ids():
            try:
                self.get(flow_id)  # no-op if already cached; loads from store otherwise
            except Exception as exc:  # noqa: BLE001
                # One unloadable flow (corrupt JSON, or a flow referencing a component
                # not available in this build) must not abort the whole worker's startup —
                # skip it so every other flow still serves.
                logger.warning("Skipping flow %r during store warm-up: %r", flow_id, exc)

    def list_metas(self) -> list[FlowMeta]:
        seen: set[str] = set()
        result: list[FlowMeta] = []
        store_ids = set(self._get_cached_store_ids())
        for _, meta in self._flows.values():
            if meta.id in seen:
                continue
            # Skip flows deleted by another worker (still in our cache but gone from store).
            # Use the real store key (may be a filename stem for pre-placed flows).
            # Check the store directly rather than the TTL-cached id list, so a delete
            # by another worker is reflected immediately (same as the get() stale check).
            if meta.id in self._store_sourced:
                store_key = self._store_keys.get(meta.id, meta.id)
                if not self._store.exists(store_key):
                    continue
            result.append(meta)
            seen.add(meta.id)
        for flow_id in store_ids:
            if flow_id not in self._flows:
                # Check the lightweight metadata cache before reading from disk.
                if flow_id in self._store_meta_cache:
                    cached = self._store_meta_cache[flow_id]
                    if cached.id not in seen:
                        result.append(cached)
                        seen.add(cached.id)
                    continue
                raw_json = self._store.read(flow_id)
                if raw_json:
                    meta = self._meta_from_raw_json(flow_id, raw_json)
                    if meta.id not in seen:
                        self._store_meta_cache[flow_id] = meta
                        result.append(meta)
                        seen.add(meta.id)
        return result

    def remove(self, flow_id: str) -> bool:
        # Resolve the canonical meta id and store key.
        entry = self._flows.get(flow_id)
        if entry is not None:
            meta_id = entry[1].id
            store_key = self._store_keys.get(meta_id, meta_id)
            # Drop all cache keys that point to this flow (UUID and any filename alias).
            for k in [meta_id, store_key]:
                self._flows.pop(k, None)
                self._store_meta_cache.pop(k, None)
            self._store_keys.pop(meta_id, None)
            self._store_sourced.discard(meta_id)
            mem_had_it = True
        else:
            # Flow not in memory; derive both the stem key (flow_id) and the UUID from the file.
            store_key = flow_id
            self._store_meta_cache.pop(flow_id, None)
            self._store_sourced.discard(flow_id)
            mem_had_it = False
            meta_id = flow_id  # best-effort default; overridden below if we can read the file
            raw = self._store.read(flow_id)
            if raw:
                meta_id = raw.get("id") or flow_id

        store_had_it = self._store.delete(store_key)
        # Ensure cross-worker DELETE propagation: delete BOTH the primary store key
        # and any alternate-keyed file so that workers whose in-memory stale-check
        # uses a different key also see the deletion on their next request.
        if store_key != meta_id:
            # Alias known: primary key was a stem, UUID-keyed file may also exist.
            self._store.delete(meta_id)
        elif store_had_it:
            # Primary key IS the UUID: delete any stem-keyed file carrying the same
            # "id" field (e.g. a pre-placed my-flow.json alongside {uuid}.json).
            self._delete_aliased_store_files(meta_id)
        self._invalidate_store_ids_cache()
        return mem_had_it or store_had_it

    def __len__(self) -> int:
        # Delegates to list_metas() so store-only flows (not yet cache-loaded) are
        # counted. list_metas() caches metadata after the first disk read, so
        # repeated calls (e.g. /health) are cheap after the first.
        return len(self.list_metas())


class UploadFlowRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str = Field(..., description="Human-readable name for the flow")
    data: dict = Field(..., description="Flow graph data — nodes and edges")
    description: str | None = Field(default=None, description="Optional flow description")
    id: str | None = Field(default=None, description="Stable flow ID from Langflow export (must be a valid UUID)")
    replace: bool = Field(default=False, description="Overwrite the existing flow if the ID already exists")

    @field_validator("id", mode="before")
    @classmethod
    def validate_id_is_uuid(cls, v: object) -> object:
        if v is None:
            return v
        try:
            uuid.UUID(str(v))
        except ValueError:
            msg = f"id must be a valid UUID, got {v!r}"
            raise ValueError(msg) from None
        return str(v)


class UploadFlowResponse(BaseModel):
    id: str = Field(..., description="Flow identifier (UUID)")
    name: str
    description: str | None
    run_url: str = Field(..., description="Endpoint to POST run requests, e.g. /flows/{id}/run")


# -----------------------------------------------------------------------------
# Streaming helper functions
# -----------------------------------------------------------------------------


async def consume_and_yield(queue: asyncio.Queue, client_consumed_queue: asyncio.Queue) -> AsyncGenerator:
    """Consumes events from a queue and yields them to the client while tracking timing metrics.

    This coroutine continuously pulls events from the input queue and yields them to the client.
    It tracks timing metrics for how long events spend in the queue and how long the client takes
    to process them.

    Args:
        queue (asyncio.Queue): The queue containing events to be consumed and yielded
        client_consumed_queue (asyncio.Queue): A queue for tracking when the client has consumed events

    Yields:
        The value from each event in the queue

    Notes:
        - Events are tuples of (event_id, value, put_time)
        - Breaks the loop when receiving a None value, signaling completion
        - Tracks and logs timing metrics for queue time and client processing time
        - Notifies client consumption via client_consumed_queue
    """
    while True:
        event_id, value, put_time = await queue.get()
        if value is None:
            break
        get_time = time.time()
        yield value
        get_time_yield = time.time()
        client_consumed_queue.put_nowait(event_id)
        logger.debug(
            f"consumed event {event_id} "
            f"(time in queue, {get_time - put_time:.4f}, "
            f"client {get_time_yield - get_time:.4f})"
        )


async def run_flow_generator_for_serve(
    graph: Graph,
    input_request: StreamRequest,
    flow_id: str,
    event_manager,
    client_consumed_queue: asyncio.Queue,
) -> None:
    """Executes a flow asynchronously and manages event streaming to the client.

    This coroutine runs a flow with streaming enabled and handles the event lifecycle,
    including success completion and error scenarios.

    Args:
        graph (Graph): The graph to execute
        input_request (StreamRequest): The input parameters for the flow
        flow_id (str): The ID of the flow being executed
        event_manager: Manages the streaming of events to the client
        client_consumed_queue (asyncio.Queue): Tracks client consumption of events

    Events Generated:
        - "add_message": Sent when new messages are added during flow execution
        - "token": Sent for each token generated during streaming
        - "end": Sent when flow execution completes, includes final result
        - "error": Sent if an error occurs during execution

    Notes:
        - Runs the flow with streaming enabled via execute_graph_with_capture()
        - On success, sends the final result via event_manager.on_end()
        - On error, logs the error and sends it via event_manager.on_error()
        - Always sends a final None event to signal completion
    """
    try:
        # For the serve app, we'll use execute_graph_with_capture with streaming
        # Note: This is a simplified version. In a full implementation, you might want
        # to integrate with the full LFX streaming pipeline from endpoints.py
        results, logs = await execute_graph_with_capture(
            graph, input_request.input_value, session_id=input_request.session_id
        )
        result_data = extract_result_data(results, logs)

        # Send the final result
        event_manager.on_end(data={"result": result_data})
        await client_consumed_queue.get()
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error running flow {flow_id}: {e}")
        event_manager.on_error(data={"error": str(e)})
    finally:
        await event_manager.queue.put((None, None, time.time()))


# -----------------------------------------------------------------------------
# Application factory
# -----------------------------------------------------------------------------


def create_multi_serve_app(
    *,
    registry: FlowRegistry,
) -> FastAPI:
    """Create a FastAPI app exposing LFX flows via a mutable registry.

    Routes dispatch to ``registry`` at request time, so flows added after
    startup (via ``POST /flows/upload/``) are immediately reachable.
    """
    app = FastAPI(
        title=f"LFX Multi-Flow Server ({len(registry)})",
        description=(
            "Hosts LFX graphs under the `/flows/{{id}}` prefix. "
            "Use `/flows` to list available IDs then POST your input to `/flows/{{id}}/run`. "
            "Use `POST /flows/upload/` to register new flows at runtime."
        ),
        version="1.0.0",
    )
    app.state.registry = registry

    # ------------------------------------------------------------------
    # Global endpoints
    # ------------------------------------------------------------------

    @app.get(
        "/flows",
        response_model=list[FlowMeta],
        tags=["info"],
        summary="List available flows",
        dependencies=[Depends(verify_api_key)],
    )
    async def list_flows():
        return registry.list_metas()

    @app.get("/health", tags=["info"], summary="Global health check")
    async def global_health():
        return {"status": "healthy", "flow_count": len(registry)}

    # ------------------------------------------------------------------
    # Upload endpoint — registered BEFORE /{flow_id} to avoid shadowing
    # ------------------------------------------------------------------

    @app.post(
        "/flows/upload/",
        response_model=UploadFlowResponse,
        status_code=201,
        tags=["upload"],
        summary="Upload and register a new flow",
        dependencies=[Depends(verify_api_key)],
    )
    async def upload_flow(body: UploadFlowRequest) -> UploadFlowResponse:
        # Conflict check before the expensive load+prepare — only possible when the
        # caller supplies an explicit id.  uuid4()-generated ids are always unique so
        # there is no point checking before we have one.
        flow_id = body.id or str(uuid.uuid4())

        if not body.replace and registry.get(flow_id) is not None:
            raise HTTPException(
                status_code=409,
                detail=f"Flow '{flow_id}' already exists. Pass replace=true to overwrite.",
            )

        try:
            graph = load_flow_from_json(body.model_dump(exclude={"replace"}))
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Invalid flow data: {exc}") from exc

        try:
            graph.prepare()
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Flow preparation failed: {exc}") from exc

        graph.flow_id = flow_id
        meta = FlowMeta(
            id=flow_id,
            relative_path="<uploaded>",
            title=body.name,
            description=body.description,
        )
        # graph.prepare() must run before registry.add() — add() stamps
        # graph.context with no_env_fallback, and prepare() must not overwrite it.
        registry.add(graph, meta, overwrite=body.replace, raw_json=body.model_dump(exclude={"replace"}))
        return UploadFlowResponse(
            id=flow_id,
            name=body.name,
            description=body.description,
            run_url=f"/flows/{flow_id}/run",
        )

    # ------------------------------------------------------------------
    # Per-flow dispatch routes
    # ------------------------------------------------------------------

    def _get_flow_or_404(flow_id: str) -> tuple[Graph, FlowMeta]:
        result = registry.get(flow_id)
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "flow not found", "flow_id": flow_id},
            )
        return result

    @app.delete(
        "/flows/{flow_id}",
        status_code=204,
        tags=["flows"],
        summary="Remove a registered flow",
        description=(
            "Remove a flow from this worker's registry and from the backing store (if any). "
            "**Multi-worker note:** the store file is deleted immediately, but other workers "
            "continue to serve the cached copy until their next stale check "
            "(triggered by an incoming request for that flow). "
            "This is the same eventual-consistency window that applies to uploads."
        ),
        dependencies=[Depends(verify_api_key)],
    )
    async def delete_flow(flow_id: str) -> Response:
        removed = registry.remove(flow_id)
        if not removed:
            raise HTTPException(
                status_code=404,
                detail={"error": "flow not found", "flow_id": flow_id},
            )
        return Response(status_code=204)

    @app.get(
        "/flows/{flow_id}/info",
        response_model=FlowMeta,
        tags=["flows"],
        summary="Flow metadata",
        dependencies=[Depends(verify_api_key)],
    )
    async def flow_info(flow_id: str) -> FlowMeta:
        _, meta = _get_flow_or_404(flow_id)
        return meta

    @app.post(
        "/flows/{flow_id}/run",
        response_model=RunResponse,
        responses={404: {"model": ErrorResponse}, 500: {"model": RunResponse}},
        tags=["flows"],
        summary="Execute flow",
        dependencies=[Depends(verify_api_key)],
    )
    async def run_flow(flow_id: str, request: RunRequest) -> RunResponse:
        graph, _ = _get_flow_or_404(flow_id)
        try:
            validate_flow_for_current_settings(graph)
            graph_copy = deepcopy(graph)
            # deepcopy() drops graph.context; re-apply the registry's env policy.
            registry.stamp(graph_copy)
            apply_global_vars_to_graph(graph_copy, request.global_vars)
            results, logs = await execute_graph_with_capture(
                graph_copy, request.input_value, session_id=request.session_id
            )
            result_data = extract_result_data(results, logs)

            if not result_data.get("success", True):
                error_message = result_data.get("result", result_data.get("text", "No response generated"))
                return JSONResponse(
                    status_code=500,
                    content=RunResponse(
                        result=error_message,
                        success=False,
                        logs=logs
                        or f"Flow execution completed but no valid result was produced.\nResult data: {result_data}",
                        type="error",
                        component=result_data.get("component", ""),
                    ).model_dump(),
                )
            return RunResponse(
                result=result_data.get("result", result_data.get("text", "")),
                success=result_data.get("success", True),
                logs=logs,
                type=result_data.get("type", "message"),
                component=result_data.get("component", ""),
            )
        except Exception as exc:  # noqa: BLE001
            error_traceback = traceback.format_exc()
            error_message = f"Flow execution failed: {exc!s}"
            logger.error(f"Error running flow {flow_id}: {exc}")
            logger.debug(f"Full traceback for flow {flow_id}:\n{error_traceback}")
            return JSONResponse(
                status_code=500,
                content=RunResponse(
                    result=error_message,
                    success=False,
                    logs=f"ERROR: {error_message}\n\nFull traceback:\n{error_traceback}",
                    type="error",
                    component="",
                ).model_dump(),
            )

    @app.post(
        "/flows/{flow_id}/stream",
        response_model=None,
        tags=["flows"],
        summary="Stream flow execution",
        dependencies=[Depends(verify_api_key)],
    )
    async def stream_flow(flow_id: str, request: StreamRequest) -> StreamingResponse:
        graph, _ = _get_flow_or_404(flow_id)
        try:
            validate_flow_for_current_settings(graph)
            from lfx.events.event_manager import create_stream_tokens_event_manager

            asyncio_queue: asyncio.Queue = asyncio.Queue()
            asyncio_queue_client_consumed: asyncio.Queue = asyncio.Queue()
            event_manager = create_stream_tokens_event_manager(queue=asyncio_queue)

            graph_copy = deepcopy(graph)
            # deepcopy() drops graph.context; re-apply the registry's env policy.
            registry.stamp(graph_copy)
            apply_global_vars_to_graph(graph_copy, request.global_vars)
            main_task = asyncio.create_task(
                run_flow_generator_for_serve(
                    graph=graph_copy,
                    input_request=request,
                    flow_id=flow_id,
                    event_manager=event_manager,
                    client_consumed_queue=asyncio_queue_client_consumed,
                )
            )

            async def on_disconnect() -> None:
                logger.debug(f"Client disconnected from flow {flow_id}, closing tasks")
                main_task.cancel()

            return StreamingResponse(
                consume_and_yield(asyncio_queue, asyncio_queue_client_consumed),
                background=on_disconnect,
                media_type="text/event-stream",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(f"Error setting up streaming for flow {flow_id}: {exc}")
            error_payload = json.dumps({"error": str(exc), "success": False})

            async def error_stream():
                yield f"data: {error_payload}\n\n"

            return StreamingResponse(error_stream(), media_type="text/event-stream")

    return app


def create_serve_app() -> FastAPI:
    """ASGI app factory called by each uvicorn worker in multi-worker mode.

    Workers cannot inherit the parent's in-memory app object. Instead, each
    worker calls this factory, which reads ``LFX_SERVE_FLOW_DIR`` and
    ``LFX_SERVE_NO_ENV_FALLBACK`` from the environment, pre-warms its own
    in-memory cache from the shared ``FilesystemFlowStore``, and returns a
    ready FastAPI app.

    The parent process must set those env vars **before** calling
    ``uvicorn.run("lfx.cli.serve_app:create_serve_app", workers=N, ...)``.
    """
    import asyncio
    import os
    from pathlib import Path

    from lfx.cli.flow_store import FilesystemFlowStore, NullFlowStore

    flow_dir_str = os.environ.get(_SERVE_FLOW_DIR_ENV)
    no_env_fallback = os.environ.get(_SERVE_NO_ENV_FALLBACK_ENV, "0") == "1"
    startup_paths_json = os.environ.get(_SERVE_STARTUP_PATHS_ENV, "")

    flow_dir = Path(flow_dir_str) if flow_dir_str else None
    flow_store = FilesystemFlowStore(flow_dir) if flow_dir else NullFlowStore()

    startup_paths = [Path(p) for p in json.loads(startup_paths_json)] if startup_paths_json else []

    if startup_paths and not flow_dir:
        # No shared store: each worker reloads startup flows from the original file paths.
        # When flow_dir IS set the parent already persisted startup JSON flows to the store;
        # workers pick them up via warm_from_store() below — no need to re-read files.
        #
        # ``create_serve_app`` is called by uvicorn as an ASGI app factory while an
        # event loop is already running in the worker process.  ``asyncio.run()``
        # raises RuntimeError in that situation.  Running the coroutine in a fresh
        # thread gives it a clean event loop with no interference.
        import concurrent.futures

        from lfx.cli.commands import build_registry_from_directory, build_registry_from_paths

        if len(startup_paths) == 1 and startup_paths[0].is_dir():
            coro = build_registry_from_directory(
                startup_paths[0],
                lambda _: None,
                check_variables=False,
                no_env_fallback=no_env_fallback,
                store=flow_store,
            )
        else:
            coro = build_registry_from_paths(
                startup_paths,
                lambda _: None,
                check_variables=False,
                no_env_fallback=no_env_fallback,
                store=flow_store,
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            registry = pool.submit(asyncio.run, coro).result()
    else:
        registry = FlowRegistry(no_env_fallback=no_env_fallback, store=flow_store)

    registry.warm_from_store()
    return create_multi_serve_app(registry=registry)
