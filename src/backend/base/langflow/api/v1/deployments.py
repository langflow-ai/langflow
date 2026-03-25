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
    DeploymentListTypesResult,
    DeploymentType,
    DeploymentUpdateResult,
)

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.mappers.deployments import get_deployment_mapper
from langflow.api.v1.mappers.deployments.helpers import (
    apply_flow_version_patch_attachments,
    attach_flow_versions,
    deployment_pagination_params,
    fetch_provider_snapshot_keys,
    get_deployment_row_or_404,
    get_owned_provider_account_or_404,
    handle_adapter_errors,
    list_deployments_synced,
    normalize_flow_version_query_ids,
    page_offset,
    raise_http_for_value_error,
    resolve_adapter_from_deployment,
    resolve_adapter_mapper_from_deployment,
    resolve_adapter_mapper_from_provider_id,
    resolve_added_snapshot_bindings_for_update,
    resolve_deployment_adapter,
    resolve_flow_version_patch_for_update,
    resolve_project_id_for_deployment_create,
    resolve_provider_tenant_id,
    resolve_snapshot_map_for_create,
    rollback_provider_create,
    rollback_provider_update,
    sync_attachment_snapshot_ids,
    to_deployment_create_response,
    to_provider_account_response,
    validate_project_scoped_flow_version_ids,
)
from langflow.api.v1.schemas.deployments import (
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentDuplicateResponse,
    DeploymentGetResponse,
    DeploymentListItem,
    DeploymentListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountListResponse,
    DeploymentProviderAccountUpdateRequest,
    DeploymentRedeployResponse,
    DeploymentStatusResponse,
    DeploymentTypeListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    ExecutionCreateRequest,
    ExecutionCreateResponse,
    ExecutionStatusResponse,
    FlowVersionIdsQuery,
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
    create_provider_account as create_provider_account_row,
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
    list_deployment_attachments,
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
DeploymentIdQuery = Annotated[
    UUID,
    Query(description="Langflow DB deployment UUID (`deployment.id`)."),
]


def _raise_http_for_provider_account_value_error(exc: ValueError) -> None:
    message = str(exc).lower()
    if "already exists" in message or "conflicts with an existing record" in message:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    raise_http_for_value_error(exc)


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

    with handle_adapter_errors():
        verify_input = deployment_mapper.resolve_verify_credentials(payload=payload)
        await deployment_adapter.verify_credentials(
            user_id=current_user.id,
            payload=verify_input,
        )

    try:
        resolved_provider_tenant_id = resolve_provider_tenant_id(
            deployment_mapper=deployment_mapper,
            provider_url=payload.provider_url,
            provider_tenant_id=payload.provider_tenant_id,
        )
        credential_kwargs = deployment_mapper.resolve_credential_fields(provider_data=payload.provider_data)
        provider_account = await create_provider_account_row(
            session,
            user_id=current_user.id,
            name=payload.name,
            provider_tenant_id=resolved_provider_tenant_id,
            provider_key=payload.provider_key,
            provider_url=payload.provider_url,
            **credential_kwargs,
        )
    except ValueError as exc:
        _raise_http_for_provider_account_value_error(exc)
    return to_provider_account_response(provider_account)


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
        providers=[to_provider_account_response(item) for item in provider_accounts],
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
    return to_provider_account_response(provider_account)


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
    provider_account = await get_provider_account_row_by_id(session, provider_id=provider_id, user_id=current_user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")
    deployment_count = await count_deployments_by_provider(
        session,
        user_id=current_user.id,
        deployment_provider_account_id=provider_id,
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
    provider_account = await get_provider_account_row_by_id(session, provider_id=provider_id, user_id=current_user.id)
    if provider_account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment provider account not found.")

    try:
        payload.validate_provider_url_allowed(provider_account.provider_key)
    except ValueError as exc:
        _raise_http_for_provider_account_value_error(exc)

    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    verify_input = None
    if "provider_url" in payload.model_fields_set or "provider_data" in payload.model_fields_set:
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
            with handle_adapter_errors():
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
    return to_provider_account_response(updated)


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
        name=payload.spec.name,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A deployment named {payload.spec.name!r} already exists for this provider account",
        )

    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    project_id = await resolve_project_id_for_deployment_create(payload=payload, user_id=current_user.id, db=session)
    flow_version_ids = deployment_mapper.util_create_flow_version_ids(payload)
    await validate_project_scoped_flow_version_ids(
        flow_version_ids=flow_version_ids,
        user_id=current_user.id,
        project_id=project_id,
        db=session,
    )
    adapter_payload = await deployment_mapper.resolve_deployment_create(
        user_id=current_user.id,
        project_id=project_id,
        db=session,
        payload=payload,
    )
    with handle_adapter_errors(), deployment_provider_scope(provider_id):
        result = await deployment_adapter.create(
            user_id=current_user.id,
            payload=adapter_payload,
            db=session,
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
            resource_key=str(result.id),
            name=payload.spec.name,
            deployment_type=payload.spec.type,
            description=payload.spec.description or None,
        )

        snapshot_id_by_flow_version_id: dict[UUID, str] = {}
        if flow_version_ids:
            snapshot_id_by_flow_version_id = resolve_snapshot_map_for_create(
                deployment_mapper=deployment_mapper,
                result=result,
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
    except Exception:
        # Compensate: delete the provider resource so it doesn't become orphaned.
        # Only the deployment resource itself is deleted (e.g. the WXO agent).
        # Secondary resources (snapshots/tools, configs) may remain orphaned --
        # this is intentional because snapshots/configs may be shared across deployments,
        # making cascade-delete unsafe.
        await session.rollback()
        await rollback_provider_create(
            deployment_adapter=deployment_adapter,
            provider_id=provider_id,
            resource_id=result.id,
            provider_result=result.provider_result,
            user_id=current_user.id,
            db=session,
        )
        raise
    return to_deployment_create_response(result, deployment_row)


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSession,
    current_user: CurrentActiveUser,
    params: Annotated[Params, Depends(deployment_pagination_params)],
    deployment_type: Annotated[DeploymentType | None, Query()] = None,
    flow_version_ids: Annotated[
        FlowVersionIdsQuery,
        Query(
            description=(
                "Optional Langflow flow version ids (pass as repeated query params, "
                "e.g. ?flow_version_ids=id1&flow_version_ids=id2). When provided, "
                "deployments are filtered to those with at least one matching "
                "attachment (OR semantics across ids)."
            )
        ),
    ] = None,
):
    normalized_flow_version_ids = normalize_flow_version_query_ids(flow_version_ids)
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id, user_id=current_user.id, db=session
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    with handle_adapter_errors(), deployment_provider_scope(provider_id):
        rows_with_counts, total = await list_deployments_synced(
            deployment_adapter=deployment_adapter,
            deployment_mapper=deployment_mapper,
            user_id=current_user.id,
            provider_id=provider_id,
            db=session,
            page=params.page,
            size=params.size,
            deployment_type=deployment_type,
            flow_version_ids=normalized_flow_version_ids or None,
        )
    deployments = [
        DeploymentListItem(
            id=row.id,
            resource_key=row.resource_key,
            type=row.deployment_type,
            name=row.name,
            description=row.description,
            attached_count=attached_count,
            created_at=row.created_at,
            updated_at=row.updated_at,
            provider_data={"matched_flow_version_ids": matched_flow_versions} if normalized_flow_version_ids else None,
        )
        for row, attached_count, matched_flow_versions in rows_with_counts
    ]
    return DeploymentListResponse(
        deployments=deployments,
        deployment_type=deployment_type,
        page=params.page,
        size=params.size,
        total=total,
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


@router.post("/executions", response_model=ExecutionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_execution(
    session: DbSession,
    payload: ExecutionCreateRequest,
    current_user: CurrentActiveUser,
):
    deployment_row = await get_deployment_row_or_404(
        deployment_id=payload.deployment_id,
        user_id=current_user.id,
        db=session,
    )
    if deployment_row.deployment_provider_account_id != payload.provider_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")

    deployment_adapter, deployment_mapper = await resolve_adapter_mapper_from_provider_id(
        payload.provider_id,
        user_id=current_user.id,
        db=session,
    )
    adapter_execution_payload = await deployment_mapper.resolve_execution_create(
        deployment_resource_key=deployment_row.resource_key,
        db=session,
        payload=payload,
    )
    with handle_adapter_errors(), deployment_provider_scope(payload.provider_id):
        execution_result = await deployment_adapter.create_execution(
            payload=adapter_execution_payload,
            user_id=current_user.id,
            db=session,
        )

    return deployment_mapper.shape_execution_create_result(
        execution_result,
        deployment_id=deployment_row.id,
    )


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
async def get_deployment_execution(
    execution_id: Annotated[str, Path(min_length=1, description="Provider-owned opaque execution identifier.")],
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    deployment_adapter, deployment_mapper = await resolve_adapter_mapper_from_provider_id(
        provider_id,
        user_id=current_user.id,
        db=session,
    )
    execution_lookup_id = execution_id.strip()
    with handle_adapter_errors(), deployment_provider_scope(provider_id):
        execution_result = await deployment_adapter.get_execution(
            execution_id=execution_lookup_id,
            user_id=current_user.id,
            db=session,
        )

    provider_deployment_id = deployment_mapper.util_resource_key_from_execution(execution_result)
    if not provider_deployment_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deployment provider execution result did not include a deployment identifier.",
        )
    deployment_row = await get_deployment_by_resource_key(
        session,
        user_id=current_user.id,
        deployment_provider_account_id=provider_id,
        resource_key=provider_deployment_id,
    )
    if deployment_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found for provider.")

    return deployment_mapper.shape_execution_status_result(
        execution_result,
        deployment_id=deployment_row.id,
    )


# ---------------------------------------------------------------------------
# Routes: Configs
# ---------------------------------------------------------------------------


@router.get("/configs", response_model=DeploymentConfigListResponse)
async def list_deployment_configs(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    deployment_id: DeploymentIdQuery,  # required today, not going to provide global listing for now
    provider_id: DeploymentProviderAccountIdQuery | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """List deployment configs."""
    _ = (session, current_user, deployment_id, provider_id, page, size)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/{deployment_id}", response_model=DeploymentGetResponse)
async def get_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter, deployment_mapper = await resolve_adapter_mapper_from_deployment(
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

        # Snapshot-level sync: verify that tracked provider_snapshot_ids still exist.
        # Best-effort — a provider outage should not block the GET response.
        try:
            attachments = await list_deployment_attachments(
                session, user_id=current_user.id, deployment_id=deployment_row.id
            )
            snapshot_ids_to_verify = deployment_mapper.util_snapshot_ids_to_verify(attachments)
            if snapshot_ids_to_verify:
                known_snapshots = await fetch_provider_snapshot_keys(
                    deployment_adapter=deployment_adapter,
                    user_id=current_user.id,
                    provider_id=deployment_row.deployment_provider_account_id,
                    db=session,
                    snapshot_ids=snapshot_ids_to_verify,
                )
                corrected_counts = await sync_attachment_snapshot_ids(
                    user_id=current_user.id,
                    deployment_ids=[deployment_row.id],
                    attachments=attachments,
                    known_snapshot_ids=known_snapshots,
                    db=session,
                )
                attached_count = corrected_counts[deployment_row.id]
            else:
                # No attachments carry a provider-verifiable snapshot ID, so
                # there is nothing to check against the provider.  The raw
                # DB attachment count is used as-is.
                attached_count = len(attachments)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Snapshot-level sync failed for deployment %s; returning unverified attachment count",
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
    provider_data = payload.get("provider_data") if isinstance(payload.get("provider_data"), dict) else {}
    provider_data = {**provider_data, "resource_key": deployment_row.resource_key}
    return DeploymentGetResponse(
        id=deployment_row.id,
        name=deployment.name,
        description=getattr(deployment, "description", None),
        type=deployment.type,
        created_at=deployment.created_at,
        updated_at=deployment.updated_at,
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
    deployment_row, deployment_adapter, deployment_mapper = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    adapter_payload = await deployment_mapper.resolve_deployment_update(
        user_id=current_user.id,
        deployment_db_id=deployment_row.id,
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
    with handle_adapter_errors(), deployment_provider_scope(deployment_row.deployment_provider_account_id):
        update_result: DeploymentUpdateResult = await deployment_adapter.update(
            deployment_id=deployment_row.resource_key,
            payload=adapter_payload,
            user_id=current_user.id,
            db=session,
        )
    try:
        added_snapshot_bindings = resolve_added_snapshot_bindings_for_update(
            deployment_mapper=deployment_mapper,
            added_flow_version_ids=added_flow_version_ids,
            result=update_result,
        )
        await apply_flow_version_patch_attachments(
            user_id=current_user.id,
            deployment_row_id=deployment_row.id,
            added_snapshot_bindings=added_snapshot_bindings,
            remove_flow_version_ids=remove_flow_version_ids,
            db=session,
        )

        if payload.spec is not None:
            update_kwargs: dict = {}
            if payload.spec.name is not None and payload.spec.name != deployment_row.name:
                update_kwargs["name"] = payload.spec.name
            if payload.spec.description is not None and payload.spec.description != deployment_row.description:
                update_kwargs["description"] = payload.spec.description
            if update_kwargs:
                deployment_row = await update_deployment_db(
                    session,
                    deployment=deployment_row,
                    **update_kwargs,
                )

        await session.commit()
    except Exception:
        # Provider was already mutated by deployment_adapter.update above.
        # Roll back the session to discard any pending DB changes (or reset
        # it from the "inactive" state after a failed commit) so the mapper
        # can query the original attachment rows and build a compensating
        # payload.
        await session.rollback()
        await rollback_provider_update(
            deployment_adapter=deployment_adapter,
            deployment_mapper=deployment_mapper,
            deployment_row=deployment_row,
            user_id=current_user.id,
            db=session,
        )
        raise

    return deployment_mapper.shape_deployment_update_result(
        update_result,
        deployment_row,
    )


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    deployment_row, deployment_adapter = await resolve_adapter_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )
    with handle_adapter_errors(), deployment_provider_scope(deployment_row.deployment_provider_account_id):
        await deployment_adapter.delete(
            deployment_id=deployment_row.resource_key,
            user_id=current_user.id,
            db=session,
        )
    await delete_deployment_by_id(session, user_id=current_user.id, deployment_id=deployment_row.id)
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
    deployment_row, deployment_adapter = await resolve_adapter_from_deployment(
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
        name=deployment_row.name,
        description=deployment_row.description,
        type=deployment_row.deployment_type,
        created_at=deployment_row.created_at,
        updated_at=deployment_row.updated_at,
        provider_data=health_result.provider_data,
    )


@router.post(
    "/{deployment_id}/redeploy",
    response_model=DeploymentRedeployResponse,
)
async def redeploy_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    """Redeploy a deployment."""
    _ = (deployment_id, session, current_user)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.post(
    "/{deployment_id}/duplicate",
    response_model=DeploymentDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    """Duplicate a deployment."""
    _ = (deployment_id, session, current_user)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")
