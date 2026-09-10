import warnings
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from lfx.log.logger import logger
from lfx.services.mcp_composer.service import MCPComposerService
from lfx.utils.util_strings import escape_like_pattern
from sqlalchemy import literal, null, or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    cascade_delete_flow,
    custom_params,
)
from langflow.api.v1.auth_helpers import handle_auth_settings_update
from langflow.api.v1.flows import _handle_unique_constraint_error
from langflow.api.v1.mappers.deployments.sync import (
    retry_flow_operation_on_deployment_guard,
    retry_project_operation_on_deployment_guard,
)
from langflow.api.v1.mcp_projects import register_project_with_composer
from langflow.api.v1.projects_files import download_project_flows, upload_project_flows
from langflow.api.v1.projects_mcp_helpers import (
    cleanup_mcp_on_delete,
    handle_mcp_server_rename,
    reconcile_mcp_server_for_auth_update,
    register_mcp_servers_for_project,
)
from langflow.initial_setup.constants import ASSISTANT_FOLDER_NAME, STARTER_FOLDER_NAME
from langflow.services.auth.mcp_encryption import encrypt_auth_settings
from langflow.services.authorization import (
    FlowAction,
    ProjectAction,
    ensure_project_permission,
    filter_visible_resources,
    resource_visible_in_scope,
    restrict_to_owned_or_visible_scope,
    visible_scope_prefilter,
)
from langflow.services.authorization.fetch import (
    authorized_or_owner_scoped,
    deny_to_404,
    deny_to_404_unless_readable,
)
from langflow.services.authorization.utils import _resolve_authz_domain
from langflow.services.database.lock_retry import (
    is_database_lock_error,
    run_with_lock_retry,
    sanitize_database_error,
)
from langflow.services.database.models.deployment.exceptions import (
    araise_if_deployment_guard_error_or_skip,
    remap_flow_guard_for_project_delete,
)
from langflow.services.database.models.deployment.guards import check_project_has_deployments
from langflow.services.database.models.deployment.orm_guards import ensure_flow_moves_allowed
from langflow.services.database.models.flow.model import Flow, FlowRead
from langflow.services.database.models.folder.constants import DEFAULT_FOLDER_NAME
from langflow.services.database.models.folder.model import (
    Folder,
    FolderCreate,
    FolderListRead,
    FolderRead,
    FolderReadWithFlows,
    FolderUpdate,
)
from langflow.services.database.models.folder.pagination_model import FolderWithPaginatedFlows
from langflow.services.database.models.user.model import User
from langflow.services.deps import get_service, get_settings_service
from langflow.services.schema import ServiceType

router = APIRouter(prefix="/projects", tags=["Projects"])

PROJECT_READ_FAILED = "Could not read the project."
PROJECT_CREATE_FAILED = "Could not create the project."
PROJECT_UPDATE_FAILED = "Could not update the project."
PROJECT_SAVE_FAILED = "Could not save the project."
PROJECT_DELETE_FAILED = "Could not delete the project."
PROJECT_DELETE_BUSY = "The database is busy. Please retry the request."
PROJECT_WRITE_DENIED_DETAIL = "You don't have permission to edit this project."
PROJECT_DELETE_DENIED_DETAIL = "You don't have permission to delete this project."

# Backwards-compatible local alias; the implementation now lives in lfx.utils.util_strings so the
# same LIKE-escaping is shared across the API endpoints + the tracing repository.
_escape_like = escape_like_pattern


