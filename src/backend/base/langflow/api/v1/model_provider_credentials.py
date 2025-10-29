"""API endpoints for model provider credentials CRUD operations."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

# Import the provider metadata to get valid provider names
from lfx.base.models.unified_models import get_model_provider_metadata
from pydantic import BaseModel, Field, field_validator

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService

_VALID_PROVIDERS = set(get_model_provider_metadata().keys())

# Get all reserved fields for model provider API keys
model_providers = get_model_provider_metadata()
api_key_fields = {info["variable_name"] for info in model_providers.values()}


class ModelProviderCredentialRequest(BaseModel):
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

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that provider is in the valid list of supported providers."""
        # Use the cached set for membership test
        if v not in _VALID_PROVIDERS:
            msg = f"Invalid provider '{v}'. Must be one of: {', '.join(_VALID_PROVIDERS)}"
            raise ValueError(msg)
        return v


class ModelProviderCredentialResponse(BaseModel):
    """Response model for model provider credentials without sensitive value field."""

    id: UUID = Field(..., description="Unique ID of the credential")
    name: str = Field(..., description="Name of the credential")
    type: str = Field(..., description="Type of the credential")
    default_fields: list[str] | None = Field(None, description="Default fields for the credential")
    created_at: datetime | None = Field(None, description="When the credential was created")
    updated_at: datetime | None = Field(None, description="When the credential was last updated")


router = APIRouter(tags=["Model Provider Credentials"], prefix="/model-provider-credentials")


@router.post("/", response_model=ModelProviderCredentialResponse, status_code=201)
async def create_model_provider_credential(
    request: ModelProviderCredentialRequest,
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

        # Create a variable name matching the expected format (e.g., OPENAI_API_KEY)
        # Map provider names to their variable name format
        from lfx.base.models.unified_models import get_model_provider_variable_mapping

        provider_variable_map = get_model_provider_variable_mapping()
        credential_name = provider_variable_map.get(request.provider)

        if not credential_name:
            # Fallback: generate name from provider if not in mapping
            credential_name = f"{request.provider.upper().replace(' ', '_')}_API_KEY"

        # Check if credential already exists and update it, otherwise create new
        try:
            existing_variable = await variable_service.get_variable_object(
                user_id=current_user.id,
                name=credential_name,
                session=session,
            )
        except (ValueError, KeyError):
            existing_variable = None

        if existing_variable is not None and existing_variable.id:
            # Update existing credential using update_variable_fields to preserve all fields
            from langflow.services.database.models.variable.model import VariableUpdate

            variable_update = VariableUpdate(
                id=existing_variable.id,
                name=credential_name,
                value=request.value,
                type=CREDENTIAL_TYPE,
                default_fields=[request.provider, "api_key"],
            )

            updated_var = await variable_service.update_variable_fields(
                user_id=current_user.id,
                variable_id=existing_variable.id,
                variable=variable_update,
                session=session,
            )
            # Convert to ModelProviderCredentialResponse
            return ModelProviderCredentialResponse.model_validate(updated_var, from_attributes=True)

        # Create new credential
        created_var = await variable_service.create_variable(
            user_id=current_user.id,
            name=credential_name,
            value=request.value,
            default_fields=[request.provider, "api_key"],
            type_=CREDENTIAL_TYPE,
            session=session,
        )
        # Convert to ModelProviderCredentialResponse
        return ModelProviderCredentialResponse.model_validate(created_var, from_attributes=True)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create model provider credential: {e!s}",
        ) from e


@router.get("/", response_model=list[ModelProviderCredentialResponse])
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

        # Filter for model provider credentials
        credentials = [var for var in all_variables if var.name in api_key_fields]

        # Filter by provider if specified
        if provider:
            filtered_credentials = [
                cred
                for cred in credentials
                if cred.default_fields
                and len(cred.default_fields) > 0
                and cred.default_fields[0].lower() == provider.lower()
            ]
        else:
            filtered_credentials = credentials

        # Convert to ModelProviderCredentialResponse
        return [
            ModelProviderCredentialResponse.model_validate(cred, from_attributes=True) for cred in filtered_credentials
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model provider credentials: {e!s}",
        ) from e


@router.get("/{credential_id}", response_model=ModelProviderCredentialResponse)
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
    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Fetch variable by ID using service
        credential = await variable_service.get_variable_by_id(
            user_id=current_user.id,
            variable_id=credential_id,
            session=session,
        )

        # Verify it's a model provider credential
        if credential.name not in api_key_fields:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )
    except ValueError as e:
        # Variable not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model provider credential not found",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve model provider credential: {e!s}",
        ) from e
    else:
        return ModelProviderCredentialResponse.model_validate(credential, from_attributes=True)


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

    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Fetch variable by ID using service
        credential = await variable_service.get_variable_by_id(
            user_id=current_user.id,
            variable_id=credential_id,
            session=session,
        )

        # Verify it's a model provider credential
        if credential.name not in api_key_fields:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Model provider credential not found",
            )

        # Decrypt the value directly
        decrypted_value = auth_utils.decrypt_api_key(
            credential.value, settings_service=variable_service.settings_service
        )

    except ValueError as e:
        # Variable not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model provider credential not found",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credential value: {e!s}",
        ) from e

    return {"value": decrypted_value}


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
    try:
        variable_service = get_variable_service()
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Variable service is not available",
            )

        # Fetch variable by ID using service
        existing_credential = await variable_service.get_variable_by_id(
            user_id=current_user.id,
            variable_id=credential_id,
            session=session,
        )

        # Verify it's a model provider credential
        if existing_credential.name not in api_key_fields:
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

    except ValueError as e:
        # Variable not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model provider credential not found",
        ) from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        if credential.name not in api_key_fields:
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


@router.get("/provider/{provider}", response_model=list[ModelProviderCredentialResponse])
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
        credentials = [var for var in all_variables if var.name in api_key_fields]

        # Filter by provider using list comprehension
        filtered_credentials = [
            cred
            for cred in credentials
            if cred.default_fields
            and len(cred.default_fields) > 0
            and cred.default_fields[0].lower() == provider.lower()
        ]

        # Convert to ModelProviderCredentialResponse
        return [
            ModelProviderCredentialResponse.model_validate(cred, from_attributes=True) for cred in filtered_credentials
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credentials for provider {provider}: {e!s}",
        ) from e
