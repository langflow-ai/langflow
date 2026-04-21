from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi_pagination import Params
from lfx.log.logger import logger
from lfx.services.adapters.deployment.exceptions import (
    DeploymentNotFoundError,
    DeploymentServiceError,
    http_status_for_deployment_error,
)
from lfx.services.adapters.deployment.schema import (
    DeploymentListParams,
    DeploymentListTypesResult,
    DeploymentType,
    DeploymentUpdateResult,
)
from pydantic import AfterValidator, StringConstraints

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.mappers.deployments import get_deployment_mapper
from langflow.api.v1.mappers.deployments.helpers import (
    apply_flow_version_patch_attachments,
    attach_flow_versions,
    deployment_pagination_params,
    flow_version_ids_for_flows,
    get_deployment_row_or_404,
    get_owned_provider_account_or_404,
    handle_adapter_errors,
    list_deployment_flow_versions_synced,
    list_deployments_synced,
    page_offset,
    raise_http_for_value_error,
    resolve_adapter_from_deployment,
    resolve_adapter_mapper_from_deployment,
    resolve_added_snapshot_bindings_for_update,
    resolve_deployment_adapter,
    resolve_flow_version_patch_for_update,
    resolve_project_id_for_deployment_create,
    resolve_snapshot_map_for_create,
    rollback_provider_create,
    rollback_provider_update,
    validate_project_scoped_flow_version_ids,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentFlowVersionListResponse,
    DeploymentGetResponse,
    DeploymentListResponse,
    DeploymentLlmListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountListResponse,
    DeploymentProviderAccountUpdateRequest,
    DeploymentSnapshotListResponse,
    DeploymentStatusResponse,
    DeploymentTypeListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    FlowIdsQuery,
    FlowVersionIdsQuery,
    RunCreateRequest,
    RunCreateResponse,
    RunStatusResponse,
    SnapshotUpdateRequest,
    SnapshotUpdateResponse,
)
from langflow.services.adapters.deployment.context import deployment_provider_scope
from langflow.services.database.models.deployment.crud import (
    count_deployments_by_provider,
    delete_deployment_by_id,
    deployment_name_exists,
    get_deployment_by_resource_key,
)
from langflow.services.database.models.deployment.crud import (
    create_deployment as create_deployment_db,
)
from langflow.services.database.models.deployment.crud import (
    update_deployment as update_deployment_db,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    count_provider_accounts as count_provider_account_rows,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    create_provider_account_from_model as create_provider_account_row,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    delete_provider_account as delete_provider_account_row,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    get_provider_account_by_id as get_provider_account_row_by_id,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    list_provider_accounts as list_provider_account_rows,
)
from langflow.services.database.models.deployment_provider_account.crud import (
    update_provider_account as update_provider_account_row,
)
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    AttachmentConflictError,
    delete_unbound_attachments,
    get_attachment_by_provider_snapshot_id,
    list_deployment_attachments,
    list_deployment_attachments_for_flow_version_ids,
    update_flow_version_by_provider_snapshot_id,
)

router = APIRouter(prefix="/deployments", tags=["Deployments"], include_in_schema=False)

DeploymentProviderAccountIdQuery = Annotated[
    UUID,
    Query(description="Langflow DB provider-account UUID (`deployment_provider_account.id`)."),
]
DeploymentProviderAccountIdPath = Annotated[
    UUID,
    Path(description="Langflow DB provider-account UUID (`deployment_provider_account.id`)."),
]
DeploymentIdPath = Annotated[
    UUID,
    Path(description="Langflow DB deployment UUID (`deployment.id`)."),
]
ProjectIdQuery = Annotated[
    UUID | None,
    Query(description="Optional project (folder) id. Filters deployments to this project."),
]
DeploymentIdQuery = Annotated[
    UUID,
    Query(description="Langflow DB deployment UUID (`deployment.id`)."),
]
SnapshotNameQueryItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def _dedupe_snapshot_names(values: list[str] | None) -> list[str] | None:
    if values is None:
        return None
    return list(dict.fromkeys(values))


SnapshotNamesQuery = Annotated[list[SnapshotNameQueryItem] | None, AfterValidator(_dedupe_snapshot_names)]
IncludeProviderDeleteQuery = Annotated[
    bool,
    Query(
        description=(
            "When true (default), deletes the deployment resource (e.g., agent) on the provider, "
            "then removes the local DB row. Other provider-managed resources "
            "(for example, tools and connections) are NOT deleted. "
            "When false, only the local Langflow DB row is removed; "
            "nothing is changed on the provider."
        ),
    ),
]


def _field_was_explicitly_set(model: object, field_name: str) -> bool:
    """Return True when a Pydantic-style model explicitly received *field_name*.

    Falls back to False for mocks and non-Pydantic objects so route handler unit
    tests that use ``MagicMock`` payloads keep their previous behavior.
    """
    fields_set = getattr(model, "model_fields_set", None)
    return isinstance(fields_set, set) and field_name in fields_set


