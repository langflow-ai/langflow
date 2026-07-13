import asyncio
import hashlib
import json
import tempfile
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Annotated, Any

import chromadb.errors
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from lfx.base.data.utils import extract_text_from_bytes
from lfx.base.knowledge_bases.backends import BackendType, create_backend
from lfx.base.knowledge_bases.ingestion_sources import (
    FolderSource,
    SourceType,
    create_source,
    get_source_class,
    registered_sources,
)
from lfx.base.vectorstores.chroma_security import chroma_client_create_collection_kwargs
from lfx.log import logger
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser, ingestion_run_service, knowledge_base_service
from langflow.api.utils.kb_helpers import KBAnalysisHelper, KBIngestionHelper, KBStorageHelper
from langflow.api.utils.kb_metadata import parse_per_file_metadata, parse_user_metadata
from langflow.api.v1.schemas import TaskResponse
from langflow.schema.knowledge_base import (
    BulkDeleteRequest,
    ChunkInfo,
    ConnectorCatalogEntry,
    ConnectorIngestRequest,
    CreateKnowledgeBaseRequest,
    IngestionRunDetail,
    IngestionRunInfo,
    IngestionRunItemInfo,
    KbMetadataKeysResponse,
    KnowledgeBaseInfo,
    PaginatedChunkResponse,
    PaginatedIngestionRunResponse,
    TestBackendConnectionRequest,
    TestBackendConnectionResponse,
)
from langflow.services.authorization import (
    KnowledgeBaseAction,
    ensure_knowledge_base_permission,
)
from langflow.services.database.models.jobs.model import JobStatus, JobType
from langflow.services.database.models.knowledge_base.model import KnowledgeBaseRecord
from langflow.services.deps import get_job_service, get_settings_service, get_task_service
from langflow.services.jobs import DuplicateJobError
from langflow.services.jobs.service import JobService
from langflow.services.memory_base.kb_path_helpers import validate_kb_path
from langflow.services.task.service import TaskService
from langflow.utils.kb_constants import (
    CHUNK_PREVIEW_MULTIPLIER,
    KB_METADATA_RESERVED_KEYS,
    MAX_CHUNK_OVERLAP,
    MAX_CHUNK_SIZE,
    MAX_MAX_CHUNKS,
    MIN_CHUNK_OVERLAP,
    MIN_CHUNK_SIZE,
    MIN_KB_NAME_LENGTH,
    MIN_MAX_CHUNKS,
)

# Cap on distinct values per metadata key returned by ``/metadata/keys``.
# Distinct value sets in the wild can be unbounded (free-form strings),
# so the endpoint truncates and signals the cap via the ``truncated`` flag
# on its response. Keep small enough to keep the popover dropdown usable.
KB_METADATA_KEYS_VALUES_CAP = 50

router = APIRouter(tags=["Knowledge Bases"], prefix="/knowledge_bases", include_in_schema=False)


@dataclass(frozen=True)
class _KbGuardResult:
    """Outcome of ``_guard_kb_action`` used by routes to know the effective owner.

    ``owner_user`` is the user whose disk-path and DB rows back the KB. For
    the common owner-only case this equals the actor; for a cross-user
    share grant it is the KB record's true owner so the route loads the KB
    from the owner's namespace instead of silently re-reading the actor's.
    """

    record: KnowledgeBaseRecord | None
    owner_user: Any  # User — typing here would create a circular import


async def _guard_kb_action(
    *,
    current_user,
    action,
    kb_name: str | None,
) -> _KbGuardResult:
    """Guard a KB-scoped action and return the effective KB owner context.

    Looks up ``KnowledgeBaseRecord(user_id=current_user.id, name=kb_name)`` so
    the policy object key (``knowledge_base:{record.id}``) lines up with the
    UUID-typed ``authz_share.resource_id`` column. Legacy disk-only KBs (no
    ``KnowledgeBaseRecord`` row) fall back to ``kb_id=None`` so the enforcer
    sees ``knowledge_base:*`` and the owner-override path still applies.

    Cross-user reachability: when share-aware fetch is supported AND
    ``LANGFLOW_AUTHZ_ENABLED=true``, the helper falls back to scanning every
    KB with that name across users so a share grant on a non-owned KB id
    surfaces here instead of silently degrading to ``knowledge_base:*``. The
    enforcer is asked once per candidate; the first allowed match wins.

    The returned ``owner_user`` is the resolved KB owner — callers use its
    ``id``/``username`` to load DB rows and resolve filesystem paths in the
    owner's namespace, otherwise a non-owner with a share grant would still
    read their own (possibly absent) KB.
    """
    from langflow.services.authorization.utils import (
        _auth_context,
        _coerce_action,
        _resolve_authz_domain,
    )
    from langflow.services.database.models.user.crud import get_user_by_id
    from langflow.services.deps import get_authorization_service, session_scope

    kb_id: uuid.UUID | None = None
    kb_user_id: uuid.UUID = current_user.id
    resolved_record: KnowledgeBaseRecord | None = None
    if kb_name:
        record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
        if record is not None:
            resolved_record = record
            kb_id = record.id
            kb_user_id = record.user_id
        else:
            # Owner-scoped lookup missed. If share-aware fetch is active,
            # scan all KBs with that name and ask the enforcer which one the
            # actor can reach via a share/role grant.
            authz = get_authorization_service()
            if await authz.supports_cross_user_fetch() and await authz.is_enabled():
                candidates = await knowledge_base_service.list_by_name(kb_name)
                act_str = _coerce_action(action)
                context = _auth_context(current_user)
                for candidate in candidates:
                    allowed = await authz.enforce(
                        user_id=current_user.id,
                        domain=_resolve_authz_domain(None, None),
                        obj=f"knowledge_base:{candidate.id}",
                        act=act_str,
                        context=context,
                    )
                    if allowed:
                        resolved_record = candidate
                        kb_id = candidate.id
                        kb_user_id = candidate.user_id
                        break
    await ensure_knowledge_base_permission(
        current_user,
        action,
        kb_id=kb_id,
        kb_user_id=kb_user_id,
        kb_name=kb_name,
    )
    # Resolve the owner User so routes can compute disk paths against the
    # right username. For the common owner-only case the actor is the owner
    # and we skip the DB roundtrip.
    if kb_user_id == current_user.id:
        return _KbGuardResult(record=resolved_record, owner_user=current_user)
    # ``kb_user_id`` comes from a SQLAlchemy column in production — always a
    # UUID. Defensive guard: skip the DB lookup if the value isn't a UUID
    # (e.g. a test mock where ``record.user_id`` is an auto-generated
    # ``MagicMock``). Without this, the bind fails with
    # ``Error binding parameter 1: type 'MagicMock' is not supported``.
    if not isinstance(kb_user_id, uuid.UUID):
        return _KbGuardResult(record=resolved_record, owner_user=current_user)
    async with session_scope() as session:
        owner = await get_user_by_id(session, kb_user_id)
    if owner is None:
        # Edge case: the record's owner has been deleted while a share still
        # references it. Fall back to the actor — the disk path won't
        # resolve and the route will surface a clean 404.
        return _KbGuardResult(record=resolved_record, owner_user=current_user)
    return _KbGuardResult(record=resolved_record, owner_user=owner)


def _validate_kb_path_containment(kb_user_path: Path, kb_path: Path, kb_name: str, username: str) -> None:
    """Raise 403 if kb_path is not contained within kb_user_path.

    Delegates the actual containment check to
    :func:`langflow.services.memory_base.kb_path_helpers.validate_kb_path`
    (introduced in #12417) so the traversal guard is defined in one
    place — but translates its ``ValueError`` into the 403 HTTPException
    expected by the KB routes and keeps the high-signal log line.
    """
    try:
        validate_kb_path(kb_user_path, kb_path)
    except ValueError as exc:
        logger.warning(
            "Path traversal attempt blocked: user=%s kb_name=%r resolved_path=%s",
            username,
            kb_name,
            kb_path,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Access denied for knowledge base '{kb_name}'.",
        ) from exc


def _resolve_kb_path(kb_name: str, owner_user) -> Path:
    """Resolve and validate KB path against the KB *owner's* namespace.

    ``owner_user`` is the User whose ``username`` roots the KB directory —
    for owner-only requests this is ``current_user``; for cross-user share
    grants ``_guard_kb_action`` returns the resolved KB owner so the route
    reads the KB from the right user directory.

    Raises 500 if root path not configured.
    Raises 403 if path traversal is detected (kb_name escapes the user directory).
    Raises 404 if the KB directory does not exist.
    """
    kb_root_path = KBStorageHelper.get_root_path()
    kb_user = owner_user.username
    kb_user_path = (kb_root_path / kb_user).resolve()
    kb_path = (kb_user_path / kb_name).resolve()

    _validate_kb_path_containment(kb_user_path, kb_path, kb_name, kb_user)

    if not kb_path.exists() or not kb_path.is_dir():
        raise HTTPException(status_code=404, detail=f"Knowledge base '{kb_name}' not found")
    return kb_path