async def _new_project(
    *,
    session: DbSession,
    project: FolderCreate,
    current_user: User,
    project_id: UUID | None = None,
    fail_on_name_conflict: bool = False,
) -> FolderRead:
    """Create a project (folder), optionally at a caller-specified id (PUT upsert).

    Mirrors ``_new_flow``:
    - ``project_id`` overrides the ``uuid4`` default when provided so a project can be
      synced across instances under the same UUID.
    - ``fail_on_name_conflict`` skips the auto-rename dedup loop so a name collision fails
      loud via the ``(user_id, name)`` unique constraint (mapped to 409 by the caller) instead
      of silently appending ``" (N)"``.

    Runs the same MCP server auto-registration + AUTO_LOGIN apikey auth + flow-move side
    effects as ``POST /projects/``. Raises on unique-constraint / deployment-guard errors;
    callers map those to HTTP status.

    ``current_user`` (the full ``User``) is required because the MCP registration and flow-move
    side effects operate on the owning user, not just their id.
    """
    new_project = Folder.model_validate(project, from_attributes=True)
    new_project.user_id = current_user.id
    # Apply the stable id: an explicit ``project_id`` (PUT upsert) overrides the uuid4 default.
    if project_id is not None:
        new_project.id = project_id

    # POST auto-renames on a name collision; PUT (fail_on_name_conflict) skips the dedup so the
    # unique constraint fires and the caller can surface a 409. Dedup uses a LIKE scan over
    # existing project names (e.g. "MyProject", "MyProject (1)", "MyProject (2)") to find the
    # highest suffix and append N+1.
    if (
        not fail_on_name_conflict
        and (
            await session.exec(
                statement=select(Folder).where(Folder.name == new_project.name).where(Folder.user_id == current_user.id)
            )
        ).first()
    ):
        escaped_project_name = _escape_like(new_project.name)
        project_results = await session.exec(
            select(Folder).where(
                Folder.name.like(f"{escaped_project_name}%", escape="\\"),  # type: ignore[attr-defined]
                Folder.user_id == current_user.id,
            )
        )
        # No emptiness guard: session.exec() returns a ScalarResult, which is always truthy even
        # when it yields no rows. Iterating an empty result simply leaves project_numbers empty.
        project_numbers = []
        for name in (existing.name for existing in project_results):
            if "(" not in name:
                continue
            try:
                project_numbers.append(int(name.split("(")[-1].split(")")[0]))
            except ValueError:
                continue
        if project_numbers:
            new_project.name = f"{new_project.name} ({max(project_numbers) + 1})"
        else:
            new_project.name = f"{new_project.name} (1)"

    settings_service = get_settings_service()
    mcp_auth: dict = {"auth_type": "none"}

    if project.auth_settings:
        mcp_auth = project.auth_settings.copy()
        new_project.auth_settings = encrypt_auth_settings(mcp_auth)
    # If AUTO_LOGIN is false, automatically enable API key authentication
    elif not settings_service.auth_settings.AUTO_LOGIN:
        mcp_auth = {"auth_type": "apikey"}
        new_project.auth_settings = encrypt_auth_settings(mcp_auth)
        await logger.adebug(
            "Auto-enabled API key authentication for project %s (%s) due to AUTO_LOGIN=false",
            new_project.name,
            new_project.id,
        )

    session.add(new_project)
    await session.flush()
    await session.refresh(new_project)

    # Auto-register MCP server for this project with configured default auth
    if get_settings_service().settings.add_projects_to_mcp_servers:
        await register_mcp_servers_for_project(new_project, mcp_auth, current_user, session)

    flow_ids_for_sync = list(dict.fromkeys((project.flows_list or []) + (project.components_list or [])))
    authorized_flow_owner_ids: dict[UUID, UUID] = {}

    async def _move_flows_into_project() -> None:
        if project.components_list:
            component_flows = (
                await session.exec(
                    select(Flow.id, Flow.folder_id).where(
                        Flow.id.in_(project.components_list),  # type: ignore[attr-defined]
                        Flow.user_id == current_user.id,
                    )
                )
            ).all()
            authorized_flow_owner_ids.update((flow_id, current_user.id) for flow_id, _folder_id in component_flows)
            await ensure_flow_moves_allowed(
                session,
                flow_folder_pairs=list(component_flows),
                new_folder_id=new_project.id,
            )
            update_statement_components = (
                update(Flow)
                .where(Flow.id.in_(project.components_list), Flow.user_id == current_user.id)  # type: ignore[attr-defined]
                .values(folder_id=new_project.id, workspace_id=new_project.workspace_id)
            )
            await session.exec(update_statement_components)

        if project.flows_list:
            project_flows = (
                await session.exec(
                    select(Flow.id, Flow.folder_id).where(
                        Flow.id.in_(project.flows_list),  # type: ignore[attr-defined]
                        Flow.user_id == current_user.id,
                    )
                )
            ).all()
            authorized_flow_owner_ids.update((flow_id, current_user.id) for flow_id, _folder_id in project_flows)
            await ensure_flow_moves_allowed(
                session,
                flow_folder_pairs=list(project_flows),
                new_folder_id=new_project.id,
            )
            update_statement_flows = (
                update(Flow)
                .where(Flow.id.in_(project.flows_list), Flow.user_id == current_user.id)  # type: ignore[attr-defined]
                .values(folder_id=new_project.id, workspace_id=new_project.workspace_id)
            )
            await session.exec(update_statement_flows)

    if flow_ids_for_sync:
        await retry_flow_operation_on_deployment_guard(
            db=session,
            flow_owner_ids=authorized_flow_owner_ids,
            operation=_move_flows_into_project,
        )
    else:
        await _move_flows_into_project()

    # Convert to FolderRead while session is still active to avoid detached instance errors
    return FolderRead.model_validate(new_project, from_attributes=True)


@router.post("/", response_model=FolderRead, status_code=201)
async def create_project(
    *,
    session: DbSession,
    project: FolderCreate,
    current_user: CurrentActiveUser,
):
    await ensure_project_permission(
        current_user, ProjectAction.CREATE, workspace_id=getattr(project, "workspace_id", None)
    )
    try:
        return await _new_project(
            session=session,
            project=project,
            current_user=current_user,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message="op=create_project",
        )
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_CREATE_FAILED)) from e


