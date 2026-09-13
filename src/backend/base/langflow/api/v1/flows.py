from __future__ import annotations

import asyncio
import io
import threading
import zipfile
from collections.abc import Collection
from typing import Annotated, cast
from uuid import UUID

import orjson
from fastapi import APIRouter, Body, Depends, File, Header, HTTPException, Request, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlmodel import apaginate
from lfx.log.logger import logger
from lfx.services.authorization.base import ShareRuleSnapshot
from lfx.services.cache.utils import CACHE_MISS
from lfx.services.catalog_policy import CatalogPolicySnapshot
from lfx.utils.flow_validation import (
    CatalogPolicyIdentityUnavailableError,
    CatalogPolicyValidationError,
    validate_catalog_policy_for_flow,
)
from pydantic import ValidationError
from sqlalchemy import case, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import and_, col, select

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    cascade_delete_flow,
    normalize_code_for_import,
    validate_is_component,
)
from langflow.api.utils.core import strip_secret_field_values
from langflow.api.utils.mcp.flow_secrets import (
    extract_and_strip_mcp_secrets,
    mcp_server_names,
    persist_and_strip_mcp_secrets,
    stage_mcp_secrets,
)
from langflow.api.utils.zip_utils import extract_flows_from_zip
from langflow.api.v1.authz_route_dependencies import (
    AuthorizedDeleteFlow,
    AuthorizedReadFlow,
    AuthorizedWriteFlow,
    RequireFlowCreate,
)
from langflow.api.v1.flows_helpers import (
    _build_flows_download_response,
    _canonicalize_flow_destination,
    _get_safe_flow_path,
    _new_flow,
    _patch_flow,
    _read_flow,
    _resolve_flow_destination,
    _save_flow_to_fs,
    _update_existing_flow,
    _validate_and_assign_folder,
    _verify_fs_path,
    destination_folder_owner_id,
    flow_read_for_actor,
)
from langflow.api.v1.mappers.deployments.sync import retry_flow_operation_on_deployment_guard
from langflow.api.v1.schemas import FlowBulkDelete, FlowListCreate
from langflow.api.v1.schemas.public_flows import PublicFlowRead
from langflow.initial_setup.constants import STARTER_FOLDER_NAME
from langflow.services.auth.utils import get_current_active_user, get_optional_user
from langflow.services.authorization import (
    FlowAction,
    apply_owned_or_visible_scope_prefilter,
    ensure_flow_permission,
    filter_visible_resources,
    visible_scope_prefilter,
)
from langflow.services.authorization.collaboration import CollaborationCapabilityError
from langflow.services.authorization.concurrency import (
    RevisionPreconditionError,
    conditional_writes_required,
    require_revision_precondition,
    strong_etag,
)
from langflow.services.authorization.fetch import authorization_admission, deny_to_404, load_mutation_actor
from langflow.services.authorization.lifecycle import safe_share_rules_removed
from langflow.services.authorization.public_access import (
    PublicResourceAction,
    authorize_public_flow_access,
    public_flow_capabilities,
)
from langflow.services.authorization.share_management import delete_resource_shares
from langflow.services.authorization.team_management import actor_can_administer_platform
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.cache.service import ThreadingInMemoryCache
from langflow.services.database.lock_retry import (
    RetryableTransactionError,
    is_database_lock_error,
    run_with_lock_retry,
    sanitize_database_error,
)
from langflow.services.database.models.deployment.exceptions import (
    araise_if_deployment_guard_error_or_skip,
)
from langflow.services.database.models.flow.model import (
    Flow,
    FlowCreate,
    FlowHeader,
    FlowRead,
    FlowType,
    FlowUpdate,
)

# TODO: Full-version import/export is planned as a follow-up feature. When implemented,
# re-add imports for create_flow_version_entry, get_flow_versions_with_provider_status, strip_version_data,
# and FlowVersionError from the flow_version modules.
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.user.model import User, UserRead
from langflow.services.deps import (
    get_authorization_service,
    get_catalog_policy_service,
    get_settings_service,
    get_storage_service,
)
from langflow.services.storage.service import StorageService
from langflow.utils.compression import compress_response
from langflow.utils.i18n import translate_flow_notes, translate_starter_flows

# Re-export helpers so existing ``from langflow.api.v1.flows import ...`` still works.
__all__ = [
    "_get_safe_flow_path",
    "_new_flow",
    "_read_flow",
    "_save_flow_to_fs",
    "_update_existing_flow",
    "_verify_fs_path",
]

_SQLITE_UNIQUE_MARKER = "UNIQUE constraint failed: "
_POSTGRES_UNIQUE_VIOLATION_SQLSTATE = "23505"
MAX_BULK_FLOW_MUTATIONS = 1000
_SQLITE_FLOW_UNIQUE_COLUMNS = {
    ("id",): "id",
    ("user_id", "name"): "name",
    ("user_id", "endpoint_name"): "endpoint_name",
}


async def _conditional_write_contract() -> bool:
    try:
        return await conditional_writes_required()
    except CollaborationCapabilityError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "AUTHORIZATION_NOT_READY", "message": "Authorization is not ready."},
        ) from exc


def _check_flow_revision(
    flow: Flow,
    *,
    if_match: str | None,
    required: bool,
) -> None:
    try:
        require_revision_precondition(
            resource_type="flow",
            resource_id=flow.id,
            current_revision=flow.edit_revision,
            if_match=if_match,
            required=required,
            changed_code="RESOURCE_CHANGED",
        )
    except RevisionPreconditionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _check_stable_put_creation(
    *,
    if_match: str | None,
    if_none_match: str | None,
    required: bool,
) -> None:
    if if_match is not None:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "RESOURCE_CHANGED", "message": "The requested resource does not yet exist."},
        )
    if required and (if_none_match is None or if_none_match.strip() != "*"):
        raise HTTPException(
            status_code=428,
            detail={"code": "PRECONDITION_REQUIRED", "message": "If-None-Match: * is required for stable-ID creation."},
        )


def _check_existing_put_creation_guard(flow: Flow, if_none_match: str | None) -> None:
    """Honor a supplied create-only condition after existing-resource authorization."""
    if if_none_match is None:
        return
    supplied = if_none_match.strip()
    current = strong_etag("flow", flow.id, flow.edit_revision)
    if supplied == "*" or current in {tag.strip() for tag in supplied.split(",")}:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={"code": "RESOURCE_CHANGED", "message": "A flow with this ID already exists."},
        )


_POSTGRES_FLOW_UNIQUE_COLUMNS = {
    "flow_pkey": "id",
    "pk_flow": "id",
    "uq_flow_id": "id",
    "unique_flow_name": "name",
    "unique_flow_endpoint_name": "endpoint_name",
}


def _postgres_unique_column(exc: BaseException) -> str | None:
    """Return a safe flow column for a PostgreSQL unique violation."""
    current: BaseException | None = exc
    constraint_name: str | None = None
    is_unique_violation = False
    seen: set[int] = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        sqlstate = getattr(current, "sqlstate", None) or getattr(current, "pgcode", None)
        is_unique_violation = is_unique_violation or sqlstate == _POSTGRES_UNIQUE_VIOLATION_SQLSTATE
        diagnostic = getattr(current, "diag", None)
        candidate = getattr(diagnostic, "constraint_name", None) or getattr(current, "constraint_name", None)
        if candidate:
            constraint_name = str(candidate)
        current = getattr(current, "orig", None) or current.__cause__

    if not is_unique_violation or constraint_name is None:
        return None
    return _POSTGRES_FLOW_UNIQUE_COLUMNS.get(constraint_name)


DB_OPERATION_FAILED = "The database rejected the request."
FLOW_PERSIST_FAILED = "Could not persist the flow."

# SQLite and PostgreSQL report a violation differently: SQLite names the columns
# ("UNIQUE constraint failed: flow.user_id, flow.name") while PostgreSQL names the constraint
# ('... violates unique constraint "unique_flow_name"'). Match whichever marker is present so both
# backends produce the same client-facing detail. Every constraint below is named in the models.
_UNIQUE_VIOLATION_DETAILS: tuple[tuple[str, str], ...] = (
    ("unique_flow_endpoint_name", "Endpoint name must be unique"),
    ("flow.endpoint_name", "Endpoint name must be unique"),
    ("unique_flow_name", "Name must be unique"),
    ("flow.name", "Name must be unique"),
    ("unique_folder_name", "Project name must be unique"),
    ("folder.name", "Project name must be unique"),
    ("flow_pkey", "A flow with this ID already exists"),
    ("flow.id", "A flow with this ID already exists"),
    ("folder_pkey", "A project with this ID already exists"),
    ("folder.id", "A project with this ID already exists"),
)
_UNIQUE_VIOLATION_TEXT = ("UNIQUE constraint failed", "duplicate key value violates unique constraint")
_UNIQUE_VIOLATION_SQLSTATE = "23505"


