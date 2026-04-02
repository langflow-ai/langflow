from __future__ import annotations

import json
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
    DeploymentAttachmentItem,
    DeploymentAttachmentListResponse,
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentDuplicateResponse,
    DeploymentGetResponse,
    DeploymentListResponse,
    DeploymentLlmListResponse,
    DeploymentProviderAccountCreateRequest,
    DeploymentProviderAccountGetResponse,
    DeploymentProviderAccountListResponse,
    DeploymentProviderAccountUpdateRequest,
    DeploymentRedeployResponse,
    DeploymentSnapshotListResponse,
    DeploymentStatusResponse,
    DeploymentTypeListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    DetectedEnvVar,
    DetectEnvVarsRequest,
    DetectEnvVarsResponse,
    ExecutionCreateRequest,
    ExecutionCreateResponse,
    ExecutionStatusResponse,
    FlowVersionIdsQuery,
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
from langflow.services.database.models.flow_version.crud import (
    get_flow_version_entry_or_raise,
)
from langflow.services.database.models.flow_version.exceptions import FlowVersionNotFoundError
from langflow.services.database.models.flow_version_deployment_attachment.crud import (
    get_attachment_by_provider_snapshot_id,
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


def _derive_env_var_name(field_key: str, template: dict) -> str:
    """Derive a meaningful env var name for a password field without a global variable.

    Looks for a sibling ``model`` field whose selected value carries a ``category``
    (e.g. ``"OpenAI"``). When found, returns ``{CATEGORY}_API_KEY`` (e.g.
    ``OPENAI_API_KEY``).  Falls back to the uppercased field key (``API_KEY``).
    """
    model_field = template.get("model")
    if isinstance(model_field, dict):
        raw = model_field.get("value")
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except ValueError:
                raw = None
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            category = raw[0].get("category", "")
            if category:
                prefix = category.upper().replace(" ", "_").replace("-", "_")
                return f"{prefix}_{field_key.upper()}"

    return field_key.upper()


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
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
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

    try:
        payload.validate_provider_url_allowed(provider_account.provider_key)
    except ValueError as exc:
        _raise_http_for_provider_account_value_error(exc)

    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    verify_input = None
    if _field_was_explicitly_set(payload, "provider_url") or _field_was_explicitly_set(payload, "provider_data"):
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
            detail=f"A deployment named '{payload.spec.name}' already exists. "
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
        with handle_adapter_errors(), deployment_provider_scope(provider_id):
            provider_create_result = await deployment_adapter.create(
                user_id=current_user.id,
                payload=adapter_payload,
                db=session,
            )
    else:
        provider_create_result = deployment_mapper.util_create_result_from_existing_resource(
            existing_resource_key=str(existing_resource_key),
        )
        if should_mutate_existing_resource:
            adapter_payload = await deployment_mapper.resolve_deployment_update_for_existing_create(
                user_id=current_user.id,
                project_id=project_id,
                db=session,
                payload=payload,
            )
            with handle_adapter_errors(), deployment_provider_scope(provider_id):
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
            name=payload.spec.name,
            deployment_type=payload.spec.type,
            description=payload.spec.description or None,
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
    except Exception:
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
        raise
    return to_deployment_create_response(provider_create_result, deployment_row)


@router.get("", response_model=DeploymentListResponse)
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
                "attachment (OR semantics across ids)."
            )
        ),
    ] = None,
):
    normalized_flow_version_ids = normalize_flow_version_query_ids(flow_version_ids)
    if load_from_provider and normalized_flow_version_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="flow_version_ids filtering is not supported when load_from_provider=true.",
        )
    provider_account = await get_owned_provider_account_or_404(
        provider_id=provider_id, user_id=current_user.id, db=session
    )
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)
    deployment_mapper = get_deployment_mapper(provider_account.provider_key)
    if load_from_provider:
        with handle_adapter_errors(), deployment_provider_scope(provider_id):
            provider_view = await deployment_adapter.list(
                user_id=current_user.id,
                db=session,
                params=None if deployment_type is None else DeploymentListParams(deployment_types=[deployment_type]),
            )
        return deployment_mapper.shape_deployment_list_result(
            provider_view,
            deployment_type=deployment_type,
        )

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
    deployments = deployment_mapper.shape_deployment_list_items(
        rows_with_counts=rows_with_counts,
        matched_flow_version_filter_ids=normalized_flow_version_ids or None,
    )
    return DeploymentListResponse(
        deployments=deployments,
        deployment_type=deployment_type,
        page=params.page,
        size=params.size,
        total=total,
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
    with handle_adapter_errors(), deployment_provider_scope(provider_id):
        llm_list_result = await deployment_adapter.list_llms(
            user_id=current_user.id,
            db=session,
        )
    return deployment_mapper.shape_llm_list_result(llm_list_result)


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
    deployment_id: DeploymentIdQuery | None = None,
    provider_id: DeploymentProviderAccountIdQuery | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
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
    with handle_adapter_errors(), deployment_provider_scope(provider_account.id):
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


@router.get("/snapshots", response_model=DeploymentSnapshotListResponse)
async def list_deployment_snapshots(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    deployment_id: DeploymentIdQuery | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """List deployment snapshots/tools."""
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
        provider_params=None,
        db=session,
    )
    with handle_adapter_errors(), deployment_provider_scope(provider_account.id):
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
    # NOTE: update_snapshot is currently only implemented on the WXO adapter.
    # If additional adapters are added, this method should be promoted to the
    # adapter protocol / base class.
    deployment_adapter = resolve_deployment_adapter(provider_account.provider_key)

    flow_definition = dict(flow_version.data)
    flow_definition["id"] = str(flow_version.flow_id)

    with handle_adapter_errors(), deployment_provider_scope(deployment.deployment_provider_account_id):
        await deployment_adapter.update_snapshot(
            user_id=current_user.id,
            db=session,
            provider_snapshot_id=snapshot_id,
            flow_definition=flow_definition,
            project_id=str(deployment.project_id),
        )

    # Provider mutation succeeded — update the local attachment record.
    # If the DB flush fails, attempt a best-effort compensating re-upload
    # of the previous flow version's artifact
    previous_flow_version_id = attachment.flow_version_id
    attachment.flow_version_id = body.flow_version_id
    session.add(attachment)
    try:
        await session.flush()
        await session.refresh(attachment)
    except Exception:
        await session.rollback()
        try:
            prev_version = await get_flow_version_entry(
                session,
                version_id=previous_flow_version_id,
                user_id=current_user.id,
            )
            if prev_version and prev_version.data:
                prev_definition = dict(prev_version.data)
                prev_definition["id"] = str(prev_version.flow_id)
                with deployment_provider_scope(deployment.deployment_provider_account_id):
                    await deployment_adapter.update_snapshot(
                        user_id=current_user.id,
                        db=session,
                        provider_snapshot_id=snapshot_id,
                        flow_definition=prev_definition,
                        project_id=str(deployment.project_id),
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
                "record points to flow_version_id=%s. Manual reconciliation may be needed.",
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


@router.get("/{deployment_id}/attachments", response_model=DeploymentAttachmentListResponse)
async def list_deployment_attachment_details(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """List flow versions currently attached to a deployment with rich metadata.

    Performs a best-effort snapshot-level sync with the provider before
    returning results, then enriches each attachment with its per-tool
    connection bindings from the provider.
    """
    from lfx.services.adapters.deployment.schema import SnapshotListParams
    from sqlmodel import select

    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion
    from langflow.services.database.models.flow_version_deployment_attachment.model import (
        FlowVersionDeploymentAttachment,
    )

    deployment_row, deployment_adapter, deployment_mapper = await resolve_adapter_mapper_from_deployment(
        deployment_id=deployment_id,
        user_id=current_user.id,
        db=session,
    )

    # Fetch the current LLM from the provider agent metadata.
    deployment_llm: str | None = None
    try:
        with deployment_provider_scope(deployment_row.deployment_provider_account_id):
            deployment_detail = await deployment_adapter.get(
                user_id=current_user.id,
                deployment_id=deployment_row.resource_key,
                db=session,
            )
        if deployment_detail.provider_data and isinstance(deployment_detail.provider_data, dict):
            deployment_llm = deployment_detail.provider_data.get("llm")
    except Exception:  # noqa: BLE001
        logger.warning(
            "Failed to fetch LLM for deployment %s; returning without LLM data",
            deployment_id,
            exc_info=True,
        )

    # Best-effort snapshot-level sync: prune stale attachment rows whose
    # provider_snapshot_id no longer exists on the provider.
    try:
        attachments = await list_deployment_attachments(
            session, user_id=current_user.id, deployment_id=deployment_row.id
        )
        snapshot_ids_to_verify = deployment_mapper.util_snapshot_ids_to_verify(attachments)
        if snapshot_ids_to_verify:
            with deployment_provider_scope(deployment_row.deployment_provider_account_id):
                known_snapshots = await fetch_provider_snapshot_keys(
                    deployment_adapter=deployment_adapter,
                    user_id=current_user.id,
                    provider_id=deployment_row.deployment_provider_account_id,
                    db=session,
                    snapshot_ids=snapshot_ids_to_verify,
                )
                await sync_attachment_snapshot_ids(
                    user_id=current_user.id,
                    deployment_ids=[deployment_row.id],
                    attachments=attachments,
                    known_snapshot_ids=known_snapshots,
                    db=session,
                )
    except Exception:  # noqa: BLE001
        logger.warning(
            "Snapshot-level sync failed for deployment %s attachments; returning unverified data",
            deployment_id,
            exc_info=True,
        )
        await session.rollback()

    # 1) DB join: attachment → flow_version → flow
    stmt = (
        select(
            FlowVersionDeploymentAttachment.flow_version_id,
            FlowVersion.flow_id,
            Flow.name.label("flow_name"),  # type: ignore[attr-defined]
            FlowVersion.version_number,
            FlowVersionDeploymentAttachment.provider_snapshot_id,
            FlowVersionDeploymentAttachment.created_at,
        )
        .join(FlowVersion, FlowVersion.id == FlowVersionDeploymentAttachment.flow_version_id)
        .join(Flow, Flow.id == FlowVersion.flow_id)
        .where(
            FlowVersionDeploymentAttachment.user_id == current_user.id,
            FlowVersionDeploymentAttachment.deployment_id == deployment_id,
        )
        .order_by(FlowVersionDeploymentAttachment.created_at)
    )
    rows = (await session.exec(stmt)).all()

    # 2) Collect provider_snapshot_ids for connection enrichment
    snapshot_ids = [row.provider_snapshot_id for row in rows if row.provider_snapshot_id]

    # 3) Fetch tool payloads from provider → extract per-tool connection bindings and names
    connections_by_snapshot: dict[str, list[str]] = {}
    tool_name_by_snapshot: dict[str, str] = {}
    if snapshot_ids:
        try:
            with handle_adapter_errors(), deployment_provider_scope(deployment_row.deployment_provider_account_id):
                snapshot_result = await deployment_adapter.list_snapshots(
                    user_id=current_user.id,
                    params=SnapshotListParams(snapshot_ids=snapshot_ids),
                    db=session,
                )
            for snap in snapshot_result.snapshots:
                snap_id = str(snap.id)
                if snap.name:
                    tool_name_by_snapshot[snap_id] = snap.name
                if snap.provider_data and isinstance(snap.provider_data, dict):
                    conns = snap.provider_data.get("binding", {}).get("langflow", {}).get("connections", {})
                    if isinstance(conns, dict) and conns:
                        connections_by_snapshot[snap_id] = list(conns.keys())
        except Exception:  # noqa: BLE001
            logger.warning(
                "Connection enrichment failed for deployment %s; returning attachments without connection data",
                deployment_id,
                exc_info=True,
            )

    items = [
        DeploymentAttachmentItem(
            flow_version_id=row.flow_version_id,
            flow_id=row.flow_id,
            flow_name=row.flow_name,
            version_tag=f"v{row.version_number}",
            provider_snapshot_id=row.provider_snapshot_id,
            tool_name=tool_name_by_snapshot.get(row.provider_snapshot_id)
            if row.provider_snapshot_id
            else None,
            connection_ids=connections_by_snapshot.get(row.provider_snapshot_id, [])
            if row.provider_snapshot_id
            else [],
            created_at=row.created_at,
        )
        for row in rows
    ]
    return DeploymentAttachmentListResponse(attachments=items, llm=deployment_llm)


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
    with handle_adapter_errors(), deployment_provider_scope(deployment_provider_account_id):
        update_result: DeploymentUpdateResult = await deployment_adapter.update(
            deployment_id=deployment_resource_key,
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
            deployment_row_id=deployment_row_id,
            added_snapshot_bindings=added_snapshot_bindings,
            remove_flow_version_ids=remove_flow_version_ids,
            db=session,
        )

        if payload.spec is not None:
            update_kwargs: dict = {}
            if payload.spec.name is not None and payload.spec.name != deployment_row.name:
                update_kwargs["name"] = payload.spec.name
            if _field_was_explicitly_set(payload.spec, "description"):
                if payload.spec.description != deployment_row.description:
                    update_kwargs["description"] = payload.spec.description
            elif payload.spec.description is not None and payload.spec.description != deployment_row.description:
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
            deployment_db_id=deployment_row_id,
            deployment_resource_key=deployment_resource_key,
            deployment_provider_account_id=deployment_provider_account_id,
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
    *,
    include_provider: IncludeProviderDeleteQuery = True,
):
    deployment_row, deployment_adapter = await resolve_adapter_from_deployment(
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


@router.post("/variables/detections", response_model=DetectEnvVarsResponse)
async def detect_deployment_env_vars(
    payload: DetectEnvVarsRequest,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Detect credential fields used by the given flow version IDs.

    Two tiers of detection:
    1. Fields with ``load_from_db=True``: the ``value`` is a Langflow global
       variable name — returned with ``global_variable_name`` set.
    2. Fields with ``password=True`` and no global variable link: the field
       key is uppercased and returned as a suggested env var name, with
       ``global_variable_name`` left as ``None``.

    Results are deduplicated. Global-variable refs take precedence over
    password-only suggestions when the same key appears in both tiers.
    """
    # tier 1: fields linked to a global variable
    global_var_keys: dict[str, str] = {}
    # tier 2: password fields with no global variable (suggested_key → suggested_key)
    password_keys: dict[str, str] = {}

    for version_id in payload.reference_ids:
        try:
            version = await get_flow_version_entry_or_raise(
                session,
                version_id=version_id,
                user_id=current_user.id,
            )
        except FlowVersionNotFoundError:
            continue

        data = version.data
        if not isinstance(data, dict):
            continue

        for node in data.get("nodes", []):
            template = node.get("data", {}).get("node", {}).get("template", {})
            if not isinstance(template, dict):
                continue
            for field_key, field in template.items():
                if not isinstance(field, dict):
                    continue
                if field.get("load_from_db") is True:
                    var_name = field.get("value")
                    if isinstance(var_name, str) and var_name.strip():
                        global_var_keys[var_name.strip()] = var_name.strip()
                elif field.get("password") is True:
                    suggested = _derive_env_var_name(field_key, template)
                    if suggested not in global_var_keys:
                        password_keys[suggested] = suggested

    # Merge: global var refs take priority; password suggestions fill in the rest
    merged: list[DetectedEnvVar] = [DetectedEnvVar(key=k, global_variable_name=k) for k in sorted(global_var_keys)]
    merged.extend(
        DetectedEnvVar(key=k, global_variable_name=None) for k in sorted(password_keys) if k not in global_var_keys
    )

    return DetectEnvVarsResponse(variables=merged)