@router.get("/", response_model=list[FolderListRead], status_code=200)
async def read_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        # Rows the caller owns outright. The legacy owner-scoped fallback also
        # surfaces null-owner projects (e.g. the starter project), but those must
        # be policy-checked rather than blanket-included: ``filter_visible_resources``
        # below treats a null owner as un-owned (its ``owner_extractor`` returns
        # None, which never equals a real user id) and routes them through
        # ``batch_enforce``. So the SQL prefilter union uses the owned-only clause
        # — a null-owner project is visible only when the plugin lists its id —
        # keeping both paths' null semantics identical (the name filter below is
        # then a convenience, not the thing preventing a null-owner leak).
        owned_clause = Folder.user_id == current_user.id
        # DB-layer authz prefilter: when a plugin returns the concrete set of
        # project ids the caller may read, widen the owner-scoped query to
        # (owned ⊕ visible) in SQL and skip the per-row in-memory filter below.
        # OSS pass-through returns None → owner-scoped query + filter unchanged.
        visibility_scope = await visible_scope_prefilter(current_user, resource_type="project", act=ProjectAction.READ)
        if visibility_scope is not None:
            stmt = restrict_to_owned_or_visible_scope(
                select(Folder),
                id_column=Folder.id,
                owner_clause=owned_clause,
                workspace_column=Folder.workspace_id,
                project_column=Folder.id,
                visibility=visibility_scope,
            )
        else:
            stmt = select(Folder).where(or_(owned_clause, Folder.user_id == None))  # noqa: E711
        projects = (await session.exec(stmt)).all()
        projects = [
            project for project in projects if not (project.name == STARTER_FOLDER_NAME and project.user_id is None)
        ]
        # When no DB prefilter is available (OSS pass-through), drop projects the
        # user can't read in memory. ``domain_extractor`` groups requests by
        # concrete project so each batch is evaluated against the same policy
        # tuple as the single-resource guard. When the prefilter is active the
        # SQL union is already authoritative — skip the per-row enforce to
        # avoid an N+1.
        if visibility_scope is None:
            projects = await filter_visible_resources(
                current_user,
                resource_type="project",
                candidates=list(projects),
                domain_extractor=lambda project: _resolve_authz_domain(project.workspace_id, project.id),
                owner_extractor=lambda project: project.user_id,
                act=ProjectAction.READ,
            )
        sorted_projects = sorted(projects, key=lambda x: x.name != DEFAULT_FOLDER_NAME)

        owner_ids = {project.user_id for project in sorted_projects if project.user_id is not None}
        owners_by_id: dict[str, str] = {}
        if owner_ids:
            owner_rows = (await session.exec(select(User.id, User.username).where(User.id.in_(owner_ids)))).all()
            owners_by_id = {str(owner_id): username for owner_id, username in owner_rows}

        # Convert while the session is active so owner-qualified project lists
        # do not trigger lazy loads after the request-scoped session closes.
        return [
            FolderListRead.model_validate(
                project,
                from_attributes=True,
                update={
                    "owner_username": owners_by_id.get(str(project.user_id)) if project.user_id is not None else None,
                    "is_owner": str(project.user_id) == str(current_user.id),
                },
            )
            for project in sorted_projects
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_READ_FAILED)) from e


