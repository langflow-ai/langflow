# ruff: noqa: ARG001
# TODO: Remove noqa once endpoint stubs are replaced with real implementations.
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from lfx.services.deployment.schema import (
    DeploymentType,
)

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.schemas.deployments import (
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentDuplicateParams,
    DeploymentDuplicateResponse,
    DeploymentGetResponse,
    DeploymentListResponse,
    DeploymentStatusResponse,
    DeploymentTypeListResponse,
    DeploymentUpdateRequest,
    DeploymentUpdateResponse,
    ExecutionCreateRequest,
    ExecutionCreateResponse,
    ExecutionStatusResponse,
    ProviderAccountCreate,
    ProviderAccountListResponse,
    ProviderAccountResponse,
    ProviderAccountUpdate,
    RedeployResponse,
    validate_flow_version_id_query,
)

router = APIRouter(prefix="/deployments", tags=["Deployments"])


ProviderIdQuery = Annotated[
    UUID,
    Query(description="Deployment provider account id."),
]


# API provider-context contract matrix:
# - Query provider_id: list/provider-capability/runtime-status GET endpoints.
# - Body provider_id: POST create operations that cannot derive provider context.
# - Derived provider_id: deployment-scoped endpoints using persisted deployment relationships.


# ---------------------------------------------------------------------------
# Routes: Provider accounts
# ---------------------------------------------------------------------------


@router.post(
    "/providers",
    response_model=ProviderAccountResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Deployment Providers"],
)
async def create_provider_account(
    payload: ProviderAccountCreate,
    user: CurrentActiveUser,
    db: DbSession,
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/providers", response_model=ProviderAccountListResponse, tags=["Deployment Providers"])
async def list_provider_accounts(
    user: CurrentActiveUser,
    db: DbSessionReadOnly,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get(
    "/providers/{provider_id}",
    response_model=ProviderAccountResponse,
    tags=["Deployment Providers"],
)
async def get_provider_account(
    provider_id: UUID,
    user: CurrentActiveUser,
    db: DbSessionReadOnly,
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.delete(
    "/providers/{provider_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Deployment Providers"],
)
async def delete_provider_account(
    provider_id: UUID,
    user: CurrentActiveUser,
    db: DbSession,
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.patch(
    "/providers/{provider_id}",
    response_model=ProviderAccountResponse,
    tags=["Deployment Providers"],
)
async def update_provider_account(
    provider_id: UUID,
    payload: ProviderAccountUpdate,
    user: CurrentActiveUser,
    db: DbSession,
):
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


# ---------------------------------------------------------------------------
# Routes: Deployments
# ---------------------------------------------------------------------------


@router.post("", response_model=DeploymentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    user: CurrentActiveUser,
    payload: DeploymentCreateRequest,
    db: DbSession,
):
    """Create a deployment for the selected provider account."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/types", response_model=DeploymentTypeListResponse)
async def list_deployment_types(
    provider_id: ProviderIdQuery,
    user: CurrentActiveUser,
    db: DbSessionReadOnly,
):
    """List deployment types for a provider account."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    provider_id: ProviderIdQuery,
    user: CurrentActiveUser,
    db: DbSessionReadOnly,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
    deployment_type: Annotated[DeploymentType | None, Query()] = None,
    flow_version_ids: Annotated[
        list[str] | None,
        Query(
            description=(
                "Optional flow version ids. When provided, deployments are filtered to those "
                "with at least one matching attachment (OR semantics across ids)."
            )
        ),
    ] = None,
):
    """List deployments for a provider account."""
    if flow_version_ids is not None:
        flow_version_ids = validate_flow_version_id_query(flow_version_ids)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


# ---------------------------------------------------------------------------
# Routes: Executions
# ---------------------------------------------------------------------------


@router.post("/executions", response_model=ExecutionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_execution(
    payload: ExecutionCreateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Create a deployment execution."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
async def get_deployment_execution(
    execution_id: UUID,
    provider_id: ProviderIdQuery,
    db: DbSessionReadOnly,
    user: CurrentActiveUser,
):
    """Get deployment execution status."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


# ---------------------------------------------------------------------------
# Routes: Single deployment operations
# ---------------------------------------------------------------------------


@router.get("/{deployment_id}", response_model=DeploymentGetResponse)
async def get_deployment(
    deployment_id: UUID,
    user: CurrentActiveUser,
    db: DbSessionReadOnly,
):
    """Get a deployment by id."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.patch(
    "/{deployment_id}",
    response_model=DeploymentUpdateResponse,
)
async def update_deployment(
    deployment_id: UUID,
    payload: DeploymentUpdateRequest,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Update a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: UUID,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Delete a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.post(
    "/{deployment_id}/redeploy",
    response_model=RedeployResponse,
)
async def redeploy_deployment(
    deployment_id: UUID,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Redeploy a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.post(
    "/{deployment_id}/duplicate",
    response_model=DeploymentDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_deployment(
    deployment_id: UUID,
    payload: DeploymentDuplicateParams,
    db: DbSession,
    user: CurrentActiveUser,
):
    """Duplicate a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get(
    "/{deployment_id}/status",
    response_model=DeploymentStatusResponse,
)
async def get_deployment_status(
    deployment_id: UUID,
    db: DbSessionReadOnly,
    user: CurrentActiveUser,
):
    """Get deployment status."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")