def _raise_http_for_provider_account_value_error(exc: ValueError) -> None:
    message = str(exc).lower()
    if "already exists" in message or "conflicts with an existing record" in message:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Provider account is already tracked by user.",
        ) from exc
    raise_http_for_value_error(exc)


async def _count_provider_deployments_after_reconciliation(
    *,
    session: DbSession,
    provider_account,
    user_id: UUID,
) -> int:
    """Return remaining deployments after best-effort stale-row reconciliation."""
    deployment_count = await count_deployments_by_provider(
        session,
        user_id=user_id,
        deployment_provider_account_id=provider_account.id,
    )
    if deployment_count <= 0:
        return 0

    try:
        deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
        deployment_mapper = get_deployment_mapper(provider_account.provider_key)
        with deployment_provider_scope(provider_account.id):
            _, deployment_count = await list_deployments_synced(
                deployment_adapter=deployment_adapter,
                deployment_mapper=deployment_mapper,
                user_id=user_id,
                provider_id=provider_account.id,
                db=session,
                page=1,
                size=deployment_count,
                deployment_type=None,
            )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to reconcile deployments before deleting provider account %s; falling back to local count.",
            provider_account.id,
            exc_info=True,
        )

    return deployment_count


async def _delete_local_deployment_row_with_commit_retry(
    *,
    session: DbSession,
    deployment_id: UUID,
    user_id: UUID,
    resource_key: str,
) -> None:
    """Delete the local deployment row, retrying once if the commit fails.

    Delete is provider-first, so by the time this helper runs the provider
    resource is already gone (or was already missing). If the first DB commit
    fails, retry the local delete once after a rollback so we do not strand a
    stale Langflow row that still blocks later reads or provider-account
    deletion.
    """
    try:
        await delete_deployment_by_id(session, user_id=user_id, deployment_id=deployment_id)
        await session.commit()
    except Exception:  # noqa: BLE001
        await session.rollback()
        logger.warning(
            "Local deployment cleanup failed for deployment %s (resource_key=%s) after provider delete; retrying.",
            deployment_id,
            resource_key,
            exc_info=True,
        )
        try:
            await delete_deployment_by_id(session, user_id=user_id, deployment_id=deployment_id)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.exception(
                "Retrying local deployment cleanup failed for deployment %s (resource_key=%s) after provider delete.",
                deployment_id,
                resource_key,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Deployment was deleted from the provider, but local cleanup failed. Retry the delete request.",
            ) from exc


@router.post(
    "/providers",
    response_model=DeploymentProviderAccountGetResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Deployment Providers"],
)
async def create_provider_account(
    session: DbSession,
    payload: DeploymentProviderAccountCreateRequest,
    current_user: CurrentActiveUser,
):
    deployment_mapper = get_deployment_mapper(payload.provider_key)
    deployment_adapter = resolve_deployment_adapter(payload.provider_key)

    with handle_adapter_errors(mapper=deployment_mapper):
        verify_input = deployment_mapper.resolve_verify_credentials_for_create(payload=payload)
        await deployment_adapter.verify_credentials(
            user_id=current_user.id,
            payload=verify_input,
        )

    try:
        provider_account_to_create = deployment_mapper.resolve_provider_account_create(
            payload=payload,
            user_id=current_user.id,
        )
        provider_account = await create_provider_account_row(
            session,
            provider_account=provider_account_to_create,
        )
    except ValueError as exc:
        _raise_http_for_provider_account_value_error(exc)
    return deployment_mapper.resolve_provider_account_response(provider_account)


@router.get("/providers", response_model=DeploymentProviderAccountListResponse, tags=["Deployment Providers"])
async def list_provider_accounts(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    offset = page_offset(page, size)
    provider_accounts = await list_provider_account_rows(session, user_id=current_user.id, offset=offset, limit=size)
    total = await count_provider_account_rows(session, user_id=current_user.id)
    return DeploymentProviderAccountListResponse(
        provider_accounts=[
            get_deployment_mapper(item.provider_key).resolve_provider_account_response(item)
            for item in provider_accounts
        ],
        page=page,
        size=size,
        total=total,
    )


@router.get(
    "/providers/{provider_id}",
    response_model=DeploymentProviderAccountGetResponse,
    tags=["Deployment Providers"],
)
async def get_provider_account(
    provider_id: DeploymentProviderAccountIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    provider_account = await get_provider_account_row_by_id(session, provider_id=provider_id, user_id=current_user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    return get_deployment_mapper(provider_account.provider_key).resolve_provider_account_response(provider_account)


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Deployment Providers"],
)
async def delete_provider_account(
    provider_id: DeploymentProviderAccountIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id,
        user_id=current_user.id,
        db=session,
    )
    deployment_count = await _count_provider_deployments_after_reconciliation(
        session=session,
        provider_account=provider_account,
        user_id=current_user.id,
    )
    if deployment_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete provider account while deployments still exist.",
        )
    try:
        await delete_provider_account_row(session, provider_account=provider_account)
    except ValueError as exc:
        _raise_http_for_provider_account_value_error(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/providers/{provider_id}",
    response_model=DeploymentProviderAccountGetResponse,
    tags=["Deployment Providers"],
)
async def update_provider_account(
    provider_id: DeploymentProviderAccountIdPath,
    session: DbSession,
    payload: DeploymentProviderAccountUpdateRequest,
    current_user: CurrentActiveUser,
):
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id,
        user_id=current_user.id,
        db=session,
    )

    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    verify_input = None
    if _field_was_explicitly_set(payload, "provider_data"):
        deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
        try:
            verify_input = deployment_mapper.resolve_verify_credentials_for_update(
                payload=payload,
                existing_account=provider_account,
            )
        except ValueError as exc:
            _raise_http_for_provider_account_value_error(exc)
        except NotImplementedError as exc:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="This operation is not supported by the deployment provider.",
            ) from exc
        if verify_input is not None:
            with handle_adapter_errors(mapper=deployment_mapper):
                await deployment_adapter.verify_credentials(
                    user_id=current_user.id,
                    payload=verify_input,
                )

    try:
        update_kwargs = deployment_mapper.resolve_provider_account_update(
            payload=payload,
            existing_account=provider_account,
        )
        updated = await update_provider_account_row(
            session,
            provider_account=provider_account,
            **update_kwargs,
        )
    except ValueError as exc:
        _raise_http_for_provider_account_value_error(exc)
    return deployment_mapper.resolve_provider_account_response(updated)