@router.get("/{project_id}", response_model=FolderWithPaginatedFlows | FolderReadWithFlows, status_code=200)
async def read_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
    params: Annotated[Params | None, Depends(custom_params)],
    page: Annotated[int | None, Query()] = None,
    size: Annotated[int | None, Query()] = None,
    is_component: bool = False,
    is_flow: bool = False,
    search: str = "",
):
    try:
        # Share-aware fetch: when an authorization plugin is
        # registered (``SUPPORTS_CROSS_USER_FETCH=True``) the project is
        # loaded by id alone and ``ensure_project_permission`` below decides
        # access. The OSS pass-through keeps the owner-scoped query so the
        # strict-pass-through stub cannot widen visibility.
        from langflow.services.deps import get_authorization_service

        authz = get_authorization_service()
        # Cross-user fetch only when both the plugin capability and the
        # ``AUTHZ_ENABLED`` flag are on — otherwise route guards are no-ops
        # and widening the lookup would expose foreign projects without any
        # policy check.
        share_aware = await authz.supports_cross_user_fetch() and await authz.is_enabled()
        stmt = select(Folder).options(selectinload(Folder.flows)).where(Folder.id == project_id)
        if not share_aware:
            stmt = stmt.where(Folder.user_id == current_user.id)
        project = (await session.exec(stmt)).first()
    except Exception as e:
        if "No result found" in str(e):
            raise HTTPException(status_code=404, detail="Project not found") from e
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_READ_FAILED)) from e

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        await ensure_project_permission(
            current_user,
            ProjectAction.READ,
            project_id=project_id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, detail="Project not found") from exc

    try:
        # When share-aware fetch is on and the project is not owned by the
        # caller (i.e. reached via a share grant), show all flows in the
        # project — the share grant on the project implies access to its
        # contents. Otherwise keep the existing owner-scoped flow filter.
        treat_as_shared = share_aware and project.user_id != current_user.id

        # DB-layer authz prefilter for the project's flows. Only meaningful for
        # shared-project reads (owner reads are already owner-scoped and run no
        # per-flow enforce). A concrete list lets us constrain the paginated SQL
        # query / set-filter the eager-loaded collection to (owned ⊕ visible) and
        # skip the per-row enforce; None keeps the in-memory fallback. The flows
        # all live in this project, so a single project-scoped domain applies.
        visibility_scope = (
            await visible_scope_prefilter(
                current_user,
                resource_type="flow",
                domain=_resolve_authz_domain(project.workspace_id, project_id),
                act=FlowAction.READ,
            )
            if treat_as_shared
            else None
        )

        # Check if pagination is explicitly requested by the user (both page and size provided)
        if page is not None and size is not None:
            stmt = select(Flow).where(Flow.folder_id == project_id)
            if not treat_as_shared:
                stmt = stmt.where(Flow.user_id == current_user.id)
            elif visibility_scope is not None:
                # Shared project with a concrete prefilter: widen to
                # (owned ⊕ visible) at the DB layer so ``page.total`` reflects the
                # prefilter and no per-row enforce runs.
                stmt = restrict_to_owned_or_visible_scope(
                    stmt,
                    id_column=Flow.id,
                    owner_clause=Flow.user_id == current_user.id,
                    workspace_expression=null() if project.workspace_id is None else literal(project.workspace_id),
                    project_column=Flow.folder_id,
                    visibility=visibility_scope,
                )

            if Flow.updated_at is not None:
                stmt = stmt.order_by(Flow.updated_at.desc())  # type: ignore[attr-defined]
            if is_component:
                stmt = stmt.where(Flow.is_component == True)  # noqa: E712
            if is_flow:
                stmt = stmt.where(Flow.is_component == False)  # noqa: E712
            if search:
                _search = _escape_like(search)
                stmt = stmt.where(Flow.name.like(f"%{_search}%", escape="\\"))  # type: ignore[attr-defined]

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", category=DeprecationWarning, module=r"fastapi_pagination\.ext\.sqlalchemy"
                )
                paginated_flows = await apaginate(session, stmt, params=params)

            # Apply the same per-flow authz filter the non-paginated branch
            # uses so shared-project reads behave identically regardless of
            # page/size. Without this, a project READ grant would expose
            # every flow in the page even when finer-grained per-flow
            # policy (deny rules, lower-permission shares) should narrow
            # the result. OSS pass-through returns the input unchanged.
            # Only runs as the in-memory fallback: when a concrete prefilter is
            # available the SQL union above already narrowed the page (and
            # ``page.total``); this fallback path's ``page.total`` may overcount
            # when items are dropped — same caveat as ``read_flows``.
            if treat_as_shared and visibility_scope is None:
                paginated_flows.items = await filter_visible_resources(
                    current_user,
                    resource_type="flow",
                    candidates=list(paginated_flows.items),
                    domain_extractor=lambda flow: _resolve_authz_domain(project.workspace_id, flow.folder_id),
                    owner_extractor=lambda flow: flow.user_id,
                    act=FlowAction.READ,
                )

            return FolderWithPaginatedFlows(folder=FolderRead.model_validate(project), flows=paginated_flows)

        # If no pagination requested, return flows visible to the caller.
        if treat_as_shared:
            # A project share grant implies access to the project itself, but
            # per-flow policy (deny rules, lower scopes) still applies. Without
            # this, ``list(project.flows)`` would leak every flow in the project
            # regardless of finer-grained policy engine rules the plugin may
            # have. OSS pass-through returns the input list unchanged, so this
            # has no effect on default OSS installs.
            if visibility_scope is not None:
                # Eager-loaded ``project.flows`` constrained to (owned ⊕ visible)
                # by set membership — the same union as the SQL prefilter, applied
                # in memory because the relationship is already materialized
                # (still no per-row enforce, so no N+1).
                visible_flows = [
                    flow
                    for flow in project.flows
                    if flow.user_id == current_user.id
                    or resource_visible_in_scope(
                        resource_id=flow.id,
                        workspace_id=project.workspace_id,
                        project_id=flow.folder_id,
                        visibility=visibility_scope,
                    )
                ]
            else:
                visible_flows = await filter_visible_resources(
                    current_user,
                    resource_type="flow",
                    candidates=list(project.flows),
                    domain_extractor=lambda flow: _resolve_authz_domain(project.workspace_id, flow.folder_id),
                    owner_extractor=lambda flow: flow.user_id,
                    act=FlowAction.READ,
                )
        else:
            visible_flows = [flow for flow in project.flows if flow.user_id == current_user.id]
        # Convert without assigning the filtered list back to the ORM
        # relationship. ``Folder.flows`` owns delete-orphan cascade; mutating it
        # in this GET handler would delete every hidden flow when the request
        # session commits.
        project_read = FolderReadWithFlows.model_validate(project, from_attributes=True)
        project_read.flows = [FlowRead.model_validate(flow, from_attributes=True) for flow in visible_flows]
        return project_read  # noqa: TRY300 - conversion must happen while the ORM session is active

    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_READ_FAILED)) from e