def _build_connector_ingest_dedupe_key(
    *,
    user_id: uuid.UUID,
    kb_name: str,
    source_type: str,
    source_config: dict[str, Any],
) -> str:
    """Build a stable idempotency key for a connector-driven ingestion job.

    The key is a SHA-256 hash of ``(user, kb, source_type, sorted_config)``
    so semantically-equivalent requests collapse to the same key regardless
    of JSON key ordering. Only the hash (not the config) goes on the
    ``job`` row, so no credentials leak through ``dedupe_key``.
    """
    canonical = json.dumps(
        {
            "user_id": str(user_id),
            "kb_name": kb_name,
            "source_type": source_type,
            "source_config": source_config,
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    return f"kb_connector_ingest:{digest}"


def _is_memory_base_associated(metadata: dict[str, Any]) -> bool:
    """Return True if the KB metadata indicates an association with a Memory Base."""
    source_types = metadata.get("source_types")
    return isinstance(source_types, list) and "memory" in source_types


def _check_memory_base_association(kb_name: str, current_user: CurrentActiveUser) -> None:
    """Raise 403 if the KB is associated with a Memory Base (FastAPI dep).

    Owner-scoped early gate — runs as ``Depends(...)`` before the route
    body and only sees the actor. For shared KBs reached through an
    shared grant the actor has no same-named local KB so this
    dep returns early; the route body then re-runs the check against the
    resolved owner via :func:`_assert_kb_not_memory_base` so a shared
    Memory-Base-managed KB still gets blocked.

    A missing local directory is NOT treated as a 404 here because the
    delete route handles the orphan-DB-row case downstream. This dep
    only blocks Memory-Base-managed KBs from being touched; an
    orphan row can't have Memory-Base metadata because that metadata
    lives in the on-disk ``embedding_metadata.json`` which is gone.
    """
    try:
        kb_path = _resolve_kb_path(kb_name, current_user)
    except HTTPException as exc:
        if exc.status_code == HTTPStatus.NOT_FOUND:
            return  # Let the route body handle the missing-dir case.
        raise

    metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
    if _is_memory_base_associated(metadata):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: knowledge base '{kb_name}' is managed by a Memory Base.",
        )


def _assert_kb_not_memory_base(kb_name: str, owner_user) -> None:
    """Post-resolution memory-base check.

    The FastAPI dep :func:`_check_memory_base_association` only sees the
    actor; for cross-user-reached KBs (a non-owner with a share grant) it
    short-circuits because the actor has no same-named local KB. Route
    bodies call this helper after :func:`_guard_kb_action` resolves the
    real owner so Memory-Base-managed KBs are still blocked even when
    reached through a share.
    """
    try:
        kb_path = _resolve_kb_path(kb_name, owner_user)
    except HTTPException as exc:
        if exc.status_code == HTTPStatus.NOT_FOUND:
            return
        raise
    metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
    if _is_memory_base_associated(metadata):
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: knowledge base '{kb_name}' is managed by a Memory Base.",
        )


def _coerce_backend_config(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


async def _resolve_kb_asset_id(
    *,
    kb_name: str,
    current_user: CurrentActiveUser,
    metadata: dict[str, Any],
) -> uuid.UUID:
    """Return the canonical ``asset_id`` for a KB.

    Prefers ``KnowledgeBaseRecord.id`` from the ``knowledge_base`` table —
    a btree-indexed UUID column — so downstream Job lookups can use the
    indexed ``Job.asset_id`` path instead of doing a JSON-extract on
    ``Job.job_metadata.kb_name``.

    Falls back to ``metadata['id']`` (and finally a fresh UUID) only for
    legacy KBs that exist on disk but haven't been backfilled into the
    ``knowledge_base`` table yet — startup runs ``backfill_all_users_from_disk``
    so this fallback should be rare. The fallback also persists the
    generated UUID into ``embedding_metadata.json`` so subsequent calls
    return a stable id.
    """
    kb_record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
    if kb_record is not None:
        return kb_record.id

    # Legacy fallback: KB exists on disk only.
    asset_id_str = metadata.get("id")
    if asset_id_str:
        try:
            return uuid.UUID(asset_id_str)
        except (ValueError, AttributeError):
            pass

    # No record, no metadata id — generate one and persist so the next
    # request resolves to the same UUID. Best-effort write; failure
    # falls through (the caller still gets a UUID, just one that won't
    # round-trip).
    asset_id = uuid.uuid4()
    try:
        kb_path = _resolve_kb_path(kb_name, current_user)
        metadata_path = kb_path / "embedding_metadata.json"
        if metadata_path.exists():
            embedding_metadata = json.loads(metadata_path.read_text())
            embedding_metadata["id"] = str(asset_id)
            metadata_path.write_text(json.dumps(embedding_metadata, indent=2))
    except (OSError, json.JSONDecodeError, HTTPException):
        await logger.awarning("Could not persist generated asset_id for kb=%r", kb_name)
    return asset_id


def _build_kb_info(
    *,
    kb_name: str,
    dir_name: str,
    metadata: dict[str, Any],
    size: int | None = None,
) -> KnowledgeBaseInfo:
    chunks_count = metadata.get("chunks") or 0
    # Trust a persisted "failed" status (set by ``perform_ingestion``)
    # so the UI can surface ``failure_reason`` after a backend error.
    # Otherwise fall back to the chunks-derived ready/empty heuristic
    # — that path covers freshly created KBs that have never been
    # ingested into and pre-status-tracking legacy rows.
    metadata_status = metadata.get("status")
    if metadata_status == "failed":
        status = "failed"
        failure_reason = metadata.get("failure_reason")
    else:
        status = "ready" if chunks_count > 0 else "empty"
        failure_reason = None
    return KnowledgeBaseInfo(
        id=str(metadata.get("id") or dir_name),
        dir_name=dir_name,
        name=kb_name,
        embedding_provider=metadata.get("embedding_provider") or "Unknown",
        embedding_model=metadata.get("embedding_model") or "Unknown",
        size=size if size is not None else int(metadata.get("size") or 0),
        words=int(metadata.get("words") or 0),
        characters=int(metadata.get("characters") or 0),
        chunks=int(chunks_count),
        avg_chunk_size=float(metadata.get("avg_chunk_size") or 0.0),
        chunk_size=metadata.get("chunk_size"),
        chunk_overlap=metadata.get("chunk_overlap"),
        separator=metadata.get("separator"),
        status=status,
        failure_reason=failure_reason,
        last_job_id=None,
        source_types=metadata.get("source_types", []),
        column_config=metadata.get("column_config"),
        backend_type=str(metadata.get("backend_type") or BackendType.CHROMA.value),
        backend_config=_coerce_backend_config(metadata.get("backend_config")),
    )


async def _resolve_backend_selection(
    *,
    kb_name: str,
    kb_path: Path,
    current_user: CurrentActiveUser,
) -> tuple[str, dict[str, Any]]:
    kb_record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
    if kb_record is not None:
        return (
            kb_record.backend_type or BackendType.CHROMA.value,
            _coerce_backend_config(kb_record.backend_config),
        )

    metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
    return (
        str(metadata.get("backend_type") or BackendType.CHROMA.value),
        _coerce_backend_config(metadata.get("backend_config")),
    )


async def _cleanup_orphan_db_row(
    *,
    kb_name: str,
    current_user: CurrentActiveUser,
) -> tuple[bool, str | None]:
    """Clean up a KB whose local directory is gone but whose DB row lingers.

    The usual delete flow requires the KB directory to exist — but
    remote-backed KBs (Astra / Mongo / Postgres / OpenSearch) store
    their vectors off-box, and the on-disk sidecar can go missing if
    the filesystem was cleaned out of band or creation failed partway
    through. Before this helper, such a KB would keep showing up in
    the UI list forever because the list endpoint reads the DB row
    while the delete endpoint 404s on the missing path.

    Returns ``(True, warning_or_None)`` when a row was found and
    deleted, ``(False, None)`` when no row exists (truly not found).
    The remote-backend cleanup is best-effort just like the normal
    delete path.
    """
    record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
    if record is None:
        return False, None

    backend_type_value = record.backend_type or BackendType.CHROMA.value
    backend_config = _coerce_backend_config(record.backend_config)

    warning: str | None = None
    if backend_type_value != BackendType.CHROMA.value:
        backend = create_backend(
            backend_type_value,
            kb_name=kb_name,
            kb_path=Path("/tmp"),  # noqa: S108 — unused; backend is remote-only
            backend_config=backend_config,
            user_id=current_user.id,
        )
        try:
            await backend.ensure_ready()
            await backend.delete_collection()
        except Exception as exc:  # noqa: BLE001
            await logger.aerror(
                "Failed to delete remote backend resources for orphan KB %s (%s): %s",
                kb_name,
                backend_type_value,
                exc,
            )
            warning = (
                f"Remote {backend_type_value} resources for knowledge base "
                f"'{kb_name}' could not be deleted ({exc}). The local record "
                "has been removed; please clean up the remote collection manually."
            )
        finally:
            await backend.teardown()

    try:
        await knowledge_base_service.delete_by_user_and_name(current_user.id, kb_name)
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("KB DB delete lagged for orphan %s: %s", kb_name, exc)

    return True, warning


async def _cancel_inflight_ingestion_for_kb(
    *,
    kb_name: str,
    current_user: CurrentActiveUser,
    job_service: JobService,
) -> None:
    """Cancel queued / in-progress ingestion jobs for the named KB.

    Looks up the KB's ``asset_id`` (preferring the indexed
    ``KnowledgeBaseRecord.id`` and falling back to disk metadata for
    legacy KBs), then transitions every job with
    ``asset_type='knowledge_base'`` and ``status in (QUEUED,
    IN_PROGRESS)`` to ``CANCELLED``. The ingestion polls
    :func:`KBIngestionHelper.is_job_cancelled` between batches and
    bails out via :class:`IngestionCancelledError`, which prevents
    chroma writes from auto-recreating the deleted KB directory.

    Best-effort: surfacing a cancellation failure here would mask the
    user's actual delete intent. Failures are logged and the delete
    proceeds — the worst case is the same as before this helper
    existed.
    """
    try:
        record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("KB lookup failed during cancel-on-delete for %s: %s", kb_name, exc)
        record = None

    asset_id: uuid.UUID | None = record.id if record is not None else None
    if asset_id is None:
        # Legacy disk-only KB: try to recover the id from the sidecar.
        try:
            kb_path = _resolve_kb_path(kb_name, current_user)
        except HTTPException:
            return
        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True) or {}
        raw_id = metadata.get("id")
        if not raw_id:
            return
        try:
            asset_id = uuid.UUID(str(raw_id))
        except (TypeError, ValueError):
            return

    try:
        cancelled = await job_service.cancel_in_flight_jobs_by_asset(
            asset_id=asset_id,
            asset_type="knowledge_base",
            user_id=current_user.id,
        )
    except Exception as exc:  # noqa: BLE001
        await logger.awarning("Cancel-on-delete failed for KB %s: %s", kb_name, exc)
        return

    if cancelled:
        await logger.ainfo(
            "Cancelled %d in-flight ingestion job(s) before deleting KB '%s'",
            len(cancelled),
            kb_name,
        )