def _is_unique_violation(exc: Exception, msg: str) -> bool:
    """Detect a unique violation on any backend.

    Prefers the SQLSTATE on the driver exception (23505 on PostgreSQL, exposed as ``sqlstate`` by
    psycopg3 and ``pgcode`` by psycopg2) and falls back to the message text, which is all SQLite
    offers.

    Only database errors are considered. SQLAlchemy hangs the driver exception off ``.orig``, so
    that attribute is what separates a real DBAPI failure from an unrelated exception whose text
    merely contains the SQLite marker — a flow name can carry that string, and text alone must not
    be enough to launder it into a 4xx conflict.
    """
    if not hasattr(exc, "orig"):
        return False
    orig = exc.orig
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate == _UNIQUE_VIOLATION_SQLSTATE:
        return True
    return any(marker in msg for marker in _UNIQUE_VIOLATION_TEXT)


def _sqlite_unique_detail(msg: str, *, status_code: int) -> HTTPException:
    """Map a SQLite ``UNIQUE constraint failed: <cols>`` message to a client-facing detail.

    SQLite names columns rather than the constraint, so the column tuple is the only signal.
    On ``flow`` only the exact shapes in ``_SQLITE_FLOW_UNIQUE_COLUMNS`` are named; any other
    shape is a 500 rather than a guess. Other tables fall through to the qualified-name markers,
    which is how a project (``folder``) collision keeps its own wording.
    """
    constraint = msg.split(_SQLITE_UNIQUE_MARKER, maxsplit=1)[1].splitlines()[0]
    tables: set[str] = set()
    columns: list[str] = []
    for qualified in constraint.split(","):
        table, separator, candidate = qualified.strip().rpartition(".")
        if not separator:
            return HTTPException(status_code=500, detail=FLOW_PERSIST_FAILED)
        tables.add(table.rsplit(".", maxsplit=1)[-1])
        columns.append(candidate)

    if tables == {"flow"}:
        column = _SQLITE_FLOW_UNIQUE_COLUMNS.get(tuple(columns))
        if column is None:
            return HTTPException(status_code=500, detail=FLOW_PERSIST_FAILED)
        return HTTPException(status_code=status_code, detail=f"{column.capitalize().replace('_', ' ')} must be unique")

    for marker, detail in _UNIQUE_VIOLATION_DETAILS:
        if marker in constraint:
            return HTTPException(status_code=status_code, detail=detail)
    return HTTPException(status_code=500, detail=FLOW_PERSIST_FAILED)


def _handle_unique_constraint_error(exc: Exception, *, status_code: int = 400) -> HTTPException:
    """Map a unique-constraint violation to *status_code*; map anything else to a sanitized 500.

    Callers either raise the result directly or read a 500 as "not a conflict" (see update_flow),
    so the 500 branch stays — but its detail is sanitized, because SQLAlchemy's ``str()`` embeds
    the failing statement and its bound parameters.

    The three signals are tried strongest first. PostgreSQL's ``diag.constraint_name`` is
    authoritative and comes from the driver, so it wins over the message text, which can carry a
    user-supplied value that imitates a marker. SQLite offers no constraint name, so its message
    is parsed structurally. Only then does the marker table run, and an unrecognized violation is
    a 500 rather than a conflict invented from driver text.
    """
    msg = str(exc)
    if not _is_unique_violation(exc, msg):
        return HTTPException(status_code=500, detail=sanitize_database_error(exc, DB_OPERATION_FAILED))

    column = _postgres_unique_column(getattr(exc, "orig", None) or exc)
    if column is not None:
        return HTTPException(status_code=status_code, detail=f"{column.capitalize().replace('_', ' ')} must be unique")

    if _SQLITE_UNIQUE_MARKER in msg:
        return _sqlite_unique_detail(msg, status_code=status_code)

    for marker, detail in _UNIQUE_VIOLATION_DETAILS:
        if marker in msg:
            return HTTPException(status_code=status_code, detail=detail)
    return HTTPException(status_code=500, detail=FLOW_PERSIST_FAILED)


def _validate_catalog_policy_for_write(
    flow_data: dict | None,
    *,
    snapshot: CatalogPolicySnapshot,
) -> None:
    """Validate one effective flow graph and expose policy denials as client errors."""
    try:
        validate_catalog_policy_for_flow(flow_data, snapshot=snapshot)
    except CatalogPolicyValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CatalogPolicyIdentityUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# build router
router = APIRouter(prefix="/flows", tags=["Flows"])

FLOW_UPDATE_FAILED = "Could not update the flow."
FLOW_UPDATE_BUSY = "The database is busy. Please retry the request."
FLOW_CREATE_FAILED = "Could not create the flow."
FLOW_CREATE_BUSY = "The database is busy. Please retry the request."
FLOW_DELETE_FAILED = "Could not delete the flow."
FLOW_DELETE_BUSY = "The database is busy. Please retry the request."