async def _apply_project_update(
    *,
    session: DbSession,
    existing_project: Folder,
    project: FolderUpdate,
    current_user: User,
    background_tasks: BackgroundTasks,
) -> FolderRead:
    """Apply an in-place project update, shared by PATCH and the PUT upsert update branch.

    A rename onto a name the owner already uses fails loud as 409 *before* the row is mutated.
    Relying on the ``(user_id, name)`` constraint instead does not work here: assigning the name
    dirties the ORM row, the next query autoflushes, and ``handle_mcp_server_rename``'s blanket
    ``except Exception`` swallows the resulting IntegrityError — leaving the session needing
    rollback so the later flush raises PendingRollbackError, which reached callers as a 500
    carrying the SQL statement and bound parameters.

    A concurrent rename that slips between that check and the flush still hits the constraint;
    both callers map it through _handle_unique_constraint_error, so it also surfaces as a 409.

    Raises on deployment-guard errors; callers map those to their own status.
    """
    if (
        project.name is not None
        and project.name != existing_project.name
        and existing_project.name == STARTER_FOLDER_NAME
        and existing_project.user_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"The system-managed '{STARTER_FOLDER_NAME}' project cannot be renamed.",
        )

    # Rename collision -> 409, checked before the mutation (see docstring). Scoped to the project
    # owner because the constraint is ``(user_id, name)``; the constraint still backstops a
    # concurrent rename that slips between this check and the flush.
    if project.name is not None and project.name != existing_project.name:
        name_taken = (
            await session.exec(
                select(Folder.id).where(
                    Folder.name == project.name,
                    Folder.user_id == existing_project.user_id,
                    Folder.id != existing_project.id,
                )
            )
        ).first()
        if name_taken is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Project name must be unique")

    # Flow rollup uses the project owner — a non-owner editing a shared
    # project must touch the owner's flows, not the actor's same-folder
    # flows (which would be empty for a non-owner anyway).
    project_owner_id = existing_project.user_id
    result = await session.exec(
        select(Flow.id, Flow.is_component).where(
            Flow.folder_id == existing_project.id, Flow.user_id == project_owner_id
        )
    )
    flows_and_components = result.all()

    project.flows = [flow_id for flow_id, is_component in flows_and_components if not is_component]
    project.components = [flow_id for flow_id, is_component in flows_and_components if is_component]

    # Track if MCP Composer needs to be started or stopped
    should_start_mcp_composer = False
    should_stop_mcp_composer = False
    new_auth_type: str | None = None
    auth_settings_updated = False

    # Check if auth_settings is being updated
    if "auth_settings" in project.model_fields_set:  # Check if auth_settings was explicitly provided
        auth_result = handle_auth_settings_update(
            existing_project=existing_project,
            new_auth_settings=project.auth_settings,
        )

        should_start_mcp_composer = auth_result["should_start_composer"]
        should_stop_mcp_composer = auth_result["should_stop_composer"]
        new_auth_type = auth_result["new_auth_type"]
        auth_settings_updated = True

    # Handle project rename and corresponding MCP server rename
    if project.name and project.name != existing_project.name:
        old_project_name = existing_project.name
        existing_project.name = project.name

        if get_settings_service().settings.add_projects_to_mcp_servers:
            await handle_mcp_server_rename(existing_project, old_project_name, project.name, current_user, session)

    if project.description is not None:
        existing_project.description = project.description

    if project.parent_id is not None:
        # Validate the supplied parent references a folder owned by the project owner, so
        # shared-project writes cannot create cross-owner folder hierarchies.
        parent = (
            await session.exec(select(Folder).where(Folder.id == project.parent_id, Folder.user_id == project_owner_id))
        ).first()
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent project not found")
        existing_project.parent_id = project.parent_id

    session.add(existing_project)
    await session.flush()
    await session.refresh(existing_project)

    # Start MCP Composer if auth changed to OAuth
    if should_start_mcp_composer:
        await logger.adebug(
            "Auth settings changed to OAuth for project %s (%s), starting MCP Composer",
            existing_project.name,
            existing_project.id,
        )
        background_tasks.add_task(register_project_with_composer, existing_project)

    # Stop MCP Composer if auth changed FROM OAuth to something else
    elif should_stop_mcp_composer:
        await logger.ainfo(
            "Auth settings changed from OAuth for project %s (%s), stopping MCP Composer",
            existing_project.name,
            existing_project.id,
        )

        mcp_composer_service: MCPComposerService = cast(
            MCPComposerService, get_service(ServiceType.MCP_COMPOSER_SERVICE)
        )
        await mcp_composer_service.stop_project_composer(str(existing_project.id))

    # Sync MCP server config for apikey/none auth; OAuth is handled by MCP Composer above.
    if auth_settings_updated and new_auth_type in {"apikey", "none"}:
        try:
            await reconcile_mcp_server_for_auth_update(
                existing_project,
                new_auth_type,
                current_user,
                session,
            )
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            await logger.awarning(
                "Failed to reconcile MCP server config for project %s after auth update: %s",
                existing_project.id,
                e,
            )

    concat_project_components = project.components + project.flows

    # Both queries scope to the project owner. Every user gets their own folder named
    # DEFAULT_FOLDER_NAME (see get_or_create_default_folder), so an unscoped ``.first()`` can
    # return a *different* user's folder and this code would move the owner's excluded flows into
    # it, copying that stranger's workspace_id. get_default_folder_id() scopes the same lookup by
    # user_id; match it. If the owner has no default folder the move is skipped by the guard
    # below, which is the safe outcome.
    flows_ids = (
        await session.exec(
            select(Flow.id).where(Flow.folder_id == existing_project.id, Flow.user_id == project_owner_id)
        )
    ).all()

    excluded_flows = list(set(flows_ids) - set(project.flows))

    my_collection_project = (
        await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME, Folder.user_id == project_owner_id))
    ).first()
    flow_ids_for_sync = list(dict.fromkeys(excluded_flows + concat_project_components))
    authorized_flow_owner_ids: dict[UUID, UUID] = {}

    async def _move_flows_for_project_update() -> None:
        # Both SELECT and UPDATE must scope to the project owner — a
        # non-owner editing a shared project must touch the *owner's*
        # flows, not the actor's. The previous code filtered the SELECT
        # by ``current_user.id`` (returning zero rows for non-owners) but
        # then ran an UPDATE without any owner filter, so an id collision
        # would have moved cross-user flows without per-flow authz.
        # Scoping both statements to ``project_owner_id`` closes the gap.
        if my_collection_project:
            excluded_flow_rows = (
                await session.exec(
                    select(Flow.id, Flow.folder_id).where(
                        Flow.id.in_(excluded_flows),  # type: ignore[attr-defined]
                        Flow.user_id == project_owner_id,
                    )
                )
            ).all()
            authorized_flow_owner_ids.update((flow_id, project_owner_id) for flow_id, _folder_id in excluded_flow_rows)
            await ensure_flow_moves_allowed(
                session,
                flow_folder_pairs=list(excluded_flow_rows),
                new_folder_id=my_collection_project.id,
            )
            update_statement_my_collection = (
                update(Flow)
                .where(
                    Flow.id.in_(excluded_flows),  # type: ignore[attr-defined]
                    Flow.user_id == project_owner_id,
                )
                .values(folder_id=my_collection_project.id, workspace_id=my_collection_project.workspace_id)
            )
            await session.exec(update_statement_my_collection)

        if concat_project_components:
            component_flow_rows = (
                await session.exec(
                    select(Flow.id, Flow.folder_id).where(
                        Flow.id.in_(concat_project_components),  # type: ignore[attr-defined]
                        Flow.user_id == project_owner_id,
                    )
                )
            ).all()
            authorized_flow_owner_ids.update((flow_id, project_owner_id) for flow_id, _folder_id in component_flow_rows)
            await ensure_flow_moves_allowed(
                session,
                flow_folder_pairs=list(component_flow_rows),
                new_folder_id=existing_project.id,
            )
            update_statement_components = (
                update(Flow)
                .where(
                    Flow.id.in_(concat_project_components),  # type: ignore[attr-defined]
                    Flow.user_id == project_owner_id,
                )
                .values(folder_id=existing_project.id, workspace_id=existing_project.workspace_id)
            )
            await session.exec(update_statement_components)

    if flow_ids_for_sync:
        await retry_flow_operation_on_deployment_guard(
            db=session,
            flow_owner_ids=authorized_flow_owner_ids,
            operation=_move_flows_for_project_update,
        )
    else:
        await _move_flows_for_project_update()

    # Convert to FolderRead while session is still active to avoid detached instance errors
    return FolderRead.model_validate(existing_project, from_attributes=True)