async def _delete_remote_backend_collection(
    *,
    kb_name: str,
    kb_path: Path,
    current_user: CurrentActiveUser,
) -> str | None:
    """Delete the remote vector-store collection on a best-effort basis.

    Returns a human-readable warning string when the remote cleanup
    failed so the caller can surface it alongside the (successful)
    local-storage + DB-row deletions; returns ``None`` on success or
    when the backend is local-only (Chroma).

    Rationale for best-effort: a stale Astra token / missing MongoDB
    credential / network blip should not leave the user unable to
    delete the KB from Langflow's UI at all. Before this, the backend
    ``ensure_ready()`` failure would abort the whole delete flow and
    the row plus on-disk metadata would stay indefinitely. Remote
    resources that linger are surfaced to the user through the
    response warning and a high-severity log line so they can be
    cleaned up out-of-band.
    """
    backend_type_value, backend_config = await _resolve_backend_selection(
        kb_name=kb_name,
        kb_path=kb_path,
        current_user=current_user,
    )
    if backend_type_value == BackendType.CHROMA.value and backend_config.get("mode") != "cloud":
        return None

    backend = create_backend(
        backend_type_value,
        kb_name=kb_name,
        kb_path=kb_path,
        backend_config=backend_config,
        user_id=current_user.id,
    )
    try:
        await backend.ensure_ready()
        await backend.delete_collection()
    except Exception as exc:  # noqa: BLE001
        await logger.aerror(
            "Failed to delete remote backend resources for %s (%s): %s — "
            "proceeding with local cleanup; the remote collection may need "
            "manual cleanup.",
            kb_name,
            backend_type_value,
            exc,
        )
        return (
            f"Remote {backend_type_value} resources for knowledge base "
            f"'{kb_name}' could not be deleted ({exc}). The local record "
            "has been removed; please clean up the remote collection manually."
        )
    finally:
        await backend.teardown()
    return None


@router.post("/test-connection", status_code=HTTPStatus.OK)
async def test_backend_connection(
    request: TestBackendConnectionRequest,
    current_user: CurrentActiveUser,
) -> TestBackendConnectionResponse:
    """Validate a vector-store backend's configuration without creating a KB.

    Builds a transient backend instance against the supplied
    ``backend_type`` / ``backend_config`` and runs ``backend.test_connection()``,
    which each backend implements with a native reachability check
    (e.g. OpenSearch ``cluster.info``, Chroma ``heartbeat``). Both
    success and connectivity / credential failures return HTTP 200 — the
    ``ok`` field on the response indicates outcome. Malformed requests
    (unknown backend, missing required field) are rejected by the
    Pydantic validators before they reach this handler and surface as
    HTTP 422.
    """
    # Test-connection is a precondition for ``create_knowledge_base`` — gate
    # it on the same permission so a viewer-role user cannot enumerate
    # backend reachability they could not act on.
    await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.CREATE, kb_name=None)
    # Use a private temp directory for the transient backend so a
    # local-storage backend (Chroma) doesn't leak files into the user's
    # KB root, and so concurrent test-connection calls don't collide.
    with tempfile.TemporaryDirectory(prefix="kb-test-connection-") as tmp_dir:
        kb_path = Path(tmp_dir)
        try:
            backend = create_backend(
                request.backend_type,
                kb_name="__test_connection__",
                kb_path=kb_path,
                backend_config=dict(request.backend_config),
                embedding_function=None,
                user_id=current_user.id,
            )
        except ValueError as exc:
            # Registry rejection (unregistered backend, etc.) — surface
            # as a normal failure result rather than a 5xx so the UI can
            # render the message in the same toast it uses for the rest.
            return TestBackendConnectionResponse(
                ok=False,
                message=str(exc),
                details={"type": "ValueError"},
            )

        try:
            result = await backend.test_connection()
        finally:
            with suppress(Exception):
                await backend.teardown()

    return TestBackendConnectionResponse(
        ok=result.ok,
        message=result.message,
        details=dict(result.details),
    )


@router.post("", status_code=HTTPStatus.CREATED)
@router.post("/", status_code=HTTPStatus.CREATED)
async def create_knowledge_base(
    request: CreateKnowledgeBaseRequest,
    current_user: CurrentActiveUser,
) -> KnowledgeBaseInfo:
    """Create a new knowledge base with embedding configuration."""
    try:
        kb_root_path = KBStorageHelper.get_root_path()
        kb_user = current_user.username
        kb_name = request.name.strip().replace(" ", "_")
        await _guard_kb_action(
            current_user=current_user,
            action=KnowledgeBaseAction.CREATE,
            kb_name=kb_name or None,
        )
        # Validate KB name
        if not kb_name or len(kb_name) < MIN_KB_NAME_LENGTH:
            raise HTTPException(status_code=400, detail="Knowledge base name must be at least 3 characters")

        # Security: resolve paths and validate containment to prevent path traversal attacks.
        # A crafted kb_name like "../victim/evil" or an absolute path like "/tmp/evil" must be
        # rejected before any directory is created.
        kb_user_path = (kb_root_path / kb_user).resolve()
        kb_path = (kb_user_path / kb_name).resolve()
        _validate_kb_path_containment(kb_user_path, kb_path, kb_name, kb_user)

        # Check both durable DB state and legacy disk state. During
        # expand/contract rollout a KB row can exist even if its local
        # sidecar directory was cleaned up out of band.
        existing_record = await knowledge_base_service.get_by_user_and_name(current_user.id, kb_name)
        if existing_record is not None:
            raise HTTPException(status_code=409, detail=f"Knowledge base '{kb_name}' already exists")
        if kb_path.exists():
            # No DB row but a directory survives.  Two paths fork here:
            # the dir is a leftover from a previous failed delete (carries
            # the .kb_deleted sentinel) -- in which case the user clearly
            # wants to reuse the name -- vs. a legitimate orphan from a
            # legacy export.  Only the sentinel case is safe to repurpose.
            if KBStorageHelper.is_kb_dir_deleted(kb_path):
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Knowledge base '{kb_name}' was recently deleted but its on-disk files "
                        "are still being released by another process. Restart the server (or wait "
                        "for the lock to clear) before recreating it with the same name."
                    ),
                )
            raise HTTPException(status_code=409, detail=f"Knowledge base '{kb_name}' already exists")

        # Create KB directory.  Clear any leftover sentinel just in case
        # mkdir is racing with a sentinel write from a concurrent delete
        # of the same name; ``clear_deletion_sentinel`` is a no-op when
        # the marker is absent.
        kb_path.mkdir(parents=True, exist_ok=True)
        KBStorageHelper.clear_deletion_sentinel(kb_path)
        kb_id = uuid.uuid4()

        # Initialize Chroma storage and collection immediately
        # This ensures files exist for read operations and avoids 'readonly' errors later
        try:
            client = KBStorageHelper.get_fresh_chroma_client(kb_path)
            client.create_collection(name=kb_name, **chroma_client_create_collection_kwargs())
        except (OSError, ValueError, chromadb.errors.ChromaError) as e:
            logger.warning("Initial Chroma setup for %s failed: %s", kb_name, e)
        finally:
            client = None
            KBStorageHelper.release_chroma_resources(kb_path)

        # Serialize column_config for persistence
        column_config_dicts = None
        if request.column_config:
            column_config_dicts = [item.model_dump() for item in request.column_config]

        # Save full embedding metadata to prevent immediate backfill.
        # ``backend_type``/``backend_config`` are persisted here too so
        # a later ``backfill_from_disk`` reconstructs the correct
        # backend routing even if the DB write below fails.
        # ``backend_config`` holds only *variable names* (never raw
        # secrets) per the credential-indirection contract.
        backend_type_value = request.backend_type or "chroma"
        backend_config_value = request.backend_config or {}
        embedding_metadata = {
            "id": str(kb_id),
            "embedding_provider": request.embedding_provider,
            "embedding_model": request.embedding_model,
            "model_selection": request.model_selection,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "chunks": 0,
            "words": 0,
            "characters": 0,
            "avg_chunk_size": 0.0,
            "size": 0,
            "column_config": column_config_dicts,
            "backend_type": backend_type_value,
            "backend_config": backend_config_value,
        }
        metadata_path = kb_path / "embedding_metadata.json"
        metadata_path.write_text(json.dumps(embedding_metadata, indent=2))

        # Write schema.json for text-metric helpers (get_text_columns)
        if column_config_dicts:
            schema_data = [{**col, "data_type": "string"} for col in column_config_dicts]
            schema_path = kb_path / "schema.json"
            schema_path.write_text(json.dumps(schema_data, indent=2))

        # Dual-write: persist the identity + config to the DB alongside
        # the JSON file so older service versions still see the legacy
        # on-disk view, while new code reads from the DB first.
        #
        # The DB row is now authoritative for list/detail reads, so a
        # create that only reaches the filesystem is an inconsistent
        # partial success. Roll back the on-disk state and surface a
        # 500 regardless of backend type.
        try:
            # ``model_selection`` is the canonical source of truth for
            # embedding config; the request still carries
            # ``embedding_provider`` / ``embedding_model`` as flat
            # convenience fields (frontend back-compat) but those are
            # derived views — folded into ``model_selection`` here
            # when the request didn't carry one of its own.
            persisted_selection = request.model_selection or {
                "name": request.embedding_model,
                "provider": request.embedding_provider,
            }
            await knowledge_base_service.create_record(
                user_id=current_user.id,
                name=kb_name,
                model_selection=persisted_selection,
                column_config=column_config_dicts or [],
                backend_type=backend_type_value,
                backend_config=backend_config_value,
                record_id=kb_id,
            )
        except Exception as exc:
            await logger.aerror(
                "KB DB persist failed for backend %s (kb=%s): %s — rolling back",
                backend_type_value,
                kb_name,
                exc,
            )
            KBStorageHelper.delete_storage(kb_path, kb_name)
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Failed to persist knowledge base '{kb_name}' with backend '{backend_type_value}'. Please retry."
                ),
            ) from exc

        return KnowledgeBaseInfo(
            id=str(kb_id),
            dir_name=kb_name,
            name=kb_name.replace("_", " "),
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            size=0,
            words=0,
            characters=0,
            chunks=0,
            avg_chunk_size=0.0,
            status="empty",
            column_config=column_config_dicts,
            backend_type=backend_type_value,
            backend_config=backend_config_value,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Clean up if something went wrong
        if kb_path.exists():
            KBStorageHelper.delete_storage(kb_path, kb_name)
        await logger.aerror("Error creating knowledge base: %s", e)
        raise HTTPException(status_code=500, detail="Internal error creating knowledge base") from e


@router.post("/preview-chunks", status_code=HTTPStatus.OK)
async def preview_chunks(
    current_user: CurrentActiveUser,
    files: Annotated[list[UploadFile], File(description="Files to preview chunking for")],
    # Upper bounds cap the memory footprint of a preview request.
    # ``max_chunks * chunk_size * CHUNK_PREVIEW_MULTIPLIER`` is the
    # largest text slice this endpoint will hold in memory — without
    # these bounds, an authenticated user can request gigabytes.
    chunk_size: Annotated[int, Form(ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE)] = 1000,
    chunk_overlap: Annotated[int, Form(ge=MIN_CHUNK_OVERLAP, le=MAX_CHUNK_OVERLAP)] = 200,
    separator: Annotated[str, Form()] = "\n",
    max_chunks: Annotated[int, Form(ge=MIN_MAX_CHUNKS, le=MAX_MAX_CHUNKS)] = 5,
) -> dict[str, object]:
    """Preview how files will be chunked without storing anything.

    Uses the same RecursiveCharacterTextSplitter as the ingest endpoint
    so the preview accurately reflects what will be stored.
    """
    await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.CREATE, kb_name=None)
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Build separators list: user separator first, then defaults
        separators = None
        if separator:
            # Unescape common escape sequences
            actual_separator = separator.replace("\\n", "\n").replace("\\t", "\t")
            separators = [actual_separator, "\n\n", "\n", " ", ""]

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=separators,
        )

        file_previews: list[dict[str, Any]] = []
        for uploaded_file in files:
            try:
                file_content = await uploaded_file.read()
                file_name = uploaded_file.filename or "unknown"
                text_content = extract_text_from_bytes(file_name, file_content)

                if not text_content.strip():
                    file_previews.append(
                        {
                            "file_name": file_name,
                            "total_chunks": 0,
                            "preview_chunks": [],
                        }
                    )
                    continue

                # Only process enough text for the requested preview chunks
                # to avoid splitting the entire file (which is slow for large files)
                preview_text_limit = max_chunks * chunk_size * CHUNK_PREVIEW_MULTIPLIER
                preview_text = text_content[:preview_text_limit]
                chunks = text_splitter.split_text(preview_text)

                # Estimate total chunks from full text length
                effective_step = max(chunk_size - chunk_overlap, 1)
                estimated_total = max(
                    len(chunks),
                    int((len(text_content) - chunk_overlap) / effective_step),
                )

                # Track character positions for metadata
                preview_chunks = []
                position = 0
                for i, chunk in enumerate(chunks[:max_chunks]):
                    # Find the actual position of this chunk in the original text
                    chunk_start = text_content.find(chunk, position)
                    if chunk_start == -1:
                        chunk_start = position
                    chunk_end = chunk_start + len(chunk)

                    preview_chunks.append(
                        {
                            "content": chunk,
                            "index": i,
                            "char_count": len(chunk),
                            "start": chunk_start,
                            "end": chunk_end,
                        }
                    )
                    position = chunk_start + 1

                file_previews.append(
                    {
                        "file_name": file_name,
                        "total_chunks": estimated_total,
                        "preview_chunks": preview_chunks,
                    }
                )

            except (OSError, ValueError, TypeError) as file_error:
                logger.warning("Error previewing file %s: %s", uploaded_file.filename, file_error)
                file_previews.append(
                    {
                        "file_name": uploaded_file.filename or "unknown",
                        "total_chunks": 0,
                        "preview_chunks": [],
                    }
                )

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error previewing chunks: %s", e)
        raise HTTPException(status_code=500, detail="Error previewing chunks.") from e
    else:
        return {"files": file_previews}