@router.post("/", response_model=FlowRead, status_code=201)
async def create_flow(
    *,
    session: DbSession,
    flow: FlowCreate,
    current_user: CurrentActiveUser,
    _create: RequireFlowCreate,
    response: Response,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    try:
        catalog_policy_snapshot = get_catalog_policy_service().snapshot
        _validate_catalog_policy_for_write(flow.data, snapshot=catalog_policy_snapshot)
        carried_secrets, secret_variables = extract_and_strip_mcp_secrets(flow.data)
        # FastAPI builds the dependency's body model independently from the
        # handler's body model. Carry the exact destination that was authorized
        # into the row we persist so stale caller scope fields cannot retarget
        # the write after the guard has run.
        flow.workspace_id, flow.folder_id = _create
        stable_flow = flow.model_copy(deep=True)
        user_id = current_user.id

        async def create_attempt(_attempt: int) -> FlowRead:
            from langflow.services.deps import get_authorization_service

            await get_authorization_service().acquire_resource_mutation_lock(session=session)
            actor = await load_mutation_actor(session, user_id)
            attempt_flow = stable_flow.model_copy(deep=True)
            await _canonicalize_flow_destination(session, attempt_flow, user_id, widen_for_authz=True)
            await ensure_flow_permission(
                actor,
                FlowAction.CREATE,
                workspace_id=attempt_flow.workspace_id,
                folder_id=attempt_flow.folder_id,
                folder_user_id=await destination_folder_owner_id(session, attempt_flow.folder_id),
                audit_session=session,
            )
            await stage_mcp_secrets(carried_secrets, secret_variables, user_id, session)
            # _new_flow mutates its input while normalizing ownership, name,
            # endpoint and destination. Rebuild it for every transaction so a
            # rollback never leaves the retry with partially normalized state.
            return await _new_flow(
                session=session,
                flow=attempt_flow,
                user_id=user_id,
                storage_service=storage_service,
                widen_for_authz=True,
                propagate_unhandled_errors=True,
            )

        created = await run_with_lock_retry(
            create_attempt,
            session=session,
            description="flow creation",
        )
        # A collaborator may create a child inside another user's shared
        # project and the project owner may read it in the next request. Commit
        # before returning so that cross-session read is never asked to
        # authorize a row that is still only visible to this transaction.
        await session.commit()
        response.headers["ETag"] = strong_etag("flow", created.id, created.edit_revision)
        return created  # noqa: TRY300 - keep the route's existing error translation structure
    except HTTPException as exc:
        if exc.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise
        await logger.aerror("Flow creation failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=FLOW_CREATE_FAILED) from exc
    except Exception as e:
        if is_database_lock_error(e):
            await logger.aerror("Flow creation remained locked after retries", error_type=type(e).__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=FLOW_CREATE_BUSY,
                headers={"Retry-After": "1"},
            ) from e
        await logger.aerror("Flow creation failed", error_type=type(e).__name__)
        # Do not expose SQLAlchemy statements, bound parameters, database URLs
        # or user-provided flow identifiers through the API response.
        handled_error = _handle_unique_constraint_error(e)
        if handled_error.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise handled_error from e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=FLOW_CREATE_FAILED) from e


@router.get("/", response_model=list[FlowRead] | Page[FlowRead] | list[FlowHeader], status_code=200)
async def read_flows(
    *,
    current_user: CurrentActiveUser,
    session: DbSession,
    remove_example_flows: bool = False,
    components_only: bool = False,
    get_all: bool = True,
    folder_id: UUID | None = None,
    flow_type: FlowType | None = None,
    params: Annotated[Params, Depends()],
    header_flows: bool = False,
    shared_only: bool = False,
):
    """Retrieve a list of flows with optional pagination, filtering, and header-only mode."""
    async with authorization_admission(session) as admission:
        try:
            auth_settings = get_settings_service().auth_settings

            default_folder = (
                await admission.exec(
                    select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == current_user.id)
                )
            ).first()
            default_folder_id = default_folder.id if default_folder else None

            starter_folder = (
                await admission.exec(
                    select(Folder).where(Folder.name == STARTER_FOLDER_NAME, col(Folder.user_id).is_(None))
                )
            ).first()
            starter_folder_id = starter_folder.id if starter_folder else None

            if not starter_folder and not default_folder:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        "Starter project and default project not found. Please create a project and add flows to it."
                    ),
                )

            # A paginated Shared with me query spans all projects. Normal list
            # callers retain the historical implicit default-project selection.
            if not folder_id and not shared_only:
                folder_id = default_folder_id

            # Rows the caller owns outright. Under AUTO_LOGIN the legacy owner-scoped
            # query also surfaces null-owner flows; keep that in the fallback path
            # (``fallback_clause``). The SQL prefilter union, however, must NOT
            # blanket-include null-owner rows: the in-memory fallback routes them
            # through ``batch_enforce`` (``filter_visible_resources``'s owner_extractor
            # returns None, which never equals a real user id), so the prefilter keeps
            # them out of the owned half and a null-owner flow is visible only when the
            # plugin lists its id. AUTHZ_ENABLED and AUTO_LOGIN are independent flags,
            # so both can be set — this keeps the two paths consistent regardless.
            owned_clause = Flow.user_id == current_user.id
            fallback_clause = owned_clause
            if auth_settings.AUTO_LOGIN:
                fallback_clause = (Flow.user_id == None) | owned_clause  # noqa: E711

            # DB-layer authz prefilter: a registered authorization plugin can return
            # the concrete set of flow ids the caller may read, letting us widen the
            # owner-scoped query to (owned ⊕ visible) in SQL and skip the per-row
            # in-memory filter below. OSS pass-through returns None → the query stays
            # owner-scoped and ``filter_visible_resources`` runs unchanged.
            visibility_scope = await visible_scope_prefilter(current_user, resource_type="flow", act=FlowAction.READ)
            if visibility_scope is not None:
                canonical_workspace = case(
                    (col(Flow.folder_id).is_not(None), Folder.workspace_id),
                    else_=Flow.workspace_id,
                )
                stmt = await apply_owned_or_visible_scope_prefilter(
                    select(Flow).outerjoin(Folder, Folder.id == Flow.folder_id),
                    id_column=Flow.id,
                    owner_clause=owned_clause,
                    workspace_expression=canonical_workspace,
                    project_column=Flow.folder_id,
                    visibility=visibility_scope,
                )
            else:
                stmt = select(Flow).where(fallback_clause)

            # Keep discovery and pagination on the same authoritative SQL policy.
            # `shared_only` means readable resources owned by somebody else; it is
            # not a separate persistence path and cannot surface null-owner rows.
            if shared_only:
                stmt = stmt.where(col(Flow.user_id).is_not(None), Flow.user_id != current_user.id)

            if remove_example_flows:
                stmt = stmt.where(Flow.folder_id != starter_folder_id)

            if components_only:
                stmt = stmt.where(Flow.is_component == True)  # noqa: E712

            if flow_type is not None:
                stmt = stmt.where(Flow.flow_type == flow_type)

            if get_all:
                flows = (await admission.exec(stmt)).all()
                flows = validate_is_component(flows)
                if components_only:
                    flows = [flow for flow in flows if flow.is_component]
                if remove_example_flows and starter_folder_id:
                    flows = [flow for flow in flows if flow.folder_id != starter_folder_id]
                # When no DB prefilter is available (OSS pass-through), drop denied
                # rows in memory (per-flow domain_extractor). When the prefilter is
                # active the SQL union above is already authoritative, so skip the
                # per-row enforce to avoid an N+1.
                if visibility_scope is None:
                    flows = await filter_visible_resources(
                        current_user,
                        resource_type="flow",
                        candidates=list(flows),
                        domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
                        owner_extractor=lambda flow: flow.user_id,
                        act=FlowAction.READ,
                    )
                if header_flows:
                    # Convert to FlowHeader objects and compress the response
                    header_owner_ids = {flow.user_id for flow in flows if flow.user_id is not None}
                    header_owners_by_id: dict[UUID, str] = {}
                    if header_owner_ids:
                        header_owners_by_id = dict(
                            (
                                await admission.exec(
                                    select(User.id, User.username).where(col(User.id).in_(header_owner_ids))
                                )
                            ).all()
                        )
                    flow_headers = []
                    for flow in flows:
                        header = FlowHeader.model_validate(flow, from_attributes=True)
                        header.owner_username = header_owners_by_id.get(flow.user_id)
                        header.is_owner = flow.user_id == current_user.id
                        flow_headers.append(header)
                    return compress_response(flow_headers)

                # Convert to FlowRead while session is still active to avoid detached instance errors
                flow_owner_ids = {flow.user_id for flow in flows if flow.user_id is not None}
                flow_owners_by_id: dict[UUID, str] = {}
                if flow_owner_ids:
                    flow_owners_by_id = dict(
                        (
                            await admission.exec(select(User.id, User.username).where(col(User.id).in_(flow_owner_ids)))
                        ).all()
                    )
                flow_reads = [
                    flow_read_for_actor(flow, current_user.id, owner_username=flow_owners_by_id.get(flow.user_id))
                    for flow in flows
                ]
                return compress_response(flow_reads)

            if folder_id is not None:
                stmt = stmt.where(Flow.folder_id == folder_id)
            if shared_only:
                stmt = stmt.order_by(Flow.name, Flow.id)

            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
                )
                page = await apaginate(admission, stmt, params=params)

            # Same authz handling as get_all. With the SQL prefilter active the union
            # was applied before pagination, so ``page.total`` is accurate; the OSS
            # fallback narrows ``page.items`` in memory and ``page.total`` may
            # overcount denied rows (unchanged from before).
            if visibility_scope is None:
                page.items = await filter_visible_resources(
                    current_user,
                    resource_type="flow",
                    candidates=list(page.items),
                    domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
                    owner_extractor=lambda flow: flow.user_id,
                    act=FlowAction.READ,
                )
            page_owner_ids = {flow.user_id for flow in page.items if flow.user_id is not None}
            page_owners_by_id: dict[UUID, str] = {}
            if page_owner_ids:
                page_owners_by_id = dict(
                    (await admission.exec(select(User.id, User.username).where(col(User.id).in_(page_owner_ids)))).all()
                )
            page.items = [
                flow_read_for_actor(flow, current_user.id, owner_username=page_owners_by_id.get(flow.user_id))
                for flow in page.items
            ]
            return page  # noqa: TRY300 — final return inside try matches the existing style of this handler

        except HTTPException:
            raise
        except Exception as e:
            import logging as _logging

            _logging.getLogger(__name__).exception("Error listing flows")
            raise HTTPException(status_code=500, detail="An internal error occurred while listing flows.") from e


@router.get("/{flow_id}", response_model=FlowRead, status_code=200)
async def read_flow(
    *,
    flow_id: UUID,  # noqa: ARG001
    flow: AuthorizedReadFlow,
    current_user: CurrentActiveUser,
    response: Response,
):
    """Read a flow."""
    response.headers["ETag"] = strong_etag("flow", flow.id, flow.edit_revision)
    return flow_read_for_actor(flow, current_user.id)


@router.get("/{flow_id}/note_translations", status_code=200)
async def get_note_translations(
    *,
    flow_id: UUID,  # noqa: ARG001
    flow: AuthorizedReadFlow,
    request: Request,
) -> dict[str, str]:
    """Return translated note node descriptions for the current locale.

    Returns a mapping of node_id → translated markdown text.  Only nodes
    with a matching translation key are included; nodes without translations
    are omitted so the caller can leave them unchanged.

    A missing or inaccessible flow yields 404 (via ``AuthorizedReadFlow``),
    consistent with ``GET /flows/{id}``; the sole frontend caller (NoteNode)
    treats that as "no translations" and renders the original text.
    """
    from langflow.utils.i18n import translate

    if not flow.data:
        return {}

    locale = getattr(request.state, "locale", "en")
    nodes = flow.data.get("nodes", [])
    result: dict[str, str] = {}
    for node in nodes:
        if node.get("type") == "noteNode":
            i18n_key = node.get("data", {}).get("node", {}).get("i18n_key")
            if i18n_key:
                translated = translate(i18n_key, locale, "")
                if translated:
                    result[node.get("id")] = translated
    return result