@router.post("", response_model=DeploymentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    session: DbSession,
    payload: DeploymentCreateRequest,
    current_user: CurrentActiveUser,
):
    provider_id = payload.provider_id
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id,
        user_id=current_user.id,
        db=session,
    )
    # fail fast if the deployment name already exists
    # we could have races but that is more
    # acceptable than provider-side rollback failure
    if await deployment_name_exists(
        session,
        user_id=current_user.id,
        deployment_provider_account_id=provider_id,
        name=payload.name,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A deployment named '{payload.name}' already exists. "
            "Please choose a different name or delete the existing deployment first.",
        )

    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    existing_resource_key = deployment_mapper.util_existing_deployment_resource_key_for_create(payload)
    if existing_resource_key is not None:
        existing_deployment = await get_deployment_by_resource_key(
            session,
            user_id=current_user.id,
            deployment_provider_account_id=provider_id,
            resource_key=str(existing_resource_key),
        )
        if existing_deployment is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The agent '{existing_resource_key}' is already managed by Langflow. "
                "Update it to make changes, or delete the existing deployment first.",
            )
    should_mutate_existing_resource = (
        existing_resource_key is not None
        and deployment_mapper.util_should_mutate_provider_for_existing_deployment_create(payload)
    )
    should_create_provider_resource = existing_resource_key is None
    project_id = await resolve_project_id_for_deployment_create(payload=payload, user_id=current_user.id, db=session)
    flow_version_ids = deployment_mapper.util_create_flow_version_ids(payload)
    await validate_project_scoped_flow_version_ids(
        flow_version_ids=flow_version_ids,
        user_id=current_user.id,
        project_id=project_id,
        db=session,
    )
    if should_create_provider_resource:
        adapter_payload = await deployment_mapper.resolve_deployment_create(
            user_id=current_user.id,
            project_id=project_id,
            db=session,
            payload=payload,
        )
        with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_id):
            provider_create_result = await deployment_adapter.create(
                user_id=current_user.id,
                payload=adapter_payload,
                db=session,
            )
    else:
        # Existing-resource create starts as DB-only onboarding: no provider
        # mutation is performed and created_* response fields stay empty.
        provider_create_result = deployment_mapper.util_create_result_from_existing_resource(
            existing_resource_key=str(existing_resource_key),
        )
        if should_mutate_existing_resource:
            # When create payload includes add_flows/upsert_tools, run provider
            # update and normalize the update result into create-style created_*.
            adapter_payload = await deployment_mapper.resolve_deployment_update_for_existing_create(
                user_id=current_user.id,
                project_id=project_id,
                db=session,
                payload=payload,
            )
            with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_id):
                provider_update_result: DeploymentUpdateResult = await deployment_adapter.update(
                    deployment_id=existing_resource_key,
                    payload=adapter_payload,
                    user_id=current_user.id,
                    db=session,
                )
            provider_create_result = deployment_mapper.util_create_result_from_existing_update(
                existing_resource_key=str(existing_resource_key),
                result=provider_update_result,
            )
    # if we get here, the deployment was created successfully in the provider
    # so we need to create the deployment row and attach the flow versions
    # in the DB
    try:
        deployment_row = await create_deployment_db(
            session,
            user_id=current_user.id,
            project_id=project_id,
            deployment_provider_account_id=provider_id,
            resource_key=str(provider_create_result.id),
            name=payload.name,
            deployment_type=payload.type,
            description=payload.description or None,
        )

        snapshot_id_by_flow_version_id: dict[UUID, str] = {}
        if flow_version_ids:
            snapshot_id_by_flow_version_id = resolve_snapshot_map_for_create(
                deployment_mapper=deployment_mapper,
                result=provider_create_result,
                flow_version_ids=flow_version_ids,
            )
        await attach_flow_versions(
            flow_version_ids=flow_version_ids,
            user_id=current_user.id,
            deployment_row_id=deployment_row.id,
            snapshot_id_by_flow_version_id=snapshot_id_by_flow_version_id,
            db=session,
        )

        await session.commit()
    except Exception as exc:
        # Compensate: delete the provider resource so it doesn't become orphaned.
        # Only the deployment resource itself is deleted (e.g. the WXO agent).
        # Secondary resources (snapshots/tools, configs) may remain orphaned --
        # this is intentional because snapshots/configs may be shared across deployments,
        # making cascade-delete unsafe.
        await session.rollback()
        if should_create_provider_resource:
            await rollback_provider_create(
                deployment_adapter=deployment_adapter,
                provider_id=provider_id,
                resource_id=provider_create_result.id,
                provider_result=provider_create_result.provider_result,
                user_id=current_user.id,
                db=session,
            )
        elif should_mutate_existing_resource:
            await rollback_provider_create(
                deployment_adapter=deployment_adapter,
                provider_id=provider_id,
                resource_id=str(existing_resource_key),
                provider_result=provider_create_result.provider_result,
                allow_delete_fallback=False,
                user_id=current_user.id,
                db=session,
            )
        if isinstance(exc, AttachmentConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise
    return deployment_mapper.shape_deployment_create_result(
        provider_create_result, deployment_row, provider_key=provider_account.provider_key
    )


# exclude none as its associated with
# irrelevant fields. If in the future
# we want to include nulls, we can always
# transisiton to that.
@router.get(
    "",
    response_model=DeploymentListResponse,
    response_model_exclude_none=True,
)
async def list_deployments(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSession,
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends(deployment_pagination_params)],
    deployment_type: Annotated[DeploymentType | None, Query()] = None,
    *,
    load_from_provider: Annotated[
        bool,
        Query(
            description=("When true, list deployments directly from the provider (bypassing Langflow deployment rows).")
        ),
    ] = False,
    flow_version_ids: Annotated[
        FlowVersionIdsQuery,
        Query(
            description=(
                "Optional Langflow flow version ids (pass as repeated query params, "
                "e.g. ?flow_version_ids=id1&flow_version_ids=id2). When provided, "
                "deployments are filtered to those with at least one matching "
                "attachment (OR semantics across ids). "
                "Mutually exclusive with flow_ids."
            )
        ),
    ] = None,
    flow_ids: Annotated[
        FlowIdsQuery,
        Query(
            description=(
                "Optional flow ids (pass as repeated query params, "
                "e.g. ?flow_ids=id1). Currently limited to 1 value. "
                "When provided, deployments are filtered to those attached "
                "to versions of the specified flow(s). "
                "Mutually exclusive with flow_version_ids."
            )
        ),
    ] = None,
    project_id: ProjectIdQuery = None,
):
    if flow_ids and flow_version_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="flow_ids and flow_version_ids are mutually exclusive.",
        )
    if load_from_provider and flow_version_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="flow_version_ids filtering is not supported when loading deployments directly from the provider.",
        )
    if load_from_provider and flow_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="flow_ids filtering is not supported when loading deployments directly from the provider.",
        )
    if load_from_provider and project_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="project_id filtering is not supported when loading deployments directly from the provider.",
        )

    effective_flow_version_ids = flow_version_ids
    if flow_ids:
        resolved = await flow_version_ids_for_flows(session, flow_ids=flow_ids, user_id=current_user.id)
        if not resolved:
            return DeploymentListResponse(deployments=[], page=params.page, size=params.size, total=0)
        effective_flow_version_ids = resolved

    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id, user_id=current_user.id, db=session
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    if load_from_provider:
        provider_list_params = deployment_mapper.resolve_load_from_provider_deployment_list_params()
        adapter_params = DeploymentListParams(provider_params=provider_list_params) if provider_list_params else None
        with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_id):
            provider_view = await deployment_adapter.list(
                user_id=current_user.id,
                db=session,
                params=adapter_params,
            )
        return deployment_mapper.shape_deployment_list_result(provider_view)

    with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_id):
        rows_with_counts, total = await list_deployments_synced(
            deployment_adapter=deployment_adapter,
            deployment_mapper=deployment_mapper,
            user_id=current_user.id,
            provider_id=provider_id,
            db=session,
            page=params.page,
            size=params.size,
            deployment_type=deployment_type,
            flow_version_ids=effective_flow_version_ids,
            project_id=project_id,
        )
    deployments = deployment_mapper.shape_deployment_list_items(
        rows_with_counts=rows_with_counts,
        # include flow_version_ids in list items only when
        # flow_version_ids or flow_ids filtering is active.
        # (empty lists are rejected by validation)
        has_flow_filter=bool(flow_version_ids or flow_ids),
        provider_key=provider_account.provider_key,
    )
    return DeploymentListResponse(
        deployments=deployments,
        page=params.page,
        size=params.size,
        total=total,
        # if we reach here, then load_from_provider is False,
        # therefore, top-level provider_data must be excluded from the response.
        # for this, we set it to None, and set response_model_exclude_none to True.
        provider_data=None,
    )