@router.post("/{kb_name}/ingest", status_code=HTTPStatus.OK, dependencies=[Depends(_check_memory_base_association)])
async def ingest_files_to_knowledge_base(
    kb_name: str,
    current_user: CurrentActiveUser,
    files: Annotated[list[UploadFile], File(description="Files to ingest into the knowledge base")],
    source_name: Annotated[str, Form()] = "",
    # Mirrors the bounds on ``preview_chunks`` so ingestion can't be
    # used to bypass the memory-footprint cap.
    chunk_size: Annotated[int, Form(ge=MIN_CHUNK_SIZE, le=MAX_CHUNK_SIZE)] = 1000,
    chunk_overlap: Annotated[int, Form(ge=MIN_CHUNK_OVERLAP, le=MAX_CHUNK_OVERLAP)] = 200,
    separator: Annotated[str, Form()] = "",
    column_config: Annotated[str, Form()] = "",
    metadata: Annotated[
        str,
        Form(description="JSON object of run-level user metadata applied to every chunk."),
    ] = "",
    per_file_metadata: Annotated[
        str,
        Form(description="JSON object keyed by filename mapping to per-file metadata overrides."),
    ] = "",
) -> dict[str, object] | TaskResponse:
    """Upload and ingest files directly into a knowledge base.

    This endpoint:
    1. Accepts file uploads
    2. Extracts text and chunks the content
    3. Creates embeddings using the KB's configured embedding model
    4. Stores the vectors in the knowledge base

    User-supplied metadata flows through two channels:

    * ``metadata`` — applied to every chunk produced by this run.
    * ``per_file_metadata`` — overrides keyed by filename; merged on top of
      the run-level dict, with per-file keys winning on collision.

    Both are validated server-side; reserved keys + oversized values raise 422
    so the UI can surface the rejection inline.
    """
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.INGEST, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    try:
        settings = get_settings_service().settings
        max_file_size_upload = settings.max_file_size_upload

        # Parse + validate metadata before reading any file bytes so a bad
        # metadata payload fails fast with 422 instead of paying the upload
        # cost first.
        run_metadata = parse_user_metadata(metadata)
        per_file_metadata_dict = parse_per_file_metadata(per_file_metadata)

        files_data = []

        for uploaded_file in files:
            file_size = uploaded_file.size
            if file_size > max_file_size_upload * 1024 * 1024:
                raise HTTPException(
                    status_code=413,
                    detail=f"File {uploaded_file.filename} exceeds the maximum upload size of {max_file_size_upload}MB",
                )
            content = await uploaded_file.read()
            files_data.append((uploaded_file.filename or "unknown", content))

        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)

        # Parse and persist column_config from FormData if provided
        if column_config:
            try:
                column_config_parsed = json.loads(column_config)
                if isinstance(column_config_parsed, list):
                    # Update embedding_metadata.json
                    cc_metadata_path = kb_path / "embedding_metadata.json"
                    if cc_metadata_path.exists():
                        existing_meta = json.loads(cc_metadata_path.read_text())
                        existing_meta["column_config"] = column_config_parsed
                        cc_metadata_path.write_text(json.dumps(existing_meta, indent=2))
                    # Write schema.json for text-metric helpers
                    schema_data = [{**col, "data_type": "string"} for col in column_config_parsed]
                    schema_path = kb_path / "schema.json"
                    schema_path.write_text(json.dumps(schema_data, indent=2))
            except (json.JSONDecodeError, TypeError):
                await logger.awarning("Malformed column_config received, using existing schema")

        # Read embedding metadata (Pass fast=False to ensure legacy KBs are migrated/detected)
        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=False)
        if not metadata:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base missing embedding configuration. Please create a new KB or reconfigure it.",
            )

        # ``model_selection`` is the canonical embedding-config payload.
        # Synthesize it from the legacy flat metadata fields when older
        # KBs only carry those (``record_to_metadata_dict`` writes both
        # forms for new KBs, so this branch is mainly for disk-only
        # ones that haven't been backfilled yet).
        model_selection = metadata.get("model_selection") or {
            "name": metadata.get("embedding_model"),
            "provider": metadata.get("embedding_provider"),
        }
        if not model_selection.get("name") or not model_selection.get("provider"):
            raise HTTPException(status_code=400, detail="Invalid embedding configuration")

        # Use ``KnowledgeBaseRecord.id`` (when present) as the Job's
        # ``asset_id`` so the read path can hit the indexed
        # ``Job.asset_id`` column instead of doing a JSON-extract on
        # ``Job.job_metadata.kb_name``. Falls back to legacy
        # ``metadata['id']`` for KBs that exist on disk only.
        asset_id = await _resolve_kb_asset_id(
            kb_name=kb_name,
            current_user=current_user,
            metadata=metadata,
        )

        # Get services and create job before async/sync split
        job_service = get_job_service()
        job_id = uuid.uuid4()

        # Create job record in database for both async and sync paths
        await job_service.create_job(
            job_id=job_id,
            flow_id=job_id,
            job_type=JobType.INGESTION,
            asset_id=asset_id,
            asset_type="knowledge_base",
            user_id=current_user.id,
        )

        # Always use async path: fire and forget the ingestion logic wrapped in status updates
        task_service = get_task_service()
        await task_service.fire_and_forget_task(
            job_service.execute_with_status,
            job_id=job_id,
            run_coro_func=KBIngestionHelper.perform_ingestion,
            kb_name=kb_name,
            kb_path=kb_path,
            files_data=files_data,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separator=separator,
            source_name=source_name,
            current_user=current_user,
            model_selection=model_selection,
            task_job_id=job_id,
            job_service=job_service,
            source_metadata=run_metadata or None,
            per_file_metadata=per_file_metadata_dict or None,
        )
        return TaskResponse(id=str(job_id), href=f"/task/{job_id}")

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error ingesting files to knowledge base: %s", e)
        raise HTTPException(status_code=500, detail="Error ingesting files to knowledge base.") from e


class IngestFolderRequest(BaseModel):
    """Body payload for ``POST /{kb_name}/ingest/folder``.

    Path is expanded (``~`` → user home) and resolved before being
    checked against the settings allow-list. ``extensions`` and
    ``max_file_size_bytes`` are optional — unset means "use the
    FolderSource defaults".
    """

    path: str = Field(..., description="Absolute or ~-expanded directory to walk.")
    recursive: bool = Field(default=True, description="Walk subdirectories as well.")
    extensions: list[str] | None = Field(
        None,
        description="Lowercase extensions without dot. None → defaults (txt, md, pdf, docx, …).",
    )
    max_file_size_bytes: int | None = Field(None, description="Per-file size cap; None → 25 MB default.")
    source_name: str = Field("", description="Optional grouping label stamped on every chunk's 'source'.")
    chunk_size: int = Field(
        1000,
        ge=MIN_CHUNK_SIZE,
        le=MAX_CHUNK_SIZE,
        description="Chunk size in characters.",
    )
    chunk_overlap: int = Field(
        200,
        ge=MIN_CHUNK_OVERLAP,
        le=MAX_CHUNK_OVERLAP,
        description="Chunk overlap in characters.",
    )
    separator: str = Field("", description="Custom separator (\\n → newline).")
    metadata: dict[str, Any] | None = Field(
        None,
        description="Run-level user metadata applied to every chunk. Same rules as the upload endpoint.",
    )
    per_file_metadata: dict[str, dict[str, Any]] | None = Field(
        None,
        description="Per-file metadata overrides keyed by absolute path or basename.",
    )


