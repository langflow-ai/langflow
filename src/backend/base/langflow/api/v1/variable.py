import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.base.models.unified_models import get_model_provider_variable_mapping, validate_model_provider_key
from sqlalchemy.exc import NoResultFound

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.api.v1.models import (
    DISABLED_MODELS_VAR,
    ENABLED_MODELS_VAR,
    get_model_names_for_provider,
    get_provider_from_variable_name,
)
from langflow.services.database.models.variable.model import VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/variables", tags=["Variables"])
model_provider_variable_mapping = get_model_provider_variable_mapping()
logger = logging.getLogger(__name__)


async def _cleanup_model_list_variable(
    variable_service: DatabaseVariableService,
    user_id: UUID,
    variable_name: str,
    models_to_remove: set[str],
    session: DbSession,
) -> None:
    """Remove specified models from a model list variable (disabled or enabled models).

    If all models are removed, the variable is deleted entirely.
    If the variable doesn't exist, this is a no-op.
    """
    try:
        model_list_var = await variable_service.get_variable_object(
            user_id=user_id, name=variable_name, session=session
        )
    except ValueError:
        # Variable doesn't exist, nothing to clean up
        return

    if not model_list_var or not model_list_var.value:
        return

    # Parse current models
    try:
        current_models = set(json.loads(model_list_var.value))
    except (json.JSONDecodeError, TypeError):
        current_models = set()

    # Filter out the provider's models
    filtered_models = current_models - models_to_remove

    # Nothing changed, no update needed
    if filtered_models == current_models:
        return

    if filtered_models:
        # Update with filtered list
        if model_list_var.id is not None:
            await variable_service.update_variable_fields(
                user_id=user_id,
                variable_id=model_list_var.id,
                variable=VariableUpdate(
                    id=model_list_var.id,
                    name=variable_name,
                    value=json.dumps(list(filtered_models)),
                    type=GENERIC_TYPE,
                ),
                session=session,
            )
    else:
        # No models left, delete the variable
        await variable_service.delete_variable(user_id=user_id, name=variable_name, session=session)


async def _cleanup_provider_models(
    variable_service: DatabaseVariableService,
    user_id: UUID,
    provider: str,
    session: DbSession,
) -> None:
    """Clean up disabled and enabled model lists for a deleted provider credential."""
    try:
        provider_models = get_model_names_for_provider(provider)
    except ValueError:
        logger.exception("Provider model retrieval failed")
        return

    # Clean up disabled and enabled models
    await _cleanup_model_list_variable(variable_service, user_id, DISABLED_MODELS_VAR, provider_models, session)
    await _cleanup_model_list_variable(variable_service, user_id, ENABLED_MODELS_VAR, provider_models, session)


@router.post("/", response_model=VariableRead, status_code=201)
async def create_variable(
    *,
    session: DbSession,
    variable: VariableCreate,
    current_user: CurrentActiveUser,
):
    """Create a new variable."""
    variable_service = get_variable_service()
    if not variable.name and not variable.value:
        raise HTTPException(status_code=400, detail="Variable name and value cannot be empty")

    if not variable.name:
        raise HTTPException(status_code=400, detail="Variable name cannot be empty")

    if not variable.value:
        raise HTTPException(status_code=400, detail="Variable value cannot be empty")

    if variable.name in await variable_service.list_variables(user_id=current_user.id, session=session):
        raise HTTPException(status_code=400, detail="Variable name already exists")

    # Check if the variable is a reserved model provider variable
    if variable.name in model_provider_variable_mapping.values():
        # Validate that the key actually works using the Language Model Service
        # Run validation off the event loop to avoid blocking
        try:
            await asyncio.to_thread(validate_model_provider_key, variable.name, variable.value)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        return await variable_service.create_variable(
            user_id=current_user.id,
            name=variable.name,
            value=variable.value,
            default_fields=variable.default_fields or [],
            type_=variable.type or CREDENTIAL_TYPE,
            session=session,
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/", response_model=list[VariableRead], status_code=200)
async def read_variables(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Read all variables."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        all_variables = await variable_service.get_all(user_id=current_user.id, session=session)
        # Filter out internal variables (those starting and ending with __)
        return [
            var for var in all_variables if not (var.name and var.name.startswith("__") and var.name.endswith("__"))
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/{variable_id}", response_model=VariableRead, status_code=200)
async def update_variable(
    *,
    session: DbSession,
    variable_id: UUID,
    variable: VariableUpdate,
    current_user: CurrentActiveUser,
):
    """Update a variable."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        # Get existing variable to check if it's a model provider credential
        existing_variable = await variable_service.get_variable_by_id(
            user_id=current_user.id, variable_id=variable_id, session=session
        )

        # Validate API key if updating a model provider variable
        if existing_variable.name in model_provider_variable_mapping.values() and variable.value:
            # Run validation off the event loop to avoid blocking
            try:
                await asyncio.to_thread(validate_model_provider_key, existing_variable.name, variable.value)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e)) from e

        return await variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=variable_id,
            variable=variable,
            session=session,
        )
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/{variable_id}", status_code=204)
async def delete_variable(
    *,
    session: DbSession,
    variable_id: UUID,
    current_user: CurrentActiveUser,
) -> None:
    """Delete a variable.

    If the deleted variable is a model provider credential (e.g., OPENAI_API_KEY),
    all disabled models for that provider are automatically cleared.
    """
    variable_service = get_variable_service()
    try:
        # Get the variable before deleting to check if it's a provider credential
        variable_to_delete = await variable_service.get_variable_by_id(
            user_id=current_user.id, variable_id=variable_id, session=session
        )

        # Check if this variable is a model provider credential
        provider = get_provider_from_variable_name(variable_to_delete.name)

        # Delete the variable
        await variable_service.delete_variable_by_id(user_id=current_user.id, variable_id=variable_id, session=session)

        # If this was a provider credential, clean up disabled and enabled models for that provider
        if provider and isinstance(variable_service, DatabaseVariableService):
            await _cleanup_provider_models(variable_service, current_user.id, provider, session)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