@router.get("/types", response_model=DeploymentTypeListResponse)
async def list_deployment_types(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id, user_id=current_user.id, db=session
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    with handle_adapter_errors(), deployment_provider_scope(provider_id):
        deployment_types_result: DeploymentListTypesResult = await deployment_adapter.list_types(
            user_id=current_user.id,
            db=session,
        )
    return DeploymentTypeListResponse(deployment_types=deployment_types_result.deployment_types)


@router.get("/llms", response_model=DeploymentLlmListResponse)
async def list_deployment_llms(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id,
        user_id=current_user.id,
        db=session,
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_id):
        llm_list_result = await deployment_adapter.list_llms(
            user_id=current_user.id,
            db=session,
        )
    return deployment_mapper.shape_llm_list_result(llm_list_result)


@router.post(
    "/{deployment_id}/runs",
    response_model=RunCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deployment_run(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    payload: RunCreateRequest,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter, deployment_mapper, _provider_key = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    adapter_execution_payload = await deployment_mapper.resolve_execution_create(
        deployment_resource_key=deployment_row.resource_key,
        db=session,
        payload=payload,
    )
    with (
        handle_adapter_errors(mapper=deployment_mapper),
        deployment_provider_scope(deployment_row.deployment_provider_account_id),
    ):
        execution_result = await deployment_adapter.create_execution(
            payload=adapter_execution_payload,
            user_id=current_user.id,
            db=session,
        )

    return deployment_mapper.shape_execution_create_result(
        execution_result,
        deployment_id=deployment_row.id,
    )


@router.get("/{deployment_id}/runs/{run_id}", response_model=RunStatusResponse)
async def get_deployment_run(
    deployment_id: DeploymentIdPath,
    run_id: Annotated[str, Path(min_length=1, description="Provider-owned opaque run identifier.")],
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter, deployment_mapper, _provider_key = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    execution_lookup_id = run_id.strip()
    with (
        handle_adapter_errors(mapper=deployment_mapper),
        deployment_provider_scope(deployment_row.deployment_provider_account_id),
    ):
        execution_result = await deployment_adapter.get_execution(
            execution_id=execution_lookup_id,
            user_id=current_user.id,
            db=session,
        )

    return deployment_mapper.shape_execution_status_result(
        execution_result,
        deployment_id=deployment_row.id,
    )


# ---------------------------------------------------------------------------
# Routes: Configs
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=DeploymentConfigListResponse, response_model_exclude_none=True)
async def list_deployment_configs(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    deployment_id: DeploymentIdQuery | None = None,
    provider_id: DeploymentProviderAccountIdQuery | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=10000)] = 20,  # TODO: Paginate if performance is an issue
):
    """List deployment configs.

    Provider account resolution priority:
    1. Both provider_id and deployment_id given → use provider_id, validate
       the deployment belongs to it (404 if mismatched).
    2. Only deployment_id given → infer provider from the deployment row.
    3. Only provider_id given → tenant-scoped listing (no deployment filter).
    4. Neither given → 422.
    """
    deployment_row = None
    provider_account = (
        await get_owned_provider_account_or_404(
            provider_id=provider_id,
            user_id=current_user.id,
            db=session,
        )
        if provider_id is not None
        else None
    )

    if deployment_id is not None:
        deployment_row = await get_deployment_row_or_404(
            deployment_id=deployment_id,
            user_id=current_user.id,
            db=session,
        )
        if provider_account is None:
            provider_account = await get_owned_provider_account_or_404(
                provider_id=deployment_row.deployment_provider_account_id,
                user_id=current_user.id,
                db=session,
            )
        elif deployment_row.deployment_provider_account_id != provider_account.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")

    if provider_account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either provider_id or deployment_id must be provided.",
        )

    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    adapter_params = await deployment_mapper.resolve_config_list_adapter_params(
        deployment_resource_key=deployment_row.resource_key if deployment_row is not None else None,
        provider_params=None,
        db=session,
    )
    with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_account.id):
        config_result = await deployment_adapter.list_configs(
            user_id=current_user.id,
            params=adapter_params,
            db=session,
        )
    return deployment_mapper.shape_config_list_result(
        config_result,
        page=page,
        size=size,
    )