@router.get("/public_flow/{flow_id}", response_model=PublicFlowRead, status_code=200)
async def read_public_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    request: Request,
):
    """Read a public flow without requiring authorization (public means public).

    Because this endpoint is unauthenticated, secret field values (every template
    field marked ``password``) are stripped before returning so a PUBLIC flow does
    not leak the owner's stored API keys / credentials to anonymous callers.

    The response also carries the anonymous capability set. A canonical PUBLIC
    share admits flows whose ``access_type`` is still PRIVATE and bounds them at
    its own permission level, so a direct-link client that re-derives access from
    the legacy flag disagrees with this decision in both directions.
    """
    flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()
    if flow is None:
        raise HTTPException(status_code=404, detail="Flow not found")
    await authorize_public_flow_access(
        flow=flow,
        action=PublicResourceAction.READ,
        request_host=request.url.hostname,
        session=session,
    )
    capabilities = await public_flow_capabilities(
        flow=flow,
        request_host=request.url.hostname,
        session=session,
    )
    flow_read = PublicFlowRead.model_validate(flow, from_attributes=True, update={"public_access": capabilities})
    flow_read.data = strip_secret_field_values(flow_read.data)
    return flow_read


@router.patch("/{flow_id}", response_model=FlowRead, status_code=200)
async def update_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    db_flow: AuthorizedWriteFlow,
    flow: FlowUpdate,
    current_user: CurrentActiveUser,
    response: Response,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Update a flow."""
    actor_id = current_user.id
    actor = UserRead.model_validate(current_user, from_attributes=True)
    try:
        precondition_required = await _conditional_write_contract()
        catalog_policy_snapshot = get_catalog_policy_service().snapshot
        # Destination check: resolve the actual owner-folder/workspace tuple
        # before authorizing a move. ``_patch_flow`` applies payload values via
        # ``model_dump(exclude_unset=True, exclude_none=True)``, so None means
        # "no change" and falls back to the existing scope.
        requested_folder_id = flow.folder_id
        target_workspace_id, target_folder_id = await _resolve_flow_destination(
            session,
            cast(UUID, db_flow.user_id),
            requested_folder_id,
            fallback_folder_id=db_flow.folder_id,
            reject_invalid=requested_folder_id is not None,
            widen_for_authz=True,
            authorized_existing_folder_id=db_flow.folder_id,
        )
        flow.workspace_id = target_workspace_id
        if requested_folder_id is not None:
            flow.folder_id = target_folder_id
        if target_workspace_id != db_flow.workspace_id or target_folder_id != db_flow.folder_id:
            if db_flow.user_id != actor.id and not actor_can_administer_platform(actor):
                raise HTTPException(status_code=403, detail="Only a workflow owner may move it.")
            try:
                await ensure_flow_permission(
                    actor,
                    FlowAction.CREATE,
                    workspace_id=target_workspace_id,
                    folder_id=target_folder_id,
                    folder_user_id=await destination_folder_owner_id(session, target_folder_id),
                    audit_session=session,
                )
            except HTTPException as exc:
                raise deny_to_404(exc, detail="Flow not found") from exc

        # Explicit folder_id=None is ignored here because _patch_flow builds
        # update_data with exclude_none=True, so null folder_id is a no-op.
        folder_id_will_change = target_folder_id != db_flow.folder_id
        flow_owner_ids = {flow_id: db_flow.user_id}

        # Extract once, outside the retry loop. The in-place rewrite of flow.data survives a
        # rollback while the staged rows do not, so re-extracting on attempt 2 would find
        # only the reference it wrote itself and stage nothing. actor.id rather than
        # current_user.id: the rollback expires the ORM User.
        carried_secrets, secret_variables = extract_and_strip_mcp_secrets(flow.data)

        async def operation() -> FlowRead:
            # Re-load inside each attempt so retry after nested rollback never uses an expired ORM instance.
            db_flow_for_attempt = await _read_flow(
                session=session,
                flow_id=flow_id,
                user_id=actor.id,
                for_update=True,
            )
            if not db_flow_for_attempt:
                raise HTTPException(status_code=404, detail="Flow not found")
            # TOCTOU: a concurrent PATCH could have moved this flow to a
            # different workspace/folder between the destination check above
            # and this retry attempt. Re-authorize against the freshly
            # reloaded source AND destination so the writer cannot ride a
            # stale check across a race.
            try:
                await ensure_flow_permission(
                    actor,
                    FlowAction.WRITE,
                    flow_id=flow_id,
                    flow_user_id=db_flow_for_attempt.user_id,
                    workspace_id=db_flow_for_attempt.workspace_id,
                    folder_id=db_flow_for_attempt.folder_id,
                    audit_session=session,
                )
            except HTTPException as exc:
                raise deny_to_404(exc, detail="Flow not found") from exc
            attempt_target_workspace_id, attempt_target_folder_id = await _resolve_flow_destination(
                session,
                db_flow_for_attempt.user_id,
                flow.folder_id,
                fallback_folder_id=db_flow_for_attempt.folder_id,
                reject_invalid=flow.folder_id is not None,
                widen_for_authz=True,
                authorized_existing_folder_id=db_flow_for_attempt.folder_id,
            )
            if (
                attempt_target_workspace_id != db_flow_for_attempt.workspace_id
                or attempt_target_folder_id != db_flow_for_attempt.folder_id
            ):
                if db_flow_for_attempt.user_id != actor.id and not actor_can_administer_platform(actor):
                    raise HTTPException(status_code=403, detail="Only a workflow owner may move it.")
                try:
                    await ensure_flow_permission(
                        actor,
                        FlowAction.CREATE,
                        workspace_id=attempt_target_workspace_id,
                        folder_id=attempt_target_folder_id,
                        folder_user_id=await destination_folder_owner_id(session, attempt_target_folder_id),
                        audit_session=session,
                    )
                except HTTPException as exc:
                    raise deny_to_404(exc, detail="Flow not found") from exc
            effective_flow_data = flow.data if flow.data is not None else db_flow_for_attempt.data
            _validate_catalog_policy_for_write(effective_flow_data, snapshot=catalog_policy_snapshot)
            # The only write path where a literal is the user editing a key rather than a
            # file arriving. Scoped to servers this flow already referenced, so saving a
            # freshly imported flow cannot adopt its credential either.
            await stage_mcp_secrets(
                carried_secrets,
                secret_variables,
                actor.id,
                session,
                rotatable_servers=mcp_server_names(db_flow_for_attempt.data),
            )
            return await _patch_flow(
                session=session,
                db_flow=db_flow_for_attempt,
                flow=flow,
                user_id=actor.id,
                storage_service=storage_service,
                if_match=if_match,
                precondition_required=precondition_required,
                widen_for_authz=True,
                actor_is_platform_admin=actor_can_administer_platform(actor),
            )

        async def update_attempt(_attempt: int) -> FlowRead:
            nonlocal current_user
            nonlocal actor
            from langflow.services.deps import get_authorization_service

            await get_authorization_service().acquire_resource_mutation_lock(session=session)
            current_user = await load_mutation_actor(session, actor_id)
            actor = UserRead.model_validate(current_user, from_attributes=True)
            if folder_id_will_change:
                return await retry_flow_operation_on_deployment_guard(
                    db=session,
                    flow_owner_ids=flow_owner_ids,
                    operation=operation,
                )
            return await operation()

        updated = await run_with_lock_retry(
            update_attempt,
            session=session,
            description=f"update_flow {flow_id}",
        )
        response.headers["ETag"] = strong_etag("flow", updated.id, updated.edit_revision)
        return updated  # noqa: TRY300 - keep the route's existing error translation structure
    except HTTPException:
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=update_flow flow_id={flow_id}",
        )
        if is_database_lock_error(e):
            await logger.awarning("op=update_flow flow_id=%s exhausted lock retries", flow_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=FLOW_UPDATE_BUSY,
                headers={"Retry-After": "1"},
            ) from e
        handled_error = _handle_unique_constraint_error(e)
        if handled_error.status_code != status.HTTP_500_INTERNAL_SERVER_ERROR:
            raise handled_error from e
        await logger.aerror("op=update_flow flow_id=%s failed with %s", flow_id, type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=FLOW_UPDATE_FAILED,
        ) from e


@router.put("/{flow_id}", response_model=FlowRead)
async def upsert_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    flow: FlowCreate,
    current_user: CurrentActiveUser,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    if_none_match: Annotated[str | None, Header(alias="If-None-Match")] = None,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Create or update a flow with a specific ID (upsert).

    Returns 201 for creation, 200 for update.  Returns 404 if owned by another user.
    """
    actor_id = current_user.id
    from fastapi.responses import JSONResponse

    # Read once, outside the retry loop: a rollback between attempts expires the ORM User
    # and a later attribute read would lazy-load outside the greenlet.
    writer_id = current_user.id
    # Extract once: a rollback between retry attempts discards the staged rows but not the
    # in-place rewrite, so a second extraction would find only its own reference.
    carried_secrets, secret_variables = extract_and_strip_mcp_secrets(flow.data)

    try:

        async def upsert_attempt(_attempt: int) -> JSONResponse:
            nonlocal current_user
            from langflow.services.deps import get_authorization_service

            await get_authorization_service().acquire_resource_mutation_lock(session=session)
            current_user = await load_mutation_actor(session, actor_id)
            catalog_policy_snapshot = get_catalog_policy_service().snapshot
            # Check if flow exists (without user filter to distinguish ownership vs CREATE)
            existing_flow = (await session.exec(select(Flow).where(Flow.id == flow_id))).first()

            if existing_flow is not None:
                # Block non-owner upsert when cross-user fetch is off (UUID privacy).
                from langflow.services.deps import get_authorization_service

                authz = get_authorization_service()
                can_widen = await authz.supports_cross_user_fetch() and await authz.is_enabled()
                if not can_widen and existing_flow.user_id != current_user.id:
                    raise HTTPException(status_code=404, detail="Flow not found")

                try:
                    await ensure_flow_permission(
                        current_user,
                        FlowAction.WRITE,
                        flow_id=flow_id,
                        flow_user_id=existing_flow.user_id,
                        workspace_id=existing_flow.workspace_id,
                        folder_id=existing_flow.folder_id,
                        audit_session=session,
                    )
                except HTTPException as exc:
                    raise deny_to_404(exc, detail="Flow not found") from exc

                precondition_required = await _conditional_write_contract()
                _check_existing_put_creation_guard(existing_flow, if_none_match)

                # Destination check (see update_flow above): resolve the actual
                # owner-folder/workspace tuple and authorize WRITE there.
                # ``_update_existing_flow`` applies payload values via
                # ``model_dump(exclude_unset=True, exclude_none=True)``, so None
                # means "keep existing" and a non-None differing value means "move".
                requested_folder_id = flow.folder_id
                target_workspace_id, target_folder_id = await _resolve_flow_destination(
                    session,
                    existing_flow.user_id,
                    requested_folder_id,
                    fallback_folder_id=existing_flow.folder_id,
                    reject_invalid=True,
                    widen_for_authz=True,
                    authorized_existing_folder_id=existing_flow.folder_id,
                )
                flow.workspace_id = target_workspace_id
                if requested_folder_id is not None:
                    flow.folder_id = target_folder_id
                if target_workspace_id != existing_flow.workspace_id or target_folder_id != existing_flow.folder_id:
                    if existing_flow.user_id != current_user.id and not actor_can_administer_platform(current_user):
                        raise HTTPException(status_code=403, detail="Only a workflow owner may move it.")
                    try:
                        await ensure_flow_permission(
                            current_user,
                            FlowAction.CREATE,
                            workspace_id=target_workspace_id,
                            folder_id=target_folder_id,
                            folder_user_id=await destination_folder_owner_id(session, target_folder_id),
                            audit_session=session,
                        )
                    except HTTPException as exc:
                        raise deny_to_404(exc, detail="Flow not found") from exc

                # Sync deployment state before folder changes
                # Explicit folder_id=None is ignored here because _update_existing_flow
                # also uses exclude_none=True for update_data.
                folder_id_will_change = target_folder_id != existing_flow.folder_id

                async def update_operation() -> FlowRead:
                    # Re-load inside each attempt so retry after nested rollback never uses an expired ORM instance.
                    existing_flow_for_attempt = await _read_flow(
                        session=session,
                        flow_id=flow_id,
                        user_id=current_user.id,
                        for_update=True,
                    )
                    if existing_flow_for_attempt is None:
                        raise HTTPException(status_code=404, detail="Flow not found")
                    # Re-authorize the freshly loaded source and resolved
                    # destination on every attempt. A concurrent move between the
                    # outer check and this write must not let a shared editor carry
                    # stale workspace permission into a different project.
                    try:
                        await ensure_flow_permission(
                            current_user,
                            FlowAction.WRITE,
                            flow_id=flow_id,
                            flow_user_id=existing_flow_for_attempt.user_id,
                            workspace_id=existing_flow_for_attempt.workspace_id,
                            folder_id=existing_flow_for_attempt.folder_id,
                            audit_session=session,
                        )
                    except HTTPException as exc:
                        raise deny_to_404(exc, detail="Flow not found") from exc

                    attempt_target_workspace_id, attempt_target_folder_id = await _resolve_flow_destination(
                        session,
                        existing_flow_for_attempt.user_id,
                        requested_folder_id,
                        fallback_folder_id=existing_flow_for_attempt.folder_id,
                        reject_invalid=requested_folder_id is not None,
                        widen_for_authz=True,
                        authorized_existing_folder_id=existing_flow_for_attempt.folder_id,
                    )
                    flow.workspace_id = attempt_target_workspace_id
                    if requested_folder_id is not None:
                        flow.folder_id = attempt_target_folder_id
                    if (
                        attempt_target_workspace_id != existing_flow_for_attempt.workspace_id
                        or attempt_target_folder_id != existing_flow_for_attempt.folder_id
                    ):
                        if existing_flow_for_attempt.user_id != current_user.id and not actor_can_administer_platform(
                            current_user
                        ):
                            raise HTTPException(status_code=403, detail="Only a workflow owner may move it.")
                        try:
                            await ensure_flow_permission(
                                current_user,
                                FlowAction.CREATE,
                                workspace_id=attempt_target_workspace_id,
                                folder_id=attempt_target_folder_id,
                                folder_user_id=await destination_folder_owner_id(session, attempt_target_folder_id),
                                audit_session=session,
                            )
                        except HTTPException as exc:
                            raise deny_to_404(exc, detail="Flow not found") from exc
                    effective_flow_data = flow.data if flow.data is not None else existing_flow_for_attempt.data
                    _validate_catalog_policy_for_write(effective_flow_data, snapshot=catalog_policy_snapshot)
                    await stage_mcp_secrets(carried_secrets, secret_variables, writer_id, session)
                    return await _update_existing_flow(
                        session=session,
                        existing_flow=existing_flow_for_attempt,
                        flow=flow,
                        current_user=current_user,
                        storage_service=storage_service,
                        if_match=if_match,
                        precondition_required=precondition_required,
                        widen_for_authz=True,
                    )

                if folder_id_will_change:
                    flow_read = await retry_flow_operation_on_deployment_guard(
                        db=session,
                        flow_owner_ids={existing_flow.id: existing_flow.user_id},
                        operation=update_operation,
                    )
                else:
                    flow_read = await update_operation()
                status_code = 200
            else:
                # CREATE path - flow doesn't exist
                await _canonicalize_flow_destination(
                    session,
                    flow,
                    current_user.id,
                    reject_invalid=True,
                    widen_for_authz=True,
                )
                await ensure_flow_permission(
                    current_user,
                    FlowAction.CREATE,
                    workspace_id=flow.workspace_id,
                    folder_id=flow.folder_id,
                    folder_user_id=await destination_folder_owner_id(session, flow.folder_id),
                    audit_session=session,
                )
                precondition_required = await _conditional_write_contract()
                _check_stable_put_creation(
                    if_match=if_match,
                    if_none_match=if_none_match,
                    required=precondition_required,
                )
                _validate_catalog_policy_for_write(flow.data, snapshot=catalog_policy_snapshot)
                await stage_mcp_secrets(carried_secrets, secret_variables, writer_id, session)
                flow_read = await _new_flow(
                    session=session,
                    flow=flow,
                    user_id=current_user.id,
                    storage_service=storage_service,
                    flow_id=flow_id,
                    fail_on_endpoint_conflict=True,
                    validate_folder=True,
                    widen_for_authz=True,
                )
                status_code = 201

            return JSONResponse(
                status_code=status_code,
                content=jsonable_encoder(flow_read),
                headers={"ETag": strong_etag("flow", flow_read.id, flow_read.edit_revision)},
            )

        return await run_with_lock_retry(upsert_attempt, session=session, description=f"upsert flow {flow_id}")

    except HTTPException:
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=upsert_flow flow_id={flow_id}",
        )
        raise _handle_unique_constraint_error(e, status_code=409) from e