def _folder_create_to_update(project: FolderCreate) -> FolderUpdate:
    """Map a ``FolderCreate`` (PUT upsert body) onto a ``FolderUpdate`` for the shared update core.

    Only fields explicitly set on the incoming body are carried over so the PUT update branch
    matches PATCH semantics (unset fields are left untouched). ``flows``/``components`` are not
    mapped because ``_apply_project_update`` recomputes them from the project's current DB
    contents; ``parent_id`` is not part of ``FolderCreate``.
    """
    # exclude_unset carries only fields explicitly set on the body; include restricts to the three
    # fields FolderUpdate shares with FolderCreate (flows/components/parent_id handled per docstring).
    data = project.model_dump(include={"name", "description", "auth_settings"}, exclude_unset=True)
    return FolderUpdate(**data)


@router.patch("/{project_id}", response_model=FolderRead, status_code=200)
async def update_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: FolderUpdate,  # Assuming FolderUpdate is a Pydantic model defining updatable fields
    current_user: CurrentActiveUser,
    background_tasks: BackgroundTasks,
):
    try:
        existing_project = await authorized_or_owner_scoped(
            session,
            Folder,
            id_column=Folder.id,
            resource_id=project_id,
            owner_column=Folder.user_id,
            owner_id=current_user.id,
        )
    except Exception as e:
        # authorized_or_owner_scoped runs SQL, so the raw str() would carry the statement and its
        # bound parameters — sanitize like the rest of this module.
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_UPDATE_FAILED)) from e

    if not existing_project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        await ensure_project_permission(
            current_user,
            ProjectAction.WRITE,
            project_id=project_id,
            project_user_id=existing_project.user_id,
            workspace_id=existing_project.workspace_id,
        )
    except HTTPException as exc:
        # A caller who can read this project already knows it exists, so the
        # 404 mask only hides *why* the edit failed. Match the flow-edit path:
        # readable -> 403 with a permission message, unreadable -> 404.
        raise await deny_to_404_unless_readable(
            exc,
            lambda: ensure_project_permission(
                current_user,
                ProjectAction.READ,
                project_id=project_id,
                project_user_id=existing_project.user_id,
                workspace_id=existing_project.workspace_id,
            ),
            denied_detail=PROJECT_WRITE_DENIED_DETAIL,
            not_found_detail="Project not found",
        ) from exc

    try:
        return await _apply_project_update(
            session=session,
            existing_project=existing_project,
            project=project,
            current_user=current_user,
            background_tasks=background_tasks,
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=update_project project_id={project_id}",
        )
        # Same mapping as the PUT upsert so both verbs answer a constraint backstop identically:
        # 409 for a unique violation that slipped past the pre-check, sanitized 500 otherwise.
        raise _handle_unique_constraint_error(e, status_code=status.HTTP_409_CONFLICT) from e


