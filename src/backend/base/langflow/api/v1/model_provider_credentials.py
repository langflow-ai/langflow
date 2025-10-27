"""API endpoints for model provider credentials CRUD operations."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.variable.model import VariableRead
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CATEGORY_GLOBAL, CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService


class ModelProviderCredentialCreate(BaseModel):
    """Request model for creating a model provider credential."""

    name: str = Field(..., description="Name of the credential")
    provider: str = Field(..., description="Model provider (e.g., OpenAI, Anthropic)")
    value: str = Field(..., description="API key value")
    description: str | None = Field(None, description="Optional description of the credential")

    @field_validator("name", "provider", "value")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        """Validate that string fields are not empty."""
        if not v or not v.strip():
            msg = "Field cannot be empty"
            raise ValueError(msg)
        return v


class ModelProviderCredentialResponse(BaseModel):
    """Response model for credential metadata."""

    name: str = Field(..., description="Name of the credential")
    provider: str = Field(..., description="Model provider (e.g., OpenAI, Anthropic)")
    description: str | None = Field(None, description="Description of the credential")
    created_at: str = Field(..., description="When the credential was created")
    updated_at: str = Field(..., description="When the credential was last updated")


router = APIRouter(tags=["Model Provider Credentials"], prefix="/model-provider-credentials")


@router.post("/", response_model=VariableRead, status_code=201)
async def create_model_provider_credential(
    request: ModelProviderCredentialCreate,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Create a new model provider credential.

    Args:
        request: Model provider credential creation request
        current_user: Current authenticated user
        session: Database session

    Returns:
        VariableRead: The created credential
    """
    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Create a unique name that includes the provider
        credential_name = f"{request.provider.lower()}_{request.name.lower().replace(' ', '_')}"

        return await variable_service.create_variable(
            user_id=current_user.id,
            name=credential_name,
            value=request.value,
            default_fields=[request.provider, "api_key"],
            type_=CREDENTIAL_TYPE,
            category=CATEGORY_GLOBAL,
            session=session,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create model provider credential: {e!s}",
        ) from e


@router.get("/", response_model=list[VariableRead])
async def get_model_provider_credentials(
    provider: Annotated[str | None, Query(description="Filter by provider name")] = None,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get model provider credentials for the current user.

    Args:
        provider: Optional provider filter
        current_user: Current authenticated user
        session: Database session

    Returns:
        list[VariableRead]: List of credentials
    """
    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Get all variables for the user
        all_variables = await variable_service.get_all(
            user_id=current_user.id,
            session=session,
        )

        # Filter for model provider credentials (those with CREDENTIAL_TYPE and CATEGORY_GLOBAL)
        credentials = [var for var in all_variables if var.type == CREDENTIAL_TYPE and var.category == CATEGORY_GLOBAL]

        # Filter by provider if specified
        if provider:
            return [
                cred
                for cred in credentials
                if cred.default_fields
                and len(cred.default_fields) > 0
                and cred.default_fields[0].lower() == provider.lower()
            ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model provider credentials: {e!s}",
        ) from e

    return credentials


@router.get("/{credential_id}", response_model=VariableRead)
async def get_model_provider_credential(
    credential_id: UUID,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get a specific model provider credential by ID.

    Args:
        credential_id: The ID of the credential
        current_user: Current authenticated user
        session: Database session

    Returns:
        VariableRead: The credential
    """
    from langflow.services.database.models.variable.model import Variable
    from sqlmodel import select

    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Query variable by ID directly
        stmt = select(Variable).where(Variable.id == credential_id, Variable.user_id == current_user.id)
        credential = (await session.exec(stmt)).first()
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Verify it's a model provider credential
        if credential.type != CREDENTIAL_TYPE or credential.category != CATEGORY_GLOBAL:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model provider credential: {e!s}",
        ) from e
    else:
        return credential


@router.get("/{credential_id}/value")
async def get_model_provider_credential_value(
    credential_id: UUID,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get the decrypted value of a model provider credential.

    Args:
        credential_id: The ID of the credential
        current_user: Current authenticated user
        session: Database session

    Returns:
        dict: The decrypted credential value
    """
    from langflow.services.auth import utils as auth_utils
    from langflow.services.database.models.variable.model import Variable
    from sqlmodel import select

    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Query variable by ID directly
        stmt = select(Variable).where(Variable.id == credential_id, Variable.user_id == current_user.id)
        credential = (await session.exec(stmt)).first()
        
        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Verify it's a model provider credential
        if credential.type != CREDENTIAL_TYPE or credential.category != CATEGORY_GLOBAL:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Decrypt the value directly
        decrypted_value = auth_utils.decrypt_api_key(
            credential.value, 
            settings_service=variable_service.settings_service
        )

        return {"value": decrypted_value}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credential value: {e!s}",
        ) from e


@router.delete("/{credential_id}", status_code=status.HTTP_200_OK)
async def delete_model_provider_credential(
    credential_id: UUID,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Delete a model provider credential by ID.

    Args:
        credential_id: The ID of the credential
        current_user: Current authenticated user
        session: Database session

    Returns:
        dict: Success message
    """
    from langflow.services.database.models.variable.model import Variable
    from sqlmodel import select

    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Query variable by ID directly
        stmt = select(Variable).where(Variable.id == credential_id, Variable.user_id == current_user.id)
        existing_credential = (await session.exec(stmt)).first()

        if not existing_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Verify it's a model provider credential
        if existing_credential.type != CREDENTIAL_TYPE or existing_credential.category != CATEGORY_GLOBAL:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Delete the credential by name
        await variable_service.delete_variable(
            user_id=current_user.id,
            name=existing_credential.name,
            session=session,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to delete model provider credential: {e!s}",
        ) from e

    return {"detail": "Credential deleted successfully"}


@router.get("/{name}/metadata", response_model=ModelProviderCredentialResponse)
async def get_model_provider_credential_metadata(
    name: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get metadata for a model provider credential.

    Args:
        name: The name of the credential
        current_user: Current authenticated user
        session: Database session

    Returns:
        ModelProviderCredentialResponse: Credential metadata
    """
    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Get the credential first
        credential = await variable_service.get_variable_object(
            user_id=current_user.id,
            name=name,
            session=session,
        )

        if not credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Verify it's a model provider credential
        if credential.type != CREDENTIAL_TYPE or credential.category != CATEGORY_GLOBAL:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Extract provider from default_fields
        provider = credential.default_fields[0] if credential.default_fields else "Unknown"

        return ModelProviderCredentialResponse(
            name=credential.name,
            provider=provider,
            description=credential.description,
            created_at=credential.created_at.isoformat() if credential.created_at else "",
            updated_at=credential.updated_at.isoformat() if credential.updated_at else "",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credential value: {e!s}",
        ) from e


@router.get("/provider/{provider}", response_model=list[VariableRead])
async def get_credentials_by_provider(
    provider: str,
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Get all credentials for a specific provider.

    Args:
        provider: The provider name
        current_user: Current authenticated user
        session: Database session

    Returns:
        list[VariableRead]: List of credentials for the provider
    """
    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Get all variables for the user
        all_variables = await variable_service.get_all(
            user_id=current_user.id,
            session=session,
        )

        # Filter for model provider credentials
        credentials = [var for var in all_variables if var.type == CREDENTIAL_TYPE and var.category == CATEGORY_GLOBAL]

        # Filter by provider using list comprehension
        return [
            cred
            for cred in credentials
            if cred.default_fields
            and len(cred.default_fields) > 0
            and cred.default_fields[0].lower() == provider.lower()
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credentials for provider {provider}: {e!s}",
        ) from e