@router.delete("/{flow_id}", status_code=200)
async def delete_flow(
    *,
    session: DbSession,
    flow_id: UUID,
    flow: AuthorizedDeleteFlow,
    current_user: CurrentActiveUser,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
):
    """Delete a flow."""
    actor = UserRead.model_validate(current_user, from_attributes=True)
    target_flow_id = flow_id
    flow_owner_ids: dict[UUID, UUID] = {target_flow_id: cast(UUID, flow.user_id)}
    removed_share_rules: tuple[ShareRuleSnapshot, ...] = ()
    precondition_required = await _conditional_write_contract()

    async def _delete_attempt(_attempt: int) -> None:
        nonlocal actor
        from langflow.services.deps import get_authorization_service

        await get_authorization_service().acquire_resource_mutation_lock(session=session)
        actor = await load_mutation_actor(session, actor.id)

        async def _delete_operation() -> None:
            nonlocal removed_share_rules
            flow_owner_ids.clear()
            removed_share_rules = ()
            retry_target = await _read_flow(session, target_flow_id, actor.id, for_update=True)
            if retry_target is None:
                return
            await ensure_flow_permission(
                actor,
                FlowAction.DELETE,
                flow_id=retry_target.id,
                flow_user_id=retry_target.user_id,
                workspace_id=retry_target.workspace_id,
                folder_id=retry_target.folder_id,
                audit_session=session,
            )
            _check_flow_revision(retry_target, if_match=if_match, required=precondition_required)
            flow_owner_ids[retry_target.id] = retry_target.user_id
            removed_share_rules = await delete_resource_shares(
                session,
                actor_id=actor.id,
                resources=(("flow", retry_target.id),),
            )
            await cascade_delete_flow(session, target_flow_id)

        await retry_flow_operation_on_deployment_guard(
            db=session,
            flow_owner_ids=flow_owner_ids,
            operation=_delete_operation,
        )

    try:
        await run_with_lock_retry(_delete_attempt, session=session, description=f"delete_flow {target_flow_id}")
        await session.commit()
    except HTTPException:
        raise
    except Exception as exc:
        await araise_if_deployment_guard_error_or_skip(
            exc,
            log_message=f"op=delete_flow flow_id={target_flow_id}",
        )
        if is_database_lock_error(exc):
            await logger.awarning("op=delete_flow flow_id=%s exhausted lock retries", target_flow_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=FLOW_DELETE_BUSY,
                headers={"Retry-After": "1"},
            ) from exc
        await logger.aerror("op=delete_flow failed with %s", type(exc).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=FLOW_DELETE_FAILED) from exc
    await safe_share_rules_removed(get_authorization_service(), removed_share_rules)
    return {"message": "Flow deleted successfully"}