@router.post(
    "/{kb_name}/ingest/folder",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(_check_memory_base_association)],
)
async def ingest_folder_to_knowledge_base(
    kb_name: str,
    current_user: CurrentActiveUser,
    payload: IngestFolderRequest,
) -> TaskResponse:
    """Ingest every matching file from a server-side folder.

    Uses ``FolderSource`` with the allow-list configured in
    ``settings.kb_allowed_folder_roots`` (defaults to an empty list —
    operators must opt in). The resolved path must be equal to or
    inside one of those roots — symlink escapes are blocked because
    ``Path.resolve()`` is applied before the containment check.

    Returns a ``TaskResponse`` pointing at the ingestion job; track it
    via ``/task/{id}`` or the ``GET /{kb_name}`` endpoint.
    """
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.INGEST, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    try:
        settings = get_settings_service().settings
        allowed_roots = settings.kb_allowed_folder_roots or []

        # Validate user-supplied metadata before resolving the KB path so a
        # malformed payload responds with 422 rather than 404 if the KB name
        # also happens to be wrong.
        from langflow.api.utils.kb_metadata import (
            validate_user_metadata as _validate_user_metadata,
        )

        run_user_metadata: dict[str, Any] = {}
        if payload.metadata:
            run_user_metadata = _validate_user_metadata(dict(payload.metadata))
        per_file_user_metadata: dict[str, dict[str, Any]] = {}
        if payload.per_file_metadata:
            for filename, file_meta in payload.per_file_metadata.items():
                if not isinstance(filename, str) or not filename:
                    raise HTTPException(
                        status_code=422,
                        detail="Per-file metadata keys must be non-empty filename strings.",
                    )
                per_file_user_metadata[filename] = _validate_user_metadata(dict(file_meta or {}))

        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)
        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=False)
        if not metadata:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base missing embedding configuration. Please create a new KB or reconfigure it.",
            )

        model_selection = metadata.get("model_selection") or {
            "name": metadata.get("embedding_model"),
            "provider": metadata.get("embedding_provider"),
        }
        if not model_selection.get("name") or not model_selection.get("provider"):
            raise HTTPException(status_code=400, detail="Invalid embedding configuration")

        asset_id = await _resolve_kb_asset_id(
            kb_name=kb_name,
            current_user=current_user,
            metadata=metadata,
        )

        # Build + validate the folder source up-front so invalid
        # configurations surface as a 4xx response before a background
        # job is spawned.
        source_config: dict[str, Any] = {
            "path": payload.path,
            "recursive": payload.recursive,
            "allowed_roots": allowed_roots,
        }
        if payload.extensions is not None:
            source_config["extensions"] = payload.extensions
        if payload.max_file_size_bytes is not None:
            source_config["max_file_size_bytes"] = payload.max_file_size_bytes
        if per_file_user_metadata:
            source_config["per_file_metadata"] = per_file_user_metadata

        folder_source = FolderSource(user_id=current_user.id, source_config=source_config)
        try:
            await folder_source.validate_config()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        job_service = get_job_service()
        job_id = uuid.uuid4()

        await job_service.create_job(
            job_id=job_id,
            flow_id=job_id,
            job_type=JobType.INGESTION,
            asset_id=asset_id,
            asset_type="knowledge_base",
            user_id=current_user.id,
        )

        task_service = get_task_service()
        await task_service.fire_and_forget_task(
            job_service.execute_with_status,
            job_id=job_id,
            run_coro_func=KBIngestionHelper.perform_ingestion,
            kb_name=kb_name,
            kb_path=kb_path,
            files_data=None,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
            separator=payload.separator,
            source_name=payload.source_name,
            current_user=current_user,
            model_selection=model_selection,
            task_job_id=job_id,
            job_service=job_service,
            source=folder_source,
            source_metadata=run_user_metadata or None,
        )
        return TaskResponse(id=str(job_id), href=f"/task/{job_id}")

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error ingesting folder to knowledge base: %s", e)
        raise HTTPException(status_code=500, detail="Error ingesting folder to knowledge base.") from e


@router.get("", status_code=HTTPStatus.OK)
@router.get("/", status_code=HTTPStatus.OK)
async def list_knowledge_bases(
    current_user: CurrentActiveUser,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> list[KnowledgeBaseInfo]:
    """List all available knowledge bases.

    Reads from ``knowledge_base`` rows first. A disk scan is only used
    as a recovery fallback when the user has no KB rows yet.
    """
    # List-level guard: a viewer-role user may still see the KBs they own,
    # but a role with ``knowledge_base:read`` revoked entirely is rejected
    # here. Per-row filtering is the authorization plugin's responsibility once
    # KB share grants exist.
    await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.READ, kb_name=None)
    try:
        kb_root_path = KBStorageHelper.get_root_path()
        # Resolve + containment-check on par with every other path
        # construction in this file. A username containing path
        # separators (from a compromised token, or a weird legacy
        # account) would otherwise escape the root directory.
        kb_user_path = (kb_root_path / current_user.username).resolve()
        _validate_kb_path_containment(
            kb_root_path.resolve(), kb_user_path, current_user.username, current_user.username
        )
        kb_path = kb_user_path

        knowledge_bases: list[KnowledgeBaseInfo] = []
        kb_ids_to_fetch: list[uuid.UUID] = []

        rows = await knowledge_base_service.list_by_user(current_user.id)

        if rows:
            for row in rows:
                metadata = knowledge_base_service.record_to_metadata_dict(row)
                # Skip KBs that are managed by a Memory Base — those are
                # exposed through the Memory Base APIs, not the generic KB list.
                if _is_memory_base_associated(metadata):
                    continue
                kb_ids_to_fetch.append(row.id)
                knowledge_bases.append(
                    _build_kb_info(
                        kb_name=row.name.replace("_", " "),
                        dir_name=row.name,
                        metadata=metadata,
                        size=row.size_bytes,
                    )
                )
        elif kb_path.exists():
            # Recovery-only fallback for legacy/exported KB directories
            # that have not been reconciled into the DB yet.
            for kb_dir in kb_path.iterdir():
                if not kb_dir.is_dir() or kb_dir.name.startswith("."):
                    continue
                # Skip dirs whose row was deleted but whose bytes survived
                # a locked-file rmtree.  Without this, a 0-row user (which
                # is what triggers the disk-fallback path) would re-surface
                # a "deleted" KB they previously cleaned up.
                if KBStorageHelper.is_kb_dir_deleted(kb_dir):
                    continue
                try:
                    metadata = knowledge_base_service.load_metadata_from_disk(kb_dir)
                    kb_id_str = metadata.get("id")
                    if kb_id_str:
                        with suppress(ValueError, AttributeError, TypeError):
                            kb_ids_to_fetch.append(uuid.UUID(str(kb_id_str)))

                    knowledge_bases.append(
                        _build_kb_info(
                            kb_name=kb_dir.name.replace("_", " "),
                            dir_name=kb_dir.name,
                            metadata=metadata,
                            size=KBStorageHelper.get_directory_size(kb_dir),
                        )
                    )
                except OSError:
                    await logger.aexception("Error reading knowledge base directory '%s'", kb_dir)
                    continue

        # Second pass: Batch fetch all job statuses in a single query
        if kb_ids_to_fetch:
            latest_jobs = await job_service.get_latest_jobs_by_asset_ids(kb_ids_to_fetch)

            # Map job statuses back to knowledge bases
            # Normalize to frontend-expected values: ready, ingesting, failed, empty
            job_status_map = {
                "queued": "ingesting",
                "in_progress": "ingesting",
                "failed": "failed",
                "cancelled": "failed",
                "timed_out": "failed",
            }
            for kb_info in knowledge_bases:
                try:
                    kb_uuid = uuid.UUID(kb_info.id)
                    if kb_uuid in latest_jobs:
                        job = latest_jobs[kb_uuid]
                        raw_status = job.status.value if hasattr(job.status, "value") else str(job.status)
                        mapped = job_status_map.get(raw_status)
                        if mapped:
                            kb_info.status = mapped
                        # For "completed", keep the file-marker / chunk-count status already set
                        kb_info.last_job_id = str(job.job_id)
                except (ValueError, AttributeError):
                    # If KB ID is not a valid UUID, skip job status update
                    pass

    except Exception as e:
        await logger.aerror("Error listing knowledge bases: %s", e)
        raise HTTPException(status_code=500, detail="Error listing knowledge bases.") from e
    else:
        return knowledge_bases


@router.get("/connectors", status_code=HTTPStatus.OK)
async def list_connectors(_current_user: CurrentActiveUser) -> list[ConnectorCatalogEntry]:
    """Enumerate registered connector sources for the UI picker.

    Declared before the ``GET /{kb_name}`` route so FastAPI matches
    the literal ``/connectors`` path first rather than treating it
    as a ``kb_name`` parameter. Skips ``file_upload`` because that
    path is wired through the dedicated upload modal.
    """
    entries: list[ConnectorCatalogEntry] = []
    for source_type in registered_sources():
        if source_type is SourceType.FILE_UPLOAD:
            continue
        try:
            source_cls = get_source_class(source_type)
        except ValueError:
            continue
        entries.append(
            ConnectorCatalogEntry(
                source_type=source_type.value,
                display_name=getattr(source_cls, "display_name", source_type.value),
                description=getattr(source_cls, "description", "") or "",
                icon=getattr(source_cls, "icon", None),
                requires_credentials=bool(getattr(source_cls, "requires_credentials", False)),
            )
        )
    return entries


@router.get("/{kb_name}", status_code=HTTPStatus.OK, dependencies=[Depends(_check_memory_base_association)])
async def get_knowledge_base(kb_name: str, current_user: CurrentActiveUser) -> KnowledgeBaseInfo:
    """Get detailed information about a specific knowledge base."""
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.READ, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    try:
        # Use the resolved owner — a non-owner reaching this route via a
        # share grant must see the owner's KB row, not their own same-named.
        record = _kb_guard.record or await knowledge_base_service.get_by_user_and_name(_kb_guard.owner_user.id, kb_name)
        if record is not None:
            return _build_kb_info(
                kb_name=record.name.replace("_", " "),
                dir_name=record.name,
                metadata=knowledge_base_service.record_to_metadata_dict(record),
                size=record.size_bytes,
            )

        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)
        metadata = knowledge_base_service.load_metadata_from_disk(kb_path)
        return _build_kb_info(
            kb_name=kb_name.replace("_", " "),
            dir_name=kb_name,
            metadata=metadata,
            size=KBStorageHelper.get_directory_size(kb_path),
        )

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error getting knowledge base '%s': %s", kb_name, e)
        raise HTTPException(status_code=500, detail="Error getting knowledge base.") from e


