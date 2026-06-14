import warnings
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi_pagination import Params
from fastapi_pagination.ext.sqlmodel import apaginate
from lfx.log.logger import logger
from lfx.services.mcp_composer.service import MCPComposerService
from sqlalchemy import or_, update
from sqlalchemy.orm import selectinload
from sqlmodel import select

from langflow.api.utils import (
    CurrentActiveUser,
    DbSession,
    cascade_delete_flow,
    custom_params,
)
from langflow.api.v1.auth_helpers import handle_auth_settings_update
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
)
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.authorization.utils import _resolve_authz_domain
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
    FolderRead,
    FolderReadWithFlows,
    FolderUpdate,
)
from langflow.services.database.models.folder.pagination_model import FolderWithPaginatedFlows
from langflow.services.deps import get_service, get_settings_service
from langflow.services.schema import ServiceType

router = APIRouter(prefix="/projects", tags=["Projects"])


def _escape_like(value: str) -> str:
    """Escape LIKE wildcards and the escape character itself."""
    return value.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")


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
        new_project = Folder.model_validate(project, from_attributes=True)
        new_project.user_id = current_user.id
        # First check if the project.name is unique
        # there might be flows with name like: "MyFlow", "MyFlow (1)", "MyFlow (2)"
        # so we need to check if the name is unique with `like` operator
        # if we find a flow with the same name, we add a number to the end of the name
        # based on the highest number found
        if (
            await session.exec(
                statement=select(Folder).where(Folder.name == new_project.name).where(Folder.user_id == current_user.id)
            )
        ).first():
            escaped_project_name = _escape_like(new_project.name)
            project_results = await session.exec(
                select(Folder).where(
                    Folder.name.like(f"{escaped_project_name}%", escape="\\"),  # type: ignore[attr-defined]
                    Folder.user_id == current_user.id,
                )
            )
            if project_results:
                project_names = [project.name for project in project_results]
                project_numbers = []
                for name in project_names:
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
                await ensure_flow_moves_allowed(
                    session,
                    flow_folder_pairs=list(component_flows),
                    new_folder_id=new_project.id,
                )
                update_statement_components = (
                    update(Flow)
                    .where(Flow.id.in_(project.components_list), Flow.user_id == current_user.id)  # type: ignore[attr-defined]
                    .values(folder_id=new_project.id)
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
                await ensure_flow_moves_allowed(
                    session,
                    flow_folder_pairs=list(project_flows),
                    new_folder_id=new_project.id,
                )
                update_statement_flows = (
                    update(Flow)
                    .where(Flow.id.in_(project.flows_list), Flow.user_id == current_user.id)  # type: ignore[attr-defined]
                    .values(folder_id=new_project.id)
                )
                await session.exec(update_statement_flows)

        if flow_ids_for_sync:
            await retry_flow_operation_on_deployment_guard(
                db=session,
                user_id=current_user.id,
                flow_ids=flow_ids_for_sync,
                operation=_move_flows_into_project,
            )
        else:
            await _move_flows_into_project()

        # Convert to FolderRead while session is still active to avoid detached instance errors
        folder_read = FolderRead.model_validate(new_project, from_attributes=True)
    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message="op=create_project",
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

    return folder_read


@router.get("/", response_model=list[FolderRead], status_code=200)
async def read_projects(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    try:
        projects = (
            await session.exec(
                select(Folder).where(
                    or_(Folder.user_id == current_user.id, Folder.user_id == None)  # noqa: E711
                )
            )
        ).all()
        projects = [project for project in projects if project.name != STARTER_FOLDER_NAME]
        # When AUTHZ_ENABLED=true, drop projects the user can't read. OSS
        # default is pass-through; the authorization plugin honors role + share grants.
        # ``domain_extractor`` groups requests by workspace so each batch is
        # evaluated against the right policy tuple. Projects are the resource
        # itself, so the domain falls back to workspace (or ``*``).
        projects = await filter_visible_resources(
            current_user,
            resource_type="project",
            candidates=list(projects),
            domain_extractor=lambda project: _resolve_authz_domain(project.workspace_id, None),
            owner_extractor=lambda project: project.user_id,
            act=ProjectAction.READ,
        )
        sorted_projects = sorted(projects, key=lambda x: x.name != DEFAULT_FOLDER_NAME)

        # Convert to FolderRead while session is still active to avoid detached instance errors
        return [FolderRead.model_validate(project, from_attributes=True) for project in sorted_projects]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e

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

        # Check if pagination is explicitly requested by the user (both page and size provided)
        if page is not None and size is not None:
            stmt = select(Flow).where(Flow.folder_id == project_id)
            if not treat_as_shared:
                stmt = stmt.where(Flow.user_id == current_user.id)

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
            # ``page.total`` may overcount when items are dropped — same
            # caveat as the paginated branch of ``read_flows``; SQL-level
            # prefiltering via authz_share lands in Phase 3.
            if treat_as_shared:
                paginated_flows.items = await filter_visible_resources(
                    current_user,
                    resource_type="flow",
                    candidates=list(paginated_flows.items),
                    domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
                    owner_extractor=lambda flow: flow.user_id,
                    act=FlowAction.READ,
                )

            return FolderWithPaginatedFlows(folder=FolderRead.model_validate(project), flows=paginated_flows)

        # If no pagination requested, return flows visible to the caller.
        if treat_as_shared:
            # A project share grant implies access to the project itself, but
            # per-flow policy (deny rules, lower scopes) still applies. Without
            # this call, ``list(project.flows)`` would leak every flow in the
            # project regardless of finer-grained policy engine rules the plugin may
            # have. OSS pass-through returns the input list unchanged, so this
            # has no effect on default OSS installs.
            visible_flows = await filter_visible_resources(
                current_user,
                resource_type="flow",
                candidates=list(project.flows),
                domain_extractor=lambda flow: _resolve_authz_domain(flow.workspace_id, flow.folder_id),
                owner_extractor=lambda flow: flow.user_id,
                act=FlowAction.READ,
            )
        else:
            visible_flows = [flow for flow in project.flows if flow.user_id == current_user.id]
        project.flows = visible_flows

        # Convert to FolderReadWithFlows while session is still active to avoid detached instance errors
        return FolderReadWithFlows.model_validate(project, from_attributes=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


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
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        raise deny_to_404(exc, detail="Project not found") from exc

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

    try:
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

        flows_ids = (await session.exec(select(Flow.id).where(Flow.folder_id == existing_project.id))).all()

        excluded_flows = list(set(flows_ids) - set(project.flows))

        my_collection_project = (await session.exec(select(Folder).where(Folder.name == DEFAULT_FOLDER_NAME))).first()
        flow_ids_for_sync = list(dict.fromkeys(excluded_flows + concat_project_components))

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
                    .values(folder_id=my_collection_project.id)
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
                    .values(folder_id=existing_project.id)
                )
                await session.exec(update_statement_components)

        if flow_ids_for_sync:
            await retry_flow_operation_on_deployment_guard(
                db=session,
                user_id=current_user.id,
                flow_ids=flow_ids_for_sync,
                operation=_move_flows_for_project_update,
            )
        else:
            await _move_flows_for_project_update()

        # Convert to FolderRead while session is still active to avoid detached instance errors
        folder_read = FolderRead.model_validate(existing_project, from_attributes=True)

    except HTTPException:
        # Re-raise HTTP exceptions (like 409 conflicts) without modification
        raise
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=update_project project_id={project_id}",
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

    return folder_read


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    *,
    session: DbSession,
    project_id: UUID,
    current_user: CurrentActiveUser,
):
    try:
        project = await authorized_or_owner_scoped(
            session,
            Folder,
            id_column=Folder.id,
            resource_id=project_id,
            owner_column=Folder.user_id,
            owner_id=current_user.id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

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
        raise deny_to_404(exc, detail="Project not found") from exc

    # Prevent deletion of the Langflow Assistant folder
    if project.name == ASSISTANT_FOLDER_NAME:
        msg = f"Cannot delete the '{ASSISTANT_FOLDER_NAME}' folder, that contains pre-built flows."
        await logger.adebug("Cannot delete the '%s' folder, that contains pre-built flows.", ASSISTANT_FOLDER_NAME)
        raise HTTPException(
            status_code=403,
            detail=msg,
        )

    await cleanup_mcp_on_delete(project, project_id, current_user, session)

    # Cascade and deployment guards operate over the project owner's flows —
    # a non-owner with a delete share must remove the owner's resources, not
    # only their own (which is the empty set for a non-owner).
    project_owner_id = project.user_id

    async def _delete_project_operation() -> None:
        flows = (
            await session.exec(select(Flow).where(Flow.folder_id == project_id, Flow.user_id == project_owner_id))
        ).all()
        if len(flows) > 0:
            for flow in flows:
                await cascade_delete_flow(session, flow.id)

        await check_project_has_deployments(session, project_id=project_id)
        await session.delete(project)
        # Flush eagerly so guard/constraint errors surface in-request rather than at teardown commit.
        await session.flush()

    try:
        await retry_project_operation_on_deployment_guard(
            db=session,
            user_id=project_owner_id,
            project_id=project_id,
            operation=_delete_project_operation,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        await araise_if_deployment_guard_error_or_skip(
            e,
            log_message=f"op=delete_project project_id={project_id}",
            remap=remap_flow_guard_for_project_delete,
        )
        raise HTTPException(status_code=500, detail=str(e)) from e


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
    return await download_project_flows(session=session, project_id=project_id, current_user=current_user)


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