@router.post("/batch/", response_model=list[FlowRead], status_code=201)
async def create_flows(
    *,
    session: DbSession,
    flow_list: FlowListCreate,
    current_user: CurrentActiveUser,
):
    """Create multiple new flows."""
    original_flow_list = flow_list
    actor_id = current_user.id

    async def create_batch_attempt(_attempt: int) -> list[FlowRead]:
        from langflow.services.deps import get_authorization_service

        await get_authorization_service().acquire_resource_mutation_lock(session=session)
        current_user = await load_mutation_actor(session, actor_id)
        flow_list = original_flow_list.model_copy(deep=True)
        if flow_list.expected_edit_revision:
            raise HTTPException(
                status_code=422,
                detail="expected_edit_revision is only valid for request contracts that update existing flows.",
            )
        catalog_policy_snapshot = get_catalog_policy_service().snapshot
        # Validate the complete request before adding or flushing any rows. This
        # keeps a denial in a later item from partially applying an earlier item.
        for flow in flow_list.flows:
            _validate_catalog_policy_for_write(flow.data, snapshot=catalog_policy_snapshot)

        # Resolve and authorize every flow's canonical project/workspace instead of
        # trusting caller-supplied denormalized scope fields.
        for flow in flow_list.flows:
            await _canonicalize_flow_destination(
                session,
                flow,
                current_user.id,
                reject_invalid=flow.folder_id is not None,
                widen_for_authz=True,
            )
            await ensure_flow_permission(
                current_user,
                FlowAction.CREATE,
                workspace_id=flow.workspace_id,
                folder_id=flow.folder_id,
                folder_user_id=await destination_folder_owner_id(session, flow.folder_id),
                audit_session=session,
            )
        # Credential persistence starts only after the entire destination and
        # policy set is authorized.
        for flow in flow_list.flows:
            await persist_and_strip_mcp_secrets(flow.data, current_user.id, session)
        # Guard against duplicate IDs up-front so callers get a clean 422 instead
        # of an unhandled DB IntegrityError.  Use upload_file() for upsert semantics.
        requested_ids = [f.id for f in flow_list.flows if f.id is not None]
        if requested_ids:
            existing_ids = (await session.exec(select(Flow.id).where(col(Flow.id).in_(requested_ids)))).all()
            if existing_ids:
                conflict = ", ".join(str(i) for i in existing_ids)
                msg = (
                    f"Flow(s) with the following IDs already exist: {conflict}. "
                    "Use the update endpoint or upload_file() for upsert semantics."
                )
                raise HTTPException(status_code=422, detail=msg)

        db_flows = []
        for flow in flow_list.flows:
            flow.user_id = current_user.id
            # Exclude id from model_validate (same reasoning as _new_flow) and apply separately.
            db_flow = Flow.model_validate(flow.model_dump(exclude={"id"}))
            if flow.id is not None:
                db_flow.id = flow.id
            await _validate_and_assign_folder(session, db_flow, current_user.id, widen_for_authz=True)
            session.add(db_flow)
            db_flows.append(db_flow)

        # Unlike create_flow/upsert_flow, this endpoint does not route through
        # _new_flow, so a (user_id, name)/(user_id, endpoint_name) collision reaches
        # the flush unhandled. Left un-rolled-back on SQLite, the failed INSERT pins
        # the write lock and the next writer busy-waits busy_timeout (30s) before its
        # own "database is locked"; the raw error would also leak the SQL statement
        # and bound parameters. Roll back to release the lock immediately, then map
        # to a clean 409.
        try:
            await session.flush()
        except IntegrityError as exc:
            await session.rollback()
            raise _handle_unique_constraint_error(exc, status_code=409) from exc
        for db_flow in db_flows:
            await session.refresh(db_flow)

        return [FlowRead.model_validate(db_flow, from_attributes=True) for db_flow in db_flows]

    return await run_with_lock_retry(create_batch_attempt, session=session, description="create flows")


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile | None, File()] = None,
    current_user: CurrentActiveUser,
    folder_id: UUID | None = None,
    storage_service: Annotated[StorageService, Depends(get_storage_service)],
):
    """Upload flows from a JSON or ZIP file (upsert semantics for flows with stable IDs)."""
    # Authorization is enforced per-flow below, after parsing — the per-flow
    # check uses the actual workspace_id/folder_id each uploaded flow targets.
    # A coarse pre-parse check here would over-reject (it would authorize the
    # caller against ``domain="*", obj="flow:*"`` regardless of where the
    # uploaded flows actually land).
    actor_id = current_user.id
    if file is None:
        raise HTTPException(status_code=400, detail="No file provided")

    contents = await file.read()

    if not contents:
        raise HTTPException(status_code=400, detail="The uploaded file is empty")

    if zipfile.is_zipfile(io.BytesIO(contents)):
        try:
            flows_data = await extract_flows_from_zip(contents)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        if not flows_data:
            raise HTTPException(status_code=400, detail="No valid flow JSON files found in the ZIP")
        data = {"flows": flows_data}
    else:
        try:
            data = orjson.loads(contents)
        except orjson.JSONDecodeError as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {e}") from e

    # Normalise code fields: if exported with code-as-lines format, rejoin to
    # strings before creating the Pydantic models so the DB always stores strings.
    if not isinstance(data, dict):
        raise HTTPException(
            status_code=422,
            detail="Invalid JSON: expected an object with 'flows' or a single flow object",
        )
    try:
        if "flows" in data:
            if not isinstance(data["flows"], list):
                raise HTTPException(
                    status_code=422,
                    detail="Invalid JSON: 'flows' must be a list of flow objects",
                )
            non_dict = [i for i, f in enumerate(data["flows"]) if not isinstance(f, dict)]
            if non_dict:
                raise HTTPException(
                    status_code=422,
                    detail=f"Invalid JSON: flows[{non_dict[0]}] is not an object",
                )
            data = {**data, "flows": [normalize_code_for_import(f) for f in data["flows"]]}
            flow_list = FlowListCreate(**data)
        else:
            flow_list = FlowListCreate(flows=[FlowCreate(**normalize_code_for_import(data))])
    except HTTPException:
        raise
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # TODO: Full-version import is planned as a follow-up feature.
    # When implemented, extract raw flow dicts here to read embedded "version"
    # arrays and create FlowVersion entries for each imported flow.

    original_flow_list = flow_list

    async def upload_attempt(_attempt: int) -> list[FlowRead]:
        nonlocal current_user
        from langflow.services.deps import get_authorization_service

        await get_authorization_service().acquire_resource_mutation_lock(session=session)
        current_user = await load_mutation_actor(session, actor_id)
        flow_list = original_flow_list.model_copy(deep=True)
        catalog_policy_snapshot = get_catalog_policy_service().snapshot

        requested_id_list = [flow.id for flow in flow_list.flows if flow.id is not None]
        requested_ids = set(requested_id_list)
        if len(requested_ids) != len(requested_id_list):
            raise HTTPException(status_code=422, detail="Invalid upload: duplicate flow IDs are not allowed")

        # Lock only rows this request is permitted to resolve. Disabled/legacy mode
        # remains owner-scoped; the registered service may widen the candidate fetch,
        # after which every row is still authorized below.
        existing_flows_by_id: dict[UUID, Flow] = {}
        if requested_ids:
            from langflow.services.deps import get_authorization_service

            authz = get_authorization_service()
            await authz.acquire_resource_mutation_lock(session=session)
            can_widen = await authz.supports_cross_user_fetch() and await authz.is_enabled()
            existing_statement = select(Flow).where(col(Flow.id).in_(requested_ids)).order_by(Flow.id).with_for_update()
            if not can_widen:
                existing_statement = existing_statement.where(Flow.user_id == current_user.id)
            existing_flows = (await session.exec(existing_statement)).all()
            existing_flows_by_id = {existing_flow.id: existing_flow for existing_flow in existing_flows}

        # Resolve and authorize the complete set before credential, filesystem, or
        # flow persistence side effects. Existing stable IDs are updates, never
        # copies: the stored owner remains authoritative.
        for flow in flow_list.flows:
            fallback_folder_id = None
            existing_flow = existing_flows_by_id.get(flow.id) if flow.id is not None else None
            if folder_id is not None:
                flow.folder_id = folder_id
            elif flow.folder_id is None and existing_flow is not None:
                fallback_folder_id = existing_flow.folder_id
            await _canonicalize_flow_destination(
                session,
                flow,
                cast(UUID, existing_flow.user_id) if existing_flow is not None else current_user.id,
                fallback_folder_id=fallback_folder_id,
                reject_invalid=flow.folder_id is not None,
                widen_for_authz=True,
                authorized_existing_folder_id=existing_flow.folder_id if existing_flow is not None else None,
            )
            if existing_flow is None:
                await ensure_flow_permission(
                    current_user,
                    FlowAction.CREATE,
                    workspace_id=flow.workspace_id,
                    folder_id=flow.folder_id,
                    folder_user_id=await destination_folder_owner_id(session, flow.folder_id),
                    audit_session=session,
                )
            else:
                destination_changed = (
                    flow.workspace_id != existing_flow.workspace_id or flow.folder_id != existing_flow.folder_id
                )
                if (
                    destination_changed
                    and existing_flow.user_id != current_user.id
                    and not actor_can_administer_platform(current_user)
                ):
                    raise HTTPException(status_code=403, detail="Only a workflow owner may move it.")
                try:
                    await ensure_flow_permission(
                        current_user,
                        FlowAction.WRITE,
                        flow_id=existing_flow.id,
                        flow_user_id=existing_flow.user_id,
                        workspace_id=existing_flow.workspace_id,
                        folder_id=existing_flow.folder_id,
                        audit_session=session,
                    )
                    if destination_changed:
                        await ensure_flow_permission(
                            current_user,
                            FlowAction.CREATE,
                            workspace_id=flow.workspace_id,
                            folder_id=flow.folder_id,
                            folder_user_id=await destination_folder_owner_id(session, flow.folder_id),
                            audit_session=session,
                        )
                except HTTPException as exc:
                    raise deny_to_404(exc, detail="Flow not found") from exc

            # Upload upserts ignore omitted/null data. Validate the stored graph in
            # that case so a metadata-only write cannot bypass a newly blocked component.
            effective_flow_data = flow.data
            if effective_flow_data is None and existing_flow is not None:
                effective_flow_data = existing_flow.data
            _validate_catalog_policy_for_write(effective_flow_data, snapshot=catalog_policy_snapshot)

        precondition_required = await _conditional_write_contract()
        unexpected_revision_ids = set(flow_list.expected_edit_revision) - set(existing_flows_by_id)
        if unexpected_revision_ids:
            raise HTTPException(
                status_code=422,
                detail="expected_edit_revision keys must identify existing authorized flows in this upload.",
            )
        for existing_flow in existing_flows_by_id.values():
            expected_revision = flow_list.expected_edit_revision.get(existing_flow.id)
            supplied_etag = (
                strong_etag("flow", existing_flow.id, expected_revision) if expected_revision is not None else None
            )
            _check_flow_revision(existing_flow, if_match=supplied_etag, required=precondition_required)

        # Credential extraction/persistence begins only after all authorization and
        # optimistic-precondition checks have passed.
        for flow in flow_list.flows:
            await persist_and_strip_mcp_secrets(flow.data, current_user.id, session)

        try:
            flow_reads: list[FlowRead] = []
            for flow in flow_list.flows:
                stable_id = flow.id
                existing_flow = existing_flows_by_id.get(stable_id) if stable_id is not None else None
                if existing_flow is not None:
                    expected_revision = flow_list.expected_edit_revision.get(existing_flow.id)
                    flow_read = await _update_existing_flow(
                        session=session,
                        existing_flow=existing_flow,
                        flow=flow,
                        current_user=current_user,
                        storage_service=storage_service,
                        if_match=(
                            strong_etag("flow", existing_flow.id, expected_revision)
                            if expected_revision is not None
                            else None
                        ),
                        precondition_required=precondition_required,
                        widen_for_authz=True,
                    )
                else:
                    flow.user_id = current_user.id
                    flow_read = await _new_flow(
                        session=session,
                        flow=flow,
                        user_id=current_user.id,
                        storage_service=storage_service,
                        flow_id=stable_id,
                        widen_for_authz=True,
                    )
                flow_reads.append(flow_read)
        except (HTTPException, RetryableTransactionError):
            raise
        except Exception as e:
            if is_database_lock_error(e):
                raise
            raise _handle_unique_constraint_error(e) from e
        else:
            return flow_reads

    return await run_with_lock_retry(upload_attempt, session=session, description="upload flows")


