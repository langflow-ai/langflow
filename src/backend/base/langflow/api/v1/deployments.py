# ruff: noqa: ARG001
# TODO: Remove noqa once endpoint stubs are replaced with real implementations.
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Query, status
from lfx.services.adapters.deployment.schema import (
    DeploymentType,
)

from langflow.api.utils import CurrentActiveUser, DbSession, DbSessionReadOnly
from langflow.api.v1.schemas.deployments import (
    DeploymentConfigListResponse,
    DeploymentCreateRequest,
    DeploymentCreateResponse,
    DeploymentDuplicateResponse,
    DeploymentGetResponse,
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


# API provider-context contract matrix:
# - Query/path ``provider_id`` is a Langflow DB UUID referencing deployment_provider_account.
# - Body ``provider_id`` is included on ``DeploymentCreateRequest`` and ``ExecutionCreateRequest``
#   to allow provider routing without an extra DB lookup when the caller already has the context.
# - Deployment-scoped routes derive provider context from persisted Langflow relationships.
#
# TODO(deployments-routing): Before replacing 501 stubs with live routing:
# - Resolve provider_key from provider_id/deployment_id and fetch adapter via registry.
# - If adapter is unavailable in current runtime (e.g. optional SDK not installed),
#   return a deterministic domain error/HTTP status instead of 500.
# - Add tests for:
#   * provider account exists but adapter key not registered
#   * adapter import was skipped at startup due to ModuleNotFoundError
#   * direct WXO provider routes in unsupported runtimes (py3.10 scenarios)


# ---------------------------------------------------------------------------
# Routes: Provider accounts
# ---------------------------------------------------------------------------


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
    """Register a new deployment provider account."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/providers", response_model=DeploymentProviderAccountListResponse, tags=["Deployment Providers"])
async def list_provider_accounts(
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
):
    """List all deployment provider accounts for the current user."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


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
    """Get a deployment provider account by id."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


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
    """Delete a deployment provider account."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


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
    """Partially update a deployment provider account."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


# ---------------------------------------------------------------------------
# Routes: Deployments
# ---------------------------------------------------------------------------


@router.post("", response_model=DeploymentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(
    session: DbSession,
    payload: DeploymentCreateRequest,
    current_user: CurrentActiveUser,
):
    """Create a deployment under the provider account specified in the request body."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("", response_model=DeploymentListResponse)
async def list_deployments(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=50)] = 20,
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
    """List deployments for the selected Langflow provider-account UUID."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/types", response_model=DeploymentTypeListResponse)
async def list_deployment_types(
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    """List deployment types for the selected Langflow provider-account UUID."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


# ---------------------------------------------------------------------------
# Routes: Executions
# ---------------------------------------------------------------------------


@router.post("/executions", response_model=ExecutionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment_execution(
    session: DbSession,
    payload: ExecutionCreateRequest,
    current_user: CurrentActiveUser,
):
    """Create a deployment execution for Langflow DB deployment/provider identifiers."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get("/executions/{execution_id}", response_model=ExecutionStatusResponse)
async def get_deployment_execution(
    execution_id: Annotated[str, Path(min_length=1, description="Provider-owned opaque execution identifier.")],
    provider_id: DeploymentProviderAccountIdQuery,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    """Get deployment execution status by provider-owned execution id and Langflow provider id."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


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
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


# ---------------------------------------------------------------------------
# Routes: Deployment details and actions
# ---------------------------------------------------------------------------


@router.get("/{deployment_id}", response_model=DeploymentGetResponse)
async def get_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    """Get a deployment by id."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


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
    """Update a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.delete("/{deployment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.get(
    "/{deployment_id}/status",
    response_model=DeploymentStatusResponse,
)
async def get_deployment_status(
    deployment_id: DeploymentIdPath,
    session: DbSessionReadOnly,
    current_user: CurrentActiveUser,
):
    """Get deployment status."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.post(
    "/{deployment_id}/redeploy",
    response_model=DeploymentRedeployResponse,
)
async def redeploy_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Redeploy a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")


@router.post(
    "/{deployment_id}/duplicate",
    response_model=DeploymentDuplicateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def duplicate_deployment(
    deployment_id: DeploymentIdPath,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Duplicate a deployment."""
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented.")
