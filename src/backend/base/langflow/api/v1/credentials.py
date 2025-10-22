"""API endpoints for credential management."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.credential.crud import (
    create_credential,
    delete_credential,
    get_credential_by_id,
    get_credentials_by_user,
    update_credential,
)
from langflow.services.database.models.credential.model import (
    CredentialCreate as ModelProviderCredentialCreate,
)
from langflow.services.database.models.credential.model import (
    CredentialRead as ModelProviderCredentialResponse,
)
from langflow.services.database.models.credential.model import (
    CredentialUpdate as ModelProviderCredentialUpdate,
)

router = APIRouter(tags=["Credentials"], prefix="/credentials")


@router.post("/", response_model=ModelProviderCredentialResponse, status_code=201)
async def create_model_provider_credential(
    credential: ModelProviderCredentialCreate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ModelProviderCredentialResponse:
    """Create a new model provider credential."""
    try:
        created_credential = await create_credential(db=session, user_id=current_user.id, credential=credential)
        return ModelProviderCredentialResponse.model_validate(created_credential)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to create credential: {e!s}"
        ) from e


@router.get("/", response_model=list[ModelProviderCredentialResponse])
async def get_model_provider_credentials(
    current_user: CurrentActiveUser,
    session: DbSession,
    provider: str | None = Query(None, description="Filter by provider name"),
) -> list[ModelProviderCredentialResponse]:
    """Get all model provider credentials for the current user."""
    try:
        credentials = await get_credentials_by_user(db=session, user_id=current_user.id, provider=provider)
        return [ModelProviderCredentialResponse.model_validate(cred) for cred in credentials]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve credentials: {e!s}"
        ) from e


@router.get("/{credential_id}", response_model=ModelProviderCredentialResponse)
async def get_model_provider_credential(
    credential_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ModelProviderCredentialResponse:
    """Get a specific model provider credential."""
    try:
        credential = await get_credential_by_id(db=session, credential_id=credential_id, user_id=current_user.id)

        if not credential:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")

        return ModelProviderCredentialResponse.model_validate(credential)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve credential: {e!s}"
        ) from e


@router.put("/{credential_id}", response_model=ModelProviderCredentialResponse)
async def update_model_provider_credential(
    credential_id: UUID,
    credential_update: ModelProviderCredentialUpdate,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> ModelProviderCredentialResponse:
    """Update a model provider credential."""
    try:
        updated_credential = await update_credential(
            db=session, credential_id=credential_id, user_id=current_user.id, credential_update=credential_update
        )
        return ModelProviderCredentialResponse.model_validate(updated_credential)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to update credential: {e!s}"
        ) from e


@router.delete("/{credential_id}")
async def delete_model_provider_credential(
    credential_id: UUID,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict[str, str]:
    """Delete a model provider credential."""
    try:
        await delete_credential(db=session, credential_id=credential_id, user_id=current_user.id)
        return {"detail": "Credential deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to delete credential: {e!s}"
        ) from e