@router.delete("/")
async def delete_multiple_flows(
    payload: Annotated[FlowBulkDelete | list[UUID], Body()],
    user: CurrentActiveUser,
    db: DbSession,
):
    """Delete multiple flows by their IDs."""
    actor = UserRead.model_validate(user, from_attributes=True)
    if isinstance(payload, list):
        flow_ids = payload
        expected_edit_revision: dict[UUID, int] = {}
    else:
        flow_ids = payload.flow_ids
        expected_edit_revision = payload.expected_edit_revision
    if len(flow_ids) > MAX_BULK_FLOW_MUTATIONS:
        raise HTTPException(status_code=422, detail="At most 1000 flows may be deleted in one request.")
    if len(set(flow_ids)) != len(flow_ids):
        raise HTTPException(status_code=422, detail="Duplicate flow IDs are not allowed.")
    unexpected_revision_ids = set(expected_edit_revision) - set(flow_ids)
    if unexpected_revision_ids:
        raise HTTPException(status_code=422, detail="expected_edit_revision keys must identify requested flows.")
    precondition_required = await _conditional_write_contract()
    try:
        authorized_flow_owner_ids: dict[UUID, UUID] = {}
        removed_share_rules: tuple[ShareRuleSnapshot, ...] = ()

        async def _delete_operation(*, allow_missing: bool) -> int:
            nonlocal removed_share_rules
            authorized_flow_owner_ids.clear()
            removed_share_rules = ()
            if not flow_ids:
                return 0
            # Widen fetch when cross-user DELETE is supported; else owner-scoped.
            from langflow.services.deps import get_authorization_service

            authz = get_authorization_service()
            await authz.acquire_resource_mutation_lock(session=db)
            predicates = [col(Flow.id).in_(flow_ids)]
            if not (await authz.supports_cross_user_fetch() and await authz.is_enabled()):
                predicates.append(col(Flow.user_id) == actor.id)
            if db.get_bind().dialect.name == "sqlite":
                await db.exec(update(Flow).where(*predicates).values(edit_revision=Flow.edit_revision))
            stmt = (
                select(Flow)
                .where(*predicates)
                .order_by(Flow.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            flows_to_delete = list((await db.exec(stmt)).all())
            if not allow_missing and {flow.id for flow in flows_to_delete} != set(flow_ids):
                raise HTTPException(status_code=404, detail="One or more flows were not found.")
            for flow in flows_to_delete:
                try:
                    await ensure_flow_permission(
                        actor,
                        FlowAction.DELETE,
                        flow_id=flow.id,
                        flow_user_id=flow.user_id,
                        workspace_id=flow.workspace_id,
                        folder_id=flow.folder_id,
                        audit_session=db,
                    )
                except HTTPException as exc:
                    raise deny_to_404(exc, detail="Flow not found") from exc
                expected_revision = expected_edit_revision.get(flow.id)
                _check_flow_revision(
                    flow,
                    if_match=(
                        strong_etag("flow", flow.id, expected_revision) if expected_revision is not None else None
                    ),
                    required=precondition_required,
                )
                if flow.user_id is None:
                    raise HTTPException(status_code=403, detail="System-managed flows cannot be deleted.")
                authorized_flow_owner_ids[flow.id] = flow.user_id
            removed_share_rules = await delete_resource_shares(
                db,
                actor_id=actor.id,
                resources=tuple(("flow", flow.id) for flow in flows_to_delete),
            )
            for flow in flows_to_delete:
                await cascade_delete_flow(db, flow.id)
            await db.flush()
            return len(flows_to_delete)

        async def _delete_attempt(attempt: int) -> int:
            nonlocal actor
            from langflow.services.deps import get_authorization_service

            await get_authorization_service().acquire_resource_mutation_lock(session=db)
            actor = await load_mutation_actor(db, actor.id)

            async def operation() -> int:
                # A row seen on the first attempt may be deleted concurrently while
                # the stale SQLite transaction is rolled back. Retrying the remaining
                # authorized rows is idempotent; an initially missing row still 404s.
                return await _delete_operation(allow_missing=attempt > 0)

            return await retry_flow_operation_on_deployment_guard(
                db=db,
                flow_owner_ids=authorized_flow_owner_ids,
                operation=operation,
            )

        deleted_count = await run_with_lock_retry(
            _delete_attempt,
            session=db,
            description=f"delete_multiple_flows count={len(flow_ids)}",
        )
        await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        await araise_if_deployment_guard_error_or_skip(
            exc,
            log_message=f"op=delete_multiple_flows flow_ids_count={len(flow_ids)}",
        )
        if is_database_lock_error(exc):
            await logger.awarning("op=delete_multiple_flows flow_ids_count=%s exhausted lock retries", len(flow_ids))
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=FLOW_DELETE_BUSY,
                headers={"Retry-After": "1"},
            ) from exc
        await logger.aerror(
            "op=delete_multiple_flows flow_ids_count=%s failed with %s", len(flow_ids), type(exc).__name__
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=FLOW_DELETE_FAILED) from exc

    await safe_share_rules_removed(get_authorization_service(), removed_share_rules)
    return {"deleted": deleted_count}


@router.post("/download/", status_code=200)
async def download_multiple_file(
    flow_ids: list[UUID],
    user: CurrentActiveUser,
    db: DbSession,
):
    """Download all flows as a zip file."""
    # TODO: Full-version download (include_version parameter) is planned as a follow-up feature.
    # When implemented, add an include_version: bool = False parameter and embed version
    # entries in each flow dict using get_flow_versions_with_provider_status and strip_version_data.
    # Widen fetch when cross-user READ is supported; else owner-scoped.
    from langflow.services.deps import get_authorization_service

    async with authorization_admission(db) as admission:
        authz = get_authorization_service()
        base_stmt = select(Flow).where(col(Flow.id).in_(flow_ids))  # type: ignore[attr-defined]
        if await authz.supports_cross_user_fetch() and await authz.is_enabled():
            stmt = base_stmt
        else:
            stmt = base_stmt.where(and_(Flow.user_id == user.id))
        flows = (await admission.exec(stmt)).all()

        if not flows:
            raise HTTPException(status_code=404, detail="No flows found.")

        for flow in flows:
            # Plugin deny → 404 (UUID privacy).
            try:
                await ensure_flow_permission(
                    user,
                    FlowAction.READ,
                    flow_id=flow.id,
                    flow_user_id=flow.user_id,
                    workspace_id=flow.workspace_id,
                    folder_id=flow.folder_id,
                )
            except HTTPException as exc:
                raise deny_to_404(exc, detail="No flows found.") from exc

        return _build_flows_download_response(flows)


# 5 minutes
_STARTER_FLOWS_TTL_SECONDS: float = 300.0
_starter_flows_cache: ThreadingInMemoryCache[threading.RLock] = ThreadingInMemoryCache(
    max_size=1,
    expiration_time=int(_STARTER_FLOWS_TTL_SECONDS),
)
_starter_flows_translated_cache: ThreadingInMemoryCache[threading.RLock] = ThreadingInMemoryCache(
    max_size=16,  # Why: 16 > 7 current supported locales, leaves headroom for future additions
    expiration_time=int(_STARTER_FLOWS_TTL_SECONDS),
)
_starter_flows_lock = asyncio.Lock()


def _filter_basic_examples_by_catalog_policy(
    flows: list[FlowRead],
    *,
    blocked_template_keys: Collection[str],
) -> list[FlowRead]:
    """Return a request-local view without exact blocked template keys."""
    return [flow for flow in flows if flow.name_key not in blocked_template_keys]


@router.get("/basic_examples/", response_model=list[FlowRead], status_code=200)
async def read_basic_examples(
    *,
    session: DbSession,
    request: Request,
    user: Annotated[User | None, Depends(get_optional_user)],
    include_blocked: bool = False,
):
    """Retrieve a list of basic example flows."""
    if include_blocked and (user is None or not user.is_superuser):
        raise HTTPException(
            status_code=403,
            detail="Only superusers can include blocked catalog templates.",
        )

    catalog_policy_snapshot = get_catalog_policy_service().snapshot
    locale = getattr(request.state, "locale", "en")
    translated_cache_key = f"starter_flows_{locale}"

    # Fast path: translated result already cached for this locale
    cached_translated = _starter_flows_translated_cache.get(translated_cache_key)
    if cached_translated is not CACHE_MISS:
        visible_flows = (
            cached_translated
            if include_blocked
            else _filter_basic_examples_by_catalog_policy(
                cached_translated,
                blocked_template_keys=catalog_policy_snapshot.blocked_template_keys,
            )
        )
        return compress_response(visible_flows)

    async with _starter_flows_lock:
        # Double-check inside lock to prevent thundering herd
        cached_translated = _starter_flows_translated_cache.get(translated_cache_key)
        if cached_translated is not CACHE_MISS:
            visible_flows = (
                cached_translated
                if include_blocked
                else _filter_basic_examples_by_catalog_policy(
                    cached_translated,
                    blocked_template_keys=catalog_policy_snapshot.blocked_template_keys,
                )
            )
            return compress_response(visible_flows)

        # Ensure raw DB data is cached
        cached_flow_reads = _starter_flows_cache.get("starter_flows")
        if cached_flow_reads is CACHE_MISS:
            try:
                starter_folder = (
                    await session.exec(
                        select(Folder).where(Folder.name == STARTER_FOLDER_NAME, col(Folder.user_id).is_(None))
                    )
                ).first()

                if not starter_folder:
                    return compress_response([])

                all_starter_folder_flows = (
                    await session.exec(select(Flow).where(Flow.folder_id == starter_folder.id))
                ).all()

                cached_flow_reads = [
                    FlowRead.model_validate(flow, from_attributes=True) for flow in all_starter_folder_flows
                ]
                _starter_flows_cache.set("starter_flows", cached_flow_reads)

            except Exception as e:
                import logging as _logging

                _logging.getLogger(__name__).exception("Error loading basic examples")
                raise HTTPException(status_code=500, detail="An internal error occurred while loading examples.") from e

        # Translate once per locale and cache the result
        # Why: cached uncompressed so the same result can be re-compressed per
        # response — keeps locale-switching working without storing per-locale
        # compressed blobs.
        translated = translate_starter_flows(cached_flow_reads, locale)
        result = []
        for flow in translated:
            flow_copy = flow.model_copy()
            if flow_copy.data and isinstance(flow_copy.data, dict):
                nodes = flow_copy.data.get("nodes", [])
                translated_nodes = translate_flow_notes(nodes, locale)
                flow_copy.data = {**flow_copy.data, "nodes": translated_nodes}
            result.append(flow_copy)

        _starter_flows_translated_cache.set(translated_cache_key, result)

    visible_flows = (
        result
        if include_blocked
        else _filter_basic_examples_by_catalog_policy(
            result,
            blocked_template_keys=catalog_policy_snapshot.blocked_template_keys,
        )
    )
    return compress_response(visible_flows)


@router.post("/expand/", status_code=200, dependencies=[Depends(get_current_active_user)], include_in_schema=False)
async def expand_compact_flow_endpoint(
    compact_data: dict,
):
    """Expand a compact flow format (minimal nodes/edges) to the full flow format."""
    from lfx.interface.components import component_cache, get_and_cache_all_types_dict

    from langflow.processing.expand_flow import expand_compact_flow

    # Ensure component cache is loaded
    if component_cache.all_types_dict is None:
        settings_service = get_settings_service()
        await get_and_cache_all_types_dict(settings_service)

    if component_cache.all_types_dict is None:
        raise HTTPException(status_code=500, detail="Component cache not initialized")

    try:
        return expand_compact_flow(compact_data, component_cache.all_types_dict)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