@router.get("/{kb_name}/chunks", status_code=HTTPStatus.OK, dependencies=[Depends(_check_memory_base_association)])
async def get_knowledge_base_chunks(
    kb_name: str,
    current_user: CurrentActiveUser,
    request: Request,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str, Query(description="Filter chunks whose text contains this substring")] = "",
    source_type: Annotated[
        str | None,
        Query(description="Only return chunks ingested via the given source type (e.g. 'file_upload', 'folder')."),
    ] = None,
    file_name: Annotated[
        str | None,
        Query(description="Only return chunks whose source filename exactly matches."),
    ] = None,
    job_id: Annotated[
        str | None,
        Query(description="Only return chunks written by the given ingestion job_id."),
    ] = None,
) -> PaginatedChunkResponse:
    """Get chunks from a specific knowledge base with pagination.

    The ``source_type`` / ``file_name`` / ``job_id`` filters map
    directly onto the metadata keys every chunk receives at ingestion
    time, so a UI can drill from a run row down to the chunks that run
    produced without pulling the whole collection into memory.

    Repeating ``meta_<key>=<value>`` query params filters chunks by
    user-supplied tags. A chunk matches when every key is present in its
    ``source_metadata`` and the value compares equal (for primitives) or
    overlaps (when the stored value is an array). Multiple keys AND;
    repeating the same key OR-s the values for that key, allowing
    multi-select chips in the UI without re-encoding into JSON.

    Filtering runs client-side on the iterated chunk stream — every
    supported backend has a different filter dialect, so a uniform
    Python pass keeps behaviour consistent across Chroma / OpenSearch /
    future backends.

    Note: a JSON-blob ``metadata_filter`` query param would be more
    ergonomic, but this router sits behind a global query-string
    flatten-on-comma middleware that would split a JSON object value at
    every comma. Repeated key=value params side-step that without
    invasive middleware changes.
    """
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.READ, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    kb_path: Path | None = None
    backend = None
    backend_type_value: str = BackendType.CHROMA.value
    try:
        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)

        # Backend selection + construction must resolve against the KB owner
        # so remote-backed shared KBs read the owner's credential variables,
        # not the actor's (the actor often has none of the right vars).
        backend_type_value, backend_config = await _resolve_backend_selection(
            kb_name=kb_name,
            kb_path=kb_path,
            current_user=_kb_guard.owner_user,
        )

        # Local-Chroma short-circuit: if the KB lives on disk and has no
        # files yet, return empty without booting a Chroma client (which
        # would otherwise hit 'readonly database' on the empty dir).
        # Cloud KBs store nothing locally, so this check must be skipped for them.
        chroma_mode = str((backend_config or {}).get("mode", "local")).lower()
        if backend_type_value == BackendType.CHROMA.value and chroma_mode != "cloud":
            has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
            if not has_data:
                return PaginatedChunkResponse(
                    chunks=[],
                    total=0,
                    page=page,
                    limit=limit,
                    total_pages=0,
                )

        backend = create_backend(
            backend_type_value,
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            user_id=_kb_guard.owner_user.id,
        )

        search_term = search.strip().lower()

        # Build a {key: [values...]} dict from every ``meta_<key>=<value>``
        # query param. Multiple values for the same key form an OR set;
        # different keys AND together at match time.
        metadata_filter_dict: dict[str, list[str]] = {}
        for key, value in request.query_params.multi_items():
            if not key.startswith("meta_"):
                continue
            metadata_key = key[len("meta_") :]
            if not metadata_key:
                continue
            metadata_filter_dict.setdefault(metadata_key, []).append(value)

        def _user_metadata_matches(meta: dict[str, Any]) -> bool:
            if not metadata_filter_dict:
                return True
            # ``source_metadata`` is stored as a JSON string on each chunk
            # so the value space stays portable across vector stores
            # whose metadata APIs only accept primitive values.
            raw = meta.get("source_metadata")
            if not raw:
                return False
            try:
                stored = json.loads(raw) if isinstance(raw, str) else raw
            except json.JSONDecodeError:
                return False
            if not isinstance(stored, dict):
                return False
            for key, expected_values in metadata_filter_dict.items():
                # Compare as strings — query-string values are always strings
                # while stored metadata may be a number, bool, or list. Casting
                # both sides keeps the contract simple ("tag=invoice" matches
                # whether stored as string or in a string array).
                actual = stored.get(key)
                if actual is None:
                    return False
                actual_set = {str(entry) for entry in actual} if isinstance(actual, list) else {str(actual)}
                expected_set = {str(value) for value in expected_values}
                if not actual_set & expected_set:
                    return False
            return True

        def matches_filters(metadata: dict[str, Any] | None, content: str) -> bool:
            meta = metadata or {}
            if source_type and meta.get("source_type") != source_type:
                return False
            if file_name and meta.get("file_name") != file_name:
                return False
            if job_id and meta.get("job_id") != job_id:
                return False
            if not _user_metadata_matches(meta):
                return False
            return not (search_term and search_term not in (content or "").lower())

        # Stream through the backend and filter in Python. The vector
        # stores don't share a filter DSL (Chroma's ``where`` vs Mongo
        # query documents vs Astra's Data API vs PGVector JSONB), so a
        # uniform client-side pass is the only path that works for all
        # four. KB chunk browsers operate on bounded collections — a
        # full iteration is acceptable here.
        offset = (page - 1) * limit
        matched: list[tuple[str, str, dict[str, Any]]] = []
        matched_count = 0
        try:
            async for batch in backend.iter_documents():
                for entry in batch:
                    if not matches_filters(entry.metadata, entry.content):
                        continue
                    entry_id = (
                        entry.metadata.get("_id") or entry.metadata.get("id") or entry.metadata.get("chunk_id") or ""
                    )
                    # Only materialize entries inside the requested page; we
                    # still have to count past them for ``total_pages``.
                    if offset <= matched_count < offset + limit:
                        matched.append((entry_id, entry.content, dict(entry.metadata)))
                    matched_count += 1
        except Exception as iter_error:
            await logger.aerror("iter_documents failed for '%s': %s", kb_name, iter_error)
            raise HTTPException(status_code=500, detail="Error getting chunks.") from iter_error

        chunks = [
            ChunkInfo(id=doc_id, content=content, char_count=len(content or ""), metadata=metadata)
            for doc_id, content, metadata in matched
        ]
        return PaginatedChunkResponse(
            chunks=chunks,
            total=matched_count,
            page=page,
            limit=limit,
            total_pages=(matched_count + limit - 1) // limit if matched_count > 0 else 0,
        )

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error getting chunks for '%s': %s", kb_name, e)
        raise HTTPException(status_code=500, detail="Error getting chunks.") from e
    finally:
        if backend is not None:
            try:
                await backend.teardown()
            except Exception as teardown_exc:  # noqa: BLE001
                # Surface at debug level so teardown failures stay
                # visible without masking the original error path.
                await logger.adebug("Backend teardown failed: %s", teardown_exc)
        # ``release_chroma_resources`` clears Chroma's shared
        # ``SharedSystemClient`` registry entry. Calling it for a
        # MongoDB/Astra/Postgres-backed KB would mutate that registry
        # for unrelated Chroma KBs served from the same path.
        if kb_path is not None and backend_type_value == BackendType.CHROMA.value:
            KBStorageHelper.release_chroma_resources(kb_path)


@router.get(
    "/{kb_name}/metadata/keys",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(_check_memory_base_association)],
)
async def get_knowledge_base_metadata_keys(
    kb_name: str,
    current_user: CurrentActiveUser,
) -> KbMetadataKeysResponse:
    """List distinct user-supplied metadata keys (and a sample of values) for a KB.

    Powers the chunks-browser filter popover so users can pick from keys
    that actually exist in the KB instead of typing blind.

    Reserved ingestion-internal keys (``file_name``, ``source``, ``job_id``,
    etc.) are excluded — those have dedicated filters on the chunks endpoint
    and would clutter the user-tag dropdown.

    Iterates the chunk stream once and dedupes per key. Distinct value sets
    are capped at ``KB_METADATA_KEYS_VALUES_CAP`` per key to keep the popover
    dropdown usable when a key has unbounded free-form values; the response
    sets ``truncated=true`` so the UI can surface a "showing first N values"
    hint. Native distinct queries are deferred to backend-specific work
    (same trade-off as the chunks-endpoint post-filter pass).
    """
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.READ, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    kb_path: Path | None = None
    backend = None
    backend_type_value: str = BackendType.CHROMA.value
    try:
        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)

        # Backend selection + construction must use the KB owner so
        # remote-backed shared KBs read the owner's credential variables.
        backend_type_value, backend_config = await _resolve_backend_selection(
            kb_name=kb_name,
            kb_path=kb_path,
            current_user=_kb_guard.owner_user,
        )

        # Local-Chroma short-circuit: empty KB without a Chroma store on
        # disk would otherwise hit 'readonly database' on the empty dir.
        if backend_type_value == BackendType.CHROMA.value:
            has_data = any((kb_path / m).exists() for m in ["chroma", "chroma.sqlite3", "index"])
            if not has_data:
                return KbMetadataKeysResponse(keys={}, truncated=False)

        backend = create_backend(
            backend_type_value,
            kb_name=kb_name,
            kb_path=kb_path,
            backend_config=backend_config,
            user_id=_kb_guard.owner_user.id,
        )

        # Per-key ordered set of stringified distinct values. Insertion
        # order is preserved so the UI dropdown shows values in the order
        # they were first ingested rather than a hash-shuffled order.
        distinct: dict[str, dict[str, None]] = {}
        truncated = False
        try:
            async for batch in backend.iter_documents(batch_size=1000):
                for entry in batch:
                    raw = (entry.metadata or {}).get("source_metadata")
                    if not raw:
                        continue
                    try:
                        stored = json.loads(raw) if isinstance(raw, str) else raw
                    except json.JSONDecodeError:
                        continue
                    if not isinstance(stored, dict):
                        continue
                    for key, value in stored.items():
                        if key in KB_METADATA_RESERVED_KEYS:
                            continue
                        bucket = distinct.setdefault(key, {})
                        # Array-valued metadata expands into one distinct value
                        # per array entry so the popover dropdown shows every
                        # tag that could be filtered on.
                        candidates = value if isinstance(value, list) else [value]
                        for candidate in candidates:
                            if candidate is None:
                                continue
                            stringified = str(candidate)
                            if stringified in bucket:
                                continue
                            if len(bucket) >= KB_METADATA_KEYS_VALUES_CAP:
                                truncated = True
                                break
                            bucket[stringified] = None
        except Exception as iter_error:
            await logger.aerror("iter_documents failed while listing metadata keys for '%s': %s", kb_name, iter_error)
            raise HTTPException(status_code=500, detail="Error listing metadata keys.") from iter_error

        return KbMetadataKeysResponse(
            keys={key: list(values.keys()) for key, values in sorted(distinct.items())},
            truncated=truncated,
        )

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error listing metadata keys for '%s': %s", kb_name, e)
        raise HTTPException(status_code=500, detail="Error listing metadata keys.") from e
    finally:
        if backend is not None:
            try:
                await backend.teardown()
            except Exception as teardown_exc:  # noqa: BLE001
                await logger.adebug("Backend teardown failed: %s", teardown_exc)
        if kb_path is not None and backend_type_value == BackendType.CHROMA.value:
            KBStorageHelper.release_chroma_resources(kb_path)