@router.get("/snapshots", response_model=DeploymentSnapshotListResponse, response_model_exclude_none=True)
async def list_deployment_snapshots(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    deployment_id: DeploymentIdQuery | None = None,
    names: Annotated[
        SnapshotNamesQuery,
        Query(min_length=1, description="Filter by provider-owned snapshot names."),
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """List deployment snapshots/tools."""
    if deployment_id is not None and names is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="filtering by both deployment_id and names is not supported.",
        )

    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id,
        user_id=current_user.id,
        db=session,
    )

    deployment_row = None
    if deployment_id is not None:
        deployment_row = await get_deployment_row_or_404(
            deployment_id=deployment_id,
            user_id=current_user.id,
            db=session,
        )
        if deployment_row.deployment_provider_account_id != provider_account.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")

    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    adapter_params = await deployment_mapper.resolve_snapshot_list_adapter_params(
        deployment_resource_key=deployment_row.resource_key if deployment_row is not None else None,
        snapshot_names=names,
        provider_params=None,
        db=session,
    )
    with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(provider_account.id):
        snapshot_result = await deployment_adapter.list_snapshots(
            user_id=current_user.id,
            params=adapter_params,
            db=session,
        )
    return deployment_mapper.shape_snapshot_list_result(
        snapshot_result,
        page=page,
        size=size,
    )