@router.put(
    "/{project_id}",
    response_model=FolderRead,
    # The handler returns 201 on create and 200 on update, so the 201 needs declaring for the
    # schema to be accurate for generated clients (FastAPI infers only the 200 default).
    responses={status.HTTP_201_CREATED: {"model": FolderRead, "description": "Project created."}},
)
async def upsert_project(
    *,
    session: DbSession,
    project_id: UUID,
    project: FolderCreate,
    current_user: CurrentActiveUser,
    background_tasks: BackgroundTasks,
):
    """Create or update a project with a specific ID (upsert).

    Returns 201 for creation, 200 for update. Returns 404 if owned by another user (avoids
    leaking existence). A name collision fails loud as 409 on both the create and update paths
    (unlike POST, which auto-renames).

    ``workspace_id`` is out of scope: ``FolderCreate`` cannot express it, so a synced project
    inherits ``NULL`` exactly like one created via POST. Workspace assignment is not part of the
    upsert contract.
    """
    from fastapi.responses import JSONResponse

    try:
        # Existence check WITHOUT user filter to distinguish ownership vs CREATE.
        existing_project = (await session.exec(select(Folder).where(Folder.id == project_id))).first()

        if existing_project is not None:
            # Block non-owner upsert when cross-user fetch is off (UUID privacy).
            from langflow.services.deps import get_authorization_service

            authz = get_authorization_service()
            can_widen = await authz.supports_cross_user_fetch() and await authz.is_enabled()
            if not can_widen and existing_project.user_id != current_user.id:
                raise HTTPException(status_code=404, detail="Project not found")

            try:
                await ensure_project_permission(
                    current_user,
                    ProjectAction.WRITE,
                    project_id=project_id,
                    project_user_id=existing_project.user_id,
                    workspace_id=existing_project.workspace_id,
                )
            except HTTPException as exc:
                raise deny_to_404(exc, detail="Project not found") from exc

            # The update core recomputes membership from the project's current flows, so
            # flows_list/components_list on the body cannot be honored here. Fail loud rather
            # than silently discarding them (unlike the CREATE branch, which moves them).
            if project.flows_list or project.components_list:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "flows_list/components_list are not supported when updating an existing "
                        "project; set a flow's project via PUT /api/v1/flows/{flow_id} instead."
                    ),
                )

            # Reuse the PATCH update core, which raises the 409 on a rename collision itself.
            # Map the PUT body onto a FolderUpdate so unset fields are left untouched.
            folder_read = await _apply_project_update(
                session=session,
                existing_project=existing_project,
                project=_folder_create_to_update(project),
                current_user=current_user,
                background_tasks=background_tasks,
            )
            status_code = 200
        else:
            # CREATE path - project doesn't exist. Create it at the caller-specified id and fail
            # loud (409) on a name collision instead of auto-renaming.
            await ensure_project_permission(
                current_user, ProjectAction.CREATE, workspace_id=getattr(project, "workspace_id", None)
            )
            folder_read = await _new_project(
                session=session,
                project=project,
                current_user=current_user,
                project_id=project_id,
                fail_on_name_conflict=True,
            )
            status_code = 201

        return JSONResponse(status_code=status_code, content=jsonable_encoder(folder_read))

    except HTTPException:
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=upsert_project project_id={project_id}",
        )
        # The shared helper maps a unique violation on either backend (409, with a detail naming
        # the constraint that fired) and sanitizes anything else into a 500.
        raise _handle_unique_constraint_error(e, status_code=status.HTTP_409_CONFLICT) from e


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    async def _load_project() -> Folder | None:
        return await authorized_or_owner_scoped(
            session,
            Folder,
            id_column=Folder.id,
            resource_id=project_id,
            owner_column=Folder.user_id,
            owner_id=current_user.id,
        )

    try:
        project = await _load_project()
    except Exception as e:
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_READ_FAILED)) from e

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        await ensure_project_permission(
            current_user,
            ProjectAction.DELETE,
            project_id=project_id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise await deny_to_404_unless_readable(
            exc,
            lambda: ensure_project_permission(
                current_user,
                ProjectAction.READ,
                project_id=project_id,
                project_user_id=project.user_id,
                workspace_id=project.workspace_id,
            ),
            denied_detail=PROJECT_DELETE_DENIED_DETAIL,
            not_found_detail="Project not found",
        ) from exc

    # Prevent deletion of projects managed by Langflow. The ownerless Starter
    # Project is also a stable authorization boundary for bundled examples.
    is_system_starter = project.name == STARTER_FOLDER_NAME and project.user_id is None
    if project.name == ASSISTANT_FOLDER_NAME or is_system_starter:
        msg = f"Cannot delete the '{project.name}' folder, which contains pre-built flows."
        await logger.adebug("Cannot delete the '%s' folder, which contains pre-built flows.", project.name)
        raise HTTPException(
            status_code=403,
            detail=msg,
        )

    # Cascade and deployment guards operate over the project owner's flows —
    # a non-owner with a delete share must remove the owner's resources, not
    # only their own (which is the empty set for a non-owner).
    project_owner_id = project.user_id

    def _make_delete_operation(target: Folder):
        async def _delete_project_operation() -> None:
            flows = (
                await session.exec(select(Flow).where(Flow.folder_id == project_id, Flow.user_id == project_owner_id))
            ).all()
            if len(flows) > 0:
                for flow in flows:
                    await cascade_delete_flow(session, flow.id)

            await check_project_has_deployments(session, project_id=project_id)
            await session.delete(target)
            # Flush eagerly so guard/constraint errors surface in-request rather than at teardown commit.
            await session.flush()

        return _delete_project_operation

    # LE-2020: a retry runs in a brand new transaction, and the rollback that
    # precedes it expires every instance loaded so far. The user and the row are
    # therefore re-read with awaits — a plain attribute read on expired state
    # would lazy-load outside the greenlet context and raise MissingGreenlet.
    async def _delete_attempt(attempt: int) -> None:
        if attempt == 0:
            target = project
        else:
            await session.refresh(current_user)
            target = await _load_project()
        if target is None:
            return
        await cleanup_mcp_on_delete(target, project_id, current_user, session)
        await retry_project_operation_on_deployment_guard(
            db=session,
            user_id=project_owner_id,
            project_id=project_id,
            operation=_make_delete_operation(target),
        )

    try:
        await run_with_lock_retry(_delete_attempt, session=session, description=f"delete_project {project_id}")
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=delete_project project_id={project_id}",
            remap=remap_flow_guard_for_project_delete,
        )
        if is_database_lock_error(e):
            # Contention that outlived the retry budget is transient, not a
            # server fault: 503 + Retry-After lets a client retry correctly.
            await logger.awarning("op=delete_project project_id=%s exhausted lock retries", project_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=PROJECT_DELETE_BUSY,
                headers={"Retry-After": "1"},
            ) from e
        await logger.aexception("op=delete_project project_id=%s failed with %s", project_id, type(e).__name__)
        raise HTTPException(status_code=500, detail=sanitize_database_error(e, PROJECT_DELETE_FAILED)) from e