@router.post(
    "/{kb_name}/ingest/connector",
    status_code=HTTPStatus.OK,
    dependencies=[Depends(_check_memory_base_association)],
)
async def ingest_via_connector(
    kb_name: str,
    payload: ConnectorIngestRequest,
    current_user: CurrentActiveUser,
) -> TaskResponse:
    """Generic connector-driven ingestion dispatcher.

    Accepts a ``source_type`` string + ``source_config`` dict,
    instantiates the matching source via the registry, validates its
    config (surfaces credential / config errors as 400 before the job
    is spawned), then hands off to the same async ingestion machinery
    file-upload + folder already use.
    """
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.INGEST, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    try:
        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)

        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=False)
        if not metadata:
            raise HTTPException(
                status_code=400,
                detail="Knowledge base missing embedding configuration. Please create a new KB or reconfigure it.",
            )
        model_selection = metadata.get("model_selection") or {
            "name": metadata.get("embedding_model"),
            "provider": metadata.get("embedding_provider"),
        }
        if not model_selection.get("name") or not model_selection.get("provider"):
            raise HTTPException(status_code=400, detail="Invalid embedding configuration")
        asset_id = await _resolve_kb_asset_id(
            kb_name=kb_name,
            current_user=current_user,
            metadata=metadata,
        )

        try:
            source = create_source(
                payload.source_type,
                user_id=current_user.id,
                source_config=payload.source_config,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        try:
            await source.validate_config()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # Build an idempotency key over (user, kb, source, config) so
        # that a double-click on "Ingest" doesn't spawn two jobs for
        # the same connector target. ``JobService.create_job`` (see
        # #12417) rejects duplicates with a ``DuplicateJobError`` when
        # a prior QUEUED/IN_PROGRESS/COMPLETED job carries the same
        # dedupe_key; FAILED/CANCELLED jobs remain retryable.
        dedupe_key = _build_connector_ingest_dedupe_key(
            user_id=current_user.id,
            kb_name=kb_name,
            source_type=payload.source_type,
            source_config=payload.source_config,
        )

        job_service = get_job_service()
        job_id = uuid.uuid4()
        try:
            await job_service.create_job(
                job_id=job_id,
                flow_id=job_id,
                job_type=JobType.INGESTION,
                asset_id=asset_id,
                asset_type="knowledge_base",
                user_id=current_user.id,
                dedupe_key=dedupe_key,
            )
        except DuplicateJobError as exc:
            raise HTTPException(
                status_code=HTTPStatus.CONFLICT,
                detail=(
                    "An ingestion for this connector target is already "
                    "queued or running. Wait for it to finish before "
                    "starting another."
                ),
            ) from exc

        task_service = get_task_service()
        await task_service.fire_and_forget_task(
            job_service.execute_with_status,
            job_id=job_id,
            run_coro_func=KBIngestionHelper.perform_ingestion,
            kb_name=kb_name,
            kb_path=kb_path,
            files_data=None,
            chunk_size=payload.chunk_size,
            chunk_overlap=payload.chunk_overlap,
            separator=payload.separator,
            source_name=payload.source_name,
            current_user=current_user,
            model_selection=model_selection,
            task_job_id=job_id,
            job_service=job_service,
            source=source,
        )
        return TaskResponse(id=str(job_id), href=f"/task/{job_id}")

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error ingesting via connector to KB: %s", e)
        raise HTTPException(status_code=500, detail="Error ingesting via connector.") from e


@router.get("/{kb_name}/runs", status_code=HTTPStatus.OK)
async def list_ingestion_runs(
    kb_name: str,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> PaginatedIngestionRunResponse:
    """Paginated list of ingestion runs for a KB (newest first).

    Scoped to the requesting user so one account can't observe
    another's run history. Returns counter-only rows; the UI fetches
    the detail endpoint for the drill-down.
    """
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.READ, kb_name=kb_name)
    # Verify the KB path exists + traversal-safe before exposing run
    # history — otherwise a crafted ``kb_name`` could be used to probe
    # for other users' KB existence by timing list_runs_for_kb.
    _resolve_kb_path(kb_name, _kb_guard.owner_user)

    rows, total = await ingestion_run_service.list_runs_for_kb(
        kb_name=kb_name,
        user_id=_kb_guard.owner_user.id,
        page=page,
        limit=limit,
    )
    runs = [_run_row_to_info(row) for row in rows]
    total_pages = (total + limit - 1) // limit if total > 0 else 0
    return PaginatedIngestionRunResponse(
        runs=runs,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
    )


@router.get("/{kb_name}/runs/{run_id}", status_code=HTTPStatus.OK)
async def get_ingestion_run(
    kb_name: str,
    run_id: uuid.UUID,
    current_user: CurrentActiveUser,
) -> IngestionRunDetail:
    """Full run detail including per-item breakdown + error messages."""
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.READ, kb_name=kb_name)
    _resolve_kb_path(kb_name, _kb_guard.owner_user)

    row = await ingestion_run_service.get_run(run_id, user_id=_kb_guard.owner_user.id)
    if row is None or row.kb_name != kb_name:
        raise HTTPException(status_code=404, detail="Ingestion run not found.")

    base = _run_row_to_info(row)
    items = [
        IngestionRunItemInfo(
            item_id=item.get("item_id", ""),
            display_name=item.get("display_name", ""),
            status=item.get("status", "succeeded"),
            chunks_created=int(item.get("chunks_created", 0) or 0),
            error_message=item.get("error_message"),
        )
        for item in (row.items or [])
    ]
    return IngestionRunDetail(
        **base.model_dump(),
        source_config=row.source_config or {},
        items=items,
    )


def _run_row_to_info(row) -> IngestionRunInfo:
    """Translate a ``RunRow`` projection into the list-response shape.

    Source rows used to come from the ``ingestion_run`` table; they
    now come from a ``RunRow`` dataclass projected from
    ``Job`` + ``Job.job_metadata``. Field names are unchanged so the
    ``IngestionRunInfo`` Pydantic shape (and the frontend that reads
    it) doesn't move.

    ``user_metadata`` is read defensively because legacy job rows
    written before the user-metadata work was merged may not have the
    key on their ``job_metadata`` blob.
    """
    user_metadata = getattr(row, "user_metadata", None) or {}
    source_config = getattr(row, "source_config", None) or {}
    raw_source_name = source_config.get("source_name")
    source_name = raw_source_name.strip() if isinstance(raw_source_name, str) and raw_source_name.strip() else None
    return IngestionRunInfo(
        id=str(row.id),
        kb_name=row.kb_name,
        kb_id=str(row.kb_id) if row.kb_id else None,
        job_id=str(row.job_id) if row.job_id else None,
        source_type=row.source_type,
        source_name=source_name,
        status=row.status,
        error_message=row.error_message,
        total_items=row.total_items,
        succeeded=row.succeeded,
        failed=row.failed,
        skipped=row.skipped,
        total_bytes=row.total_bytes,
        chunks_created=row.chunks_created,
        started_at=row.started_at,
        finished_at=row.finished_at,
        user_metadata=user_metadata,
    )