@router.patch(
    "/snapshots/{provider_snapshot_id}",
    response_model=SnapshotUpdateResponse,
)
async def update_snapshot(
    provider_snapshot_id: Annotated[
        str,
        Path(min_length=1, description="Provider-owned snapshot identifier (e.g. WXO tool_id)."),
    ],
    *,
    body: SnapshotUpdateRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Replace an existing provider snapshot's content with a new flow version.

    Resolves the deployment context from the attachment record linked to
    ``provider_snapshot_id``.  Only Langflow-tracked snapshots (those with
    a ``flow_version_deployment_attachment`` row) can be updated.
    """
    from langflow.services.database.models.deployment.crud import get_deployment as get_deployment_row
    from langflow.services.database.models.flow_version.crud import get_flow_version_entry

    snapshot_id = provider_snapshot_id.strip()

    attachment = await get_attachment_by_provider_snapshot_id(
        session,
        user_id=current_user.id,
        provider_snapshot_id=snapshot_id,
    )
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No attachment found for provider_snapshot_id '{snapshot_id}'.",
        )

    deployment = await get_deployment_row(
        session,
        user_id=current_user.id,
        deployment_id=attachment.deployment_id,
    )
    if deployment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deployment for attachment (deployment_id={attachment.deployment_id}) not found.",
        )

    flow_version = await get_flow_version_entry(
        session,
        version_id=body.flow_version_id,
        user_id=current_user.id,
    )
    if flow_version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flow version '{body.flow_version_id}' not found.",
        )
    if flow_version.data is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Flow version '{body.flow_version_id}' has no data.",
        )

    provider_account = await get_owned_provider_account_or_404(
        provider_id=deployment.deployment_provider_account_id,
        user_id=current_user.id,
        db=session,
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)

    from langflow.services.database.models.flow.model import Flow

    flow_row = await session.get(Flow, flow_version.flow_id)

    flow_artifact = deployment_mapper.resolve_snapshot_update_artifact(
        flow_version=flow_version,
        flow_row=flow_row,
        deployment=deployment,
    )

    with (
        handle_adapter_errors(mapper=deployment_mapper),
        deployment_provider_scope(deployment.deployment_provider_account_id),
    ):
        await deployment_adapter.update_snapshot(
            user_id=current_user.id,
            db=session,
            snapshot_id=snapshot_id,
            flow_artifact=flow_artifact,
        )

    # Provider mutation succeeded — update all local attachment rows that share
    # this provider snapshot id.
    # If the DB flush fails, attempt a best-effort compensating re-upload
    # of the previous flow version's artifact.
    # Concurrency note: rollback uses a single previously-read flow_version_id.
    # This assumes the snapshot->flow_version invariant held before this call.
    # Because the invariant is enforced in app logic (not a DB constraint),
    # concurrent writers can still race and violate that assumption.
    previous_flow_version_id = attachment.flow_version_id
    try:
        updated_rows = await update_flow_version_by_provider_snapshot_id(
            session,
            user_id=current_user.id,
            provider_snapshot_id=snapshot_id,
            flow_version_id=body.flow_version_id,
        )
        if updated_rows == 0:
            logger.warning(
                "Snapshot '%s' update changed zero attachment rows after provider mutation "
                "(user_id=%s, requested_flow_version_id=%s). Possible concurrent modification.",
                snapshot_id,
                current_user.id,
                body.flow_version_id,
            )
        await session.commit()
    except Exception:
        await session.rollback()
        logger.warning(
            "DB update/commit failed after provider snapshot update for snapshot '%s' "
            "(requested_flow_version_id=%s). Attempting compensating provider rollback.",
            snapshot_id,
            body.flow_version_id,
            exc_info=True,
        )
        try:
            prev_version = await get_flow_version_entry(
                session,
                version_id=previous_flow_version_id,
                user_id=current_user.id,
            )
            if prev_version and prev_version.data:
                prev_artifact = deployment_mapper.resolve_snapshot_update_artifact(
                    flow_version=prev_version,
                    flow_row=flow_row,
                    deployment=deployment,
                )
                with deployment_provider_scope(deployment.deployment_provider_account_id):
                    await deployment_adapter.update_snapshot(
                        user_id=current_user.id,
                        db=session,
                        snapshot_id=snapshot_id,
                        flow_artifact=prev_artifact,
                    )
                logger.info(
                    "Restored provider snapshot '%s' to previous flow_version_id=%s after DB commit failure.",
                    snapshot_id,
                    previous_flow_version_id,
                )
        except Exception:  # noqa: BLE001
            logger.warning(
                "Best-effort rollback failed for snapshot '%s'. "
                "Provider content reflects flow_version_id=%s but attachment "
                "records point to flow_version_id=%s. Manual reconciliation may be needed.",
                snapshot_id,
                body.flow_version_id,
                previous_flow_version_id,
                exc_info=True,
            )
        raise

    return SnapshotUpdateResponse(
        flow_version_id=body.flow_version_id,
        provider_snapshot_id=snapshot_id,
    )


# Internal note: keep exclude-none for lean responses; use explicit nulls only for intentional tri-state fields.
@router.get(
    "/{deployment_id}",
    response_model=DeploymentGetResponse,
    response_model_exclude_none=True,
)
async def get_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter, deployment_mapper, provider_key = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )

    with deployment_provider_scope(deployment_row.deployment_provider_account_id):
        # Deployment-level sync: if the provider no longer has this deployment,
        # delete the stale DB row (FK CASCADE handles attachments) and return 404.
        try:
            deployment = await deployment_adapter.get(
                user_id=current_user.id,
                deployment_id=deployment_row.resource_key,
                db=session,
            )
        except DeploymentNotFoundError:
            logger.warning(
                "Deployment %s (resource_key=%s) not found on provider — deleting stale row",
                deployment_row.id,
                deployment_row.resource_key,
            )
            try:
                await delete_deployment_by_id(session, user_id=current_user.id, deployment_id=deployment_row.id)
                await session.commit()
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to delete stale deployment row %s; returning 404 anyway",
                    deployment_row.id,
                    exc_info=True,
                )
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found.") from None
        except DeploymentServiceError as exc:
            raise HTTPException(
                status_code=http_status_for_deployment_error(exc),
                detail=exc.message,
            ) from exc

        # Snapshot-level sync: reconcile tracked attachments against provider
        # binding state for this deployment.
        try:
            try:
                bindings = deployment_mapper.extract_snapshot_bindings_for_get(
                    deployment,
                    resource_key=deployment_row.resource_key,
                )
            except NotImplementedError:
                logger.debug(
                    "Mapper for provider %s does not support binding-aware GET sync; "
                    "returning unverified attachment count for deployment %s",
                    provider_key,
                    deployment_row.id,
                )
                bindings = None

            if bindings is not None:
                async with session.begin_nested():
                    await delete_unbound_attachments(
                        db=session,
                        user_id=current_user.id,
                        provider_account_id=deployment_row.deployment_provider_account_id,
                        deployment_ids=[deployment_row.id],
                        bindings=bindings,
                    )

            attachments = await list_deployment_attachments(
                session, user_id=current_user.id, deployment_id=deployment_row.id
            )
            attached_count = len(attachments)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Binding-aware sync failed for deployment %s; returning unverified attachment count",
                deployment_row.id,
                exc_info=True,
            )
            await session.rollback()  # clean up potentially dirty session
            try:
                attachments = await list_deployment_attachments(
                    session, user_id=current_user.id, deployment_id=deployment_row.id
                )
                attached_count = len(attachments)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Fallback attachment count query also failed for deployment %s; defaulting to 0",
                    deployment_row.id,
                    exc_info=True,
                )
                attached_count = 0

    payload = deployment.model_dump(exclude_unset=True)
    raw_provider_data = payload.get("provider_data")
    provider_data = deployment_mapper.shape_deployment_get_data(raw_provider_data)
    return DeploymentGetResponse(
        id=deployment_row.id,
        provider_id=deployment_row.deployment_provider_account_id,
        provider_key=provider_key,
        name=deployment_row.name,
        description=deployment_row.description,
        type=deployment_row.deployment_type,
        # Timestamps are local DB audit fields, not provider payload fields.
        created_at=deployment_row.created_at,
        updated_at=deployment_row.updated_at,
        provider_data=provider_data,
        resource_key=deployment_row.resource_key,
        attached_count=attached_count,
    )


@router.patch(
    "/{deployment_id}",
    response_model=DeploymentUpdateResponse,
)
async def update_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    payload: DeploymentUpdateRequest,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter, deployment_mapper, provider_key = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    deployment_row_id = deployment_row.id
    deployment_resource_key = deployment_row.resource_key
    deployment_provider_account_id = deployment_row.deployment_provider_account_id
    adapter_payload = await deployment_mapper.resolve_deployment_update(
        user_id=current_user.id,
        deployment_db_id=deployment_row_id,
        db=session,
        payload=payload,
    )
    added_flow_version_ids, remove_flow_version_ids = resolve_flow_version_patch_for_update(
        deployment_mapper=deployment_mapper,
        payload=payload,
    )
    await validate_project_scoped_flow_version_ids(
        flow_version_ids=list(dict.fromkeys([*added_flow_version_ids, *remove_flow_version_ids])),
        user_id=current_user.id,
        project_id=deployment_row.project_id,
        db=session,
    )
    with handle_adapter_errors(mapper=deployment_mapper), deployment_provider_scope(deployment_provider_account_id):
        update_result: DeploymentUpdateResult = await deployment_adapter.update(
            deployment_id=deployment_resource_key,
            payload=adapter_payload,
            user_id=current_user.id,
            db=session,
        )
    try:
        existing_attachments = await list_deployment_attachments_for_flow_version_ids(
            session,
            user_id=current_user.id,
            deployment_id=deployment_row_id,
            flow_version_ids=added_flow_version_ids,
        )
        already_attached = {a.flow_version_id for a in existing_attachments}
        newly_added_flow_version_ids = [fv for fv in added_flow_version_ids if fv not in already_attached]
        added_snapshot_bindings = resolve_added_snapshot_bindings_for_update(
            deployment_mapper=deployment_mapper,
            added_flow_version_ids=newly_added_flow_version_ids,
            result=update_result,
        )
        await apply_flow_version_patch_attachments(
            user_id=current_user.id,
            deployment_row_id=deployment_row_id,
            added_snapshot_bindings=added_snapshot_bindings,
            remove_flow_version_ids=remove_flow_version_ids,
            db=session,
        )

        update_kwargs: dict = {}
        if payload.name is not None and payload.name != deployment_row.name:
            update_kwargs["name"] = payload.name
        if _field_was_explicitly_set(payload, "description"):
            if payload.description != deployment_row.description:
                update_kwargs["description"] = payload.description
        elif payload.description is not None and payload.description != deployment_row.description:
            update_kwargs["description"] = payload.description
        if update_kwargs:
            deployment_row = await update_deployment_db(
                session,
                deployment=deployment_row,
                **update_kwargs,
            )

        await session.commit()
    except Exception as exc:
        # Provider was already mutated by deployment_adapter.update above.
        # Roll back the session to discard any pending DB changes (or reset
        # it from the "inactive" state after a failed commit) so the mapper
        # can query the original attachment rows and build a compensating
        # payload.
        await session.rollback()
        await rollback_provider_update(
            deployment_adapter=deployment_adapter,
            deployment_mapper=deployment_mapper,
            deployment_db_id=deployment_row_id,
            deployment_resource_key=deployment_resource_key,
            deployment_provider_account_id=deployment_provider_account_id,
            user_id=current_user.id,
            db=session,
        )
        if isinstance(exc, AttachmentConflictError):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        raise

    return deployment_mapper.shape_deployment_update_result(
        update_result,
        deployment_row,
        provider_key=provider_key,
    )


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
    *,
    include_provider: IncludeProviderDeleteQuery = True,
):
    deployment_row, deployment_adapter, _provider_key = await resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    if include_provider:
        try:
            with handle_adapter_errors(), deployment_provider_scope(deployment_row.deployment_provider_account_id):
                await deployment_adapter.delete(
                    deployment_id=deployment_row.resource_key,
                    user_id=current_user.id,
                    db=session,
                )
        except HTTPException as exc:
            if exc.status_code != status.HTTP_404_NOT_FOUND:
                raise
            logger.warning(
                "Deployment %s (resource_key=%s) already missing on provider %s during delete; deleting stale row.",
                deployment_row.id,
                deployment_row.resource_key,
                deployment_row.deployment_provider_account_id,
            )
    await _delete_local_deployment_row_with_commit_retry(
        session=session,
        deployment_id=deployment_row.id,
        user_id=current_user.id,
        resource_key=deployment_row.resource_key,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{deployment_id}/status",
    response_model=DeploymentStatusResponse,
)
async def get_deployment_status(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter, provider_key = await resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    with handle_adapter_errors(), deployment_provider_scope(deployment_row.deployment_provider_account_id):
        health_result = await deployment_adapter.get_status(
            deployment_id=deployment_row.resource_key,
            user_id=current_user.id,
            db=session,
        )
    return DeploymentStatusResponse(
        id=deployment_row.id,
        provider_id=deployment_row.deployment_provider_account_id,
        provider_key=provider_key,
        name=deployment_row.name,
        description=deployment_row.description,
        type=deployment_row.deployment_type,
        created_at=deployment_row.created_at,
        updated_at=deployment_row.updated_at,
        provider_data=health_result.provider_data,
    )


@router.get(
    "/{deployment_id}/flows",
    response_model=DeploymentFlowVersionListResponse,
)
async def list_deployment_flow_versions(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    flow_ids: Annotated[
        FlowIdsQuery,
        Query(
            description=(
                "Optional flow ids (pass as repeated query params, "
                "e.g. ?flow_ids=id1). Currently limited to 1 value. "
                "When provided, only attached flow versions belonging to the specified flow(s) are returned."
            )
        ),
    ] = None,
):
    deployment_row, deployment_adapter, deployment_mapper, _provider_key = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    with (
        handle_adapter_errors(mapper=deployment_mapper),
        deployment_provider_scope(deployment_row.deployment_provider_account_id),
    ):
        rows, total, snapshot_result = await list_deployment_flow_versions_synced(
            deployment_adapter=deployment_adapter,
            user_id=current_user.id,
            provider_id=deployment_row.deployment_provider_account_id,
            deployment_id=deployment_row.id,
            db=session,
            page=page,
            size=size,
            flow_ids=flow_ids,
        )
    return deployment_mapper.shape_flow_version_list_result(
        rows=rows,
        snapshot_result=snapshot_result,
        page=page,
        size=size,
        total=total,
    )