@router.get("/download/{project_id}", status_code=200)
async def download_file(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    """Download all flows from project as a zip file."""
    # Fetch the project row first so the authorization call carries the
    # owner id (for the owner-override path) and the workspace id (for the
    # project-domain resolver). When share-aware fetch is supported, the
    # row is loaded by id and ``ensure_project_permission`` decides access;
    # otherwise the query stays owner-scoped.
    project = await authorized_or_owner_scoped(
        session,
        Folder,
        id_column=Folder.id,
        resource_id=project_id,
        owner_column=Folder.user_id,
        owner_id=current_user.id,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await ensure_project_permission(
        current_user,
        ProjectAction.READ,
        project_id=project_id,
        project_user_id=project.user_id,
        workspace_id=project.workspace_id,
    )
    return await download_project_flows(
        session=session,
        project_id=project_id,
        current_user=current_user,
        project_owner_id=project.user_id,
    )


@router.post("/upload/", response_model=list[FlowRead], status_code=201)
async def upload_file(
    *,
    session: DbSession,
    file: Annotated[UploadFile | None, File()] = None,
    current_user: CurrentActiveUser,
):
    """Upload flows from a file.

    Accepts either a JSON file with project metadata (folder_name, folder_description, flows)
    or a ZIP file containing individual flow JSON files (as produced by the download endpoint).
    """
    await ensure_project_permission(current_user, ProjectAction.CREATE)
    return await upload_project_flows(session=session, file=file, current_user=current_user)