@router.delete("/{kb_name}", status_code=HTTPStatus.OK, dependencies=[Depends(_check_memory_base_association)])
async def delete_knowledge_base(
    kb_name: str,
    current_user: CurrentActiveUser,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> dict[str, str]:
    """Delete a specific knowledge base."""
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.DELETE, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    # All KB data lives in the owner's namespace (disk path, DB row, remote
    # collection, in-flight job). Route the cleanup helpers through the
    # owner so a non-owner with a delete share grant actually clears the
    # owner's resources, not their own.
    kb_owner = _kb_guard.owner_user
    try:
        try:
            kb_path = _resolve_kb_path(kb_name, kb_owner)
        except HTTPException as exc:
            # The local directory is gone but a DB row may still be
            # dangling (remote-backed KBs created without a sidecar,
            # or a partially-cleaned-up delete from a prior attempt).
            # Fall through to an orphan-row cleanup so the UI stops
            # showing the KB.
            if exc.status_code != HTTPStatus.NOT_FOUND:
                raise
            handled, orphan_warning = await _cleanup_orphan_db_row(
                kb_name=kb_name,
                current_user=kb_owner,
            )
            if not handled:
                raise
            response: dict[str, str] = {"message": f"Knowledge base '{kb_name}' deleted successfully"}
            if orphan_warning:
                response["warning"] = orphan_warning
            return response

        # Cancel any in-flight ingestion before tearing down the KB.
        # Without this, the background job keeps writing chunks via the
        # backend's persistent client, which auto-recreates the kb
        # directory after rmtree. The list endpoint's disk-fallback
        # path then re-discovers the recreated dir and the KB
        # reappears in the UI seconds after delete.
        await _cancel_inflight_ingestion_for_kb(
            kb_name=kb_name,
            current_user=kb_owner,
            job_service=job_service,
        )

        remote_warning = await _delete_remote_backend_collection(
            kb_name=kb_name,
            kb_path=kb_path,
            current_user=kb_owner,
        )

        # Delete the DB row first, then attempt to clear the on-disk dir.
        # Rationale: when Chroma still holds a SQLite lock (most common on
        # Windows) physical removal can fail, but the user's intent was to
        # remove the KB.  By dropping the DB row first the row never lingers
        # past a partial cleanup, and KBStorageHelper.delete_storage() drops
        # a sentinel inside any dir it could not remove so the listing layer
        # treats it as gone until the next restart fully reaps it.
        try:
            await knowledge_base_service.delete_by_user_and_name(_kb_guard.owner_user.id, kb_name)
        except Exception as exc:
            await logger.aerror("KB DB delete failed for %s: %s", kb_name, exc)
            raise HTTPException(status_code=500, detail="Error deleting knowledge base.") from exc

        storage_warning: str | None = None
        if not KBStorageHelper.delete_storage(kb_path, kb_name):
            # Both physical removal AND the sentinel write failed.  This is
            # rare (would require the dir itself being unwritable) but we
            # still return 200 because the DB row is gone -- the user no
            # longer sees the KB.  A warning surfaces so operators know the
            # bytes are still on disk and want a follow-up cleanup.
            storage_warning = (
                f"Knowledge base '{kb_name}' was removed from the database but its on-disk "
                "files could not be cleaned up. The KB will not reappear in the UI; the bytes "
                "will be removed on the next server restart."
            )
            await logger.awarning(storage_warning)

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error deleting knowledge base '%s': %s", kb_name, e)
        raise HTTPException(status_code=500, detail="Error deleting knowledge base.") from e
    else:
        response: dict[str, str] = {"message": f"Knowledge base '{kb_name}' deleted successfully"}
        # Storage-cleanup failure first so it is the most visible to the
        # operator (it has actionable filesystem implications).  Remote-
        # backend warnings stack onto the same response field separated by
        # a sentinel so a future client can split them.
        warnings = [w for w in (storage_warning, remote_warning) if w]
        if warnings:
            response["warning"] = " | ".join(warnings)
        return response


@router.delete("", status_code=HTTPStatus.OK)
@router.delete("/", status_code=HTTPStatus.OK)
async def delete_knowledge_bases_bulk(
    request: BulkDeleteRequest,
    current_user: CurrentActiveUser,
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> dict[str, object]:
    """Delete multiple knowledge bases."""
    # Per-KB guard. Resolve each guard upfront so the loop body can use the
    # owner context (path + DB row owner) when an authorization plugin authorizes
    # a non-owner via a share grant.
    kb_guards: dict[str, _KbGuardResult] = {}
    for kb_name in request.kb_names:
        kb_guards[kb_name] = await _guard_kb_action(
            current_user=current_user,
            action=KnowledgeBaseAction.DELETE,
            kb_name=kb_name,
        )
    try:
        deleted_count = 0
        not_found_kbs = []
        failed_kbs = []
        memory_base_kbs: list[str] = []
        remote_warnings: list[str] = []

        for kb_name in request.kb_names:
            kb_guard = kb_guards[kb_name]
            try:
                kb_path = _resolve_kb_path(kb_name, kb_guard.owner_user)
            except HTTPException as exc:
                if exc.status_code == HTTPStatus.NOT_FOUND:
                    # Try the orphan-row cleanup before declaring the
                    # KB not found — a remote-backed KB (Astra /
                    # Mongo / Postgres / OpenSearch) whose local dir
                    # is missing must still be deletable so the UI
                    # stops showing it. Owner-scoped: the orphan row
                    # belongs to the KB owner, not the actor.
                    handled, orphan_warning = await _cleanup_orphan_db_row(
                        kb_name=kb_name,
                        current_user=kb_guard.owner_user,
                    )
                    if handled:
                        deleted_count += 1
                        if orphan_warning:
                            remote_warnings.append(orphan_warning)
                    else:
                        not_found_kbs.append(kb_name)
                    continue
                raise  # Re-raise 403 (traversal) and 500 errors

            # Mirror the per-KB Memory-Base guard the single-delete /
            # ingest / chunks routes apply via dependency. Memory-Base
            # KBs are managed through the Memory Base APIs and must
            # not be deletable through the generic bulk endpoint.
            kb_metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
            if _is_memory_base_associated(kb_metadata):
                memory_base_kbs.append(kb_name)
                continue

            try:
                # Cancel any in-flight ingestion before tearing down
                # this KB. See the matching call in the single-delete
                # endpoint for the failure mode this prevents. Owner-
                # scoped so a shared-KB delete clears the owner's job.
                await _cancel_inflight_ingestion_for_kb(
                    kb_name=kb_name,
                    current_user=kb_guard.owner_user,
                    job_service=job_service,
                )
                remote_warning = await _delete_remote_backend_collection(
                    kb_name=kb_name,
                    kb_path=kb_path,
                    current_user=kb_guard.owner_user,
                )
                if remote_warning:
                    remote_warnings.append(remote_warning)

                # DB-first ordering, mirroring the single-delete endpoint:
                # row goes first so a locked-storage cleanup leaves no
                # stale row behind.  delete_storage() drops a sentinel
                # inside any dir it could not remove so listing stays
                # consistent.
                try:
                    await knowledge_base_service.delete_by_user_and_name(kb_guard.owner_user.id, kb_name)
                except Exception as exc:  # noqa: BLE001 - DB delete failures shouldn't block remaining KBs in the bulk op
                    await logger.aexception("KB DB delete failed for %s: %s", kb_name, exc)
                    failed_kbs.append(kb_name)
                    continue

                if not KBStorageHelper.delete_storage(kb_path, kb_name):
                    # Both rmtree and the sentinel write failed -- count
                    # this as deleted (the row is gone, the listing UI
                    # will not show the KB) but warn so the operator can
                    # follow up on the orphaned bytes.
                    remote_warnings.append(
                        f"Knowledge base '{kb_name}' was removed from the database but its on-disk "
                        "files could not be cleaned up; bytes will be reaped on next server restart."
                    )
                deleted_count += 1
            except (HTTPException, OSError, PermissionError) as e:
                await logger.aexception("Error deleting knowledge base '%s': %s", kb_name, e)
                # Continue with other deletions even if one fails
                failed_kbs.append(kb_name)

        if not_found_kbs and deleted_count == 0 and not memory_base_kbs:
            raise HTTPException(
                status_code=404, detail="Knowledge bases not found: {}".format(", ".join(not_found_kbs))
            )

        result: dict[str, object] = {
            "message": f"Successfully deleted {deleted_count} knowledge base(s)",
            "deleted_count": deleted_count,
        }

        if not_found_kbs:
            result["not_found"] = ", ".join(not_found_kbs)
        if failed_kbs:
            result["failed"] = ", ".join(failed_kbs)
        if memory_base_kbs:
            result["memory_base_skipped"] = ", ".join(memory_base_kbs)
        if remote_warnings:
            result["warnings"] = remote_warnings

    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error deleting knowledge bases: %s", e)
        raise HTTPException(status_code=500, detail="Error deleting knowledge bases.") from e
    else:
        return result


@router.post("/{kb_name}/cancel", status_code=HTTPStatus.OK, dependencies=[Depends(_check_memory_base_association)])
async def cancel_ingestion(
    kb_name: str,
    current_user: CurrentActiveUser,
    job_service: Annotated[JobService, Depends(get_job_service)],
    task_service: Annotated[TaskService, Depends(get_task_service)],
) -> dict[str, str]:
    """Cancel the ongoing ingestion task for a knowledge base."""
    _kb_guard = await _guard_kb_action(current_user=current_user, action=KnowledgeBaseAction.WRITE, kb_name=kb_name)
    _assert_kb_not_memory_base(kb_name, _kb_guard.owner_user)
    try:
        kb_path = _resolve_kb_path(kb_name, _kb_guard.owner_user)

        # ``asset_id`` is now sourced from ``KnowledgeBaseRecord.id``
        # (the indexed column on ``job.asset_id``); legacy KBs that
        # only exist on disk fall back to ``metadata['id']``.
        metadata = KBAnalysisHelper.get_metadata(kb_path, fast=True)
        asset_id = await _resolve_kb_asset_id(
            kb_name=kb_name,
            current_user=current_user,
            metadata=metadata,
        )

        # Fetch the latest ingestion job for this KB
        latest_jobs = await job_service.get_latest_jobs_by_asset_ids([asset_id])

        if asset_id not in latest_jobs:
            raise HTTPException(status_code=404, detail=f"No ingestion job found for the knowledge base {kb_name}")

        job = latest_jobs[asset_id]
        job_status = job.status.value if hasattr(job.status, "value") else str(job.status)

        # Check if job is already completed or failed
        if job_status in ["completed", "failed", "cancelled", "timed_out"]:
            raise HTTPException(status_code=400, detail=f"Cannot cancel job with status '{job_status}'")

        revoked = await task_service.revoke_task(job.job_id)
        # Update status immediately so background task can see it
        await job_service.update_job_status(job.job_id, JobStatus.CANCELLED)

        # Clean up any partially ingested chunks from this job. Forward
        # the KB's configured backend + user_id so non-Chroma KBs
        # (Mongo/Astra/Postgres) actually find their variable-backed
        # credentials and delete against the right store — otherwise
        # cleanup silently falls back to Chroma and remote chunks
        # written before the cancel stick around.
        kb_record = _kb_guard.record or await knowledge_base_service.get_by_user_and_name(
            _kb_guard.owner_user.id, kb_name
        )
        backend_type_value = (
            kb_record.backend_type if kb_record and kb_record.backend_type else BackendType.CHROMA.value
        )
        backend_config = (kb_record.backend_config or {}) if kb_record is not None else {}
        await KBIngestionHelper.cleanup_chroma_chunks_by_job(
            job.job_id,
            kb_path,
            kb_name,
            backend_type=backend_type_value,
            backend_config=backend_config,
            user_id=current_user.id,
        )

        if revoked:
            message = f"Ingestion job for {job.job_id} cancelled successfully."
        else:
            message = f"Job {job.job_id} is already cancelled."
    except asyncio.CancelledError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        await logger.aerror("Error cancelling ingestion: %s", e)
        raise HTTPException(status_code=500, detail="Error cancelling ingestion.") from e
    else:
        return {"message": message}
