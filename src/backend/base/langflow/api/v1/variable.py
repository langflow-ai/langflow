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
from langflow.services.auth import utils as auth_utils
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
    """Read all variables.

    Model provider credentials are validated when reading from the database.
    If a provider key is invalid, its default_fields are cleared to prevent
    the provider from appearing enabled.

    Each variable in the response includes:
    - is_valid: bool | None - True if valid, False if invalid, None if not a provider credential
    - validation_error: str | None - Error message if validation failed

    Returns a list of variables with validation status for model provider credentials.
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        all_variables = await variable_service.get_all(user_id=current_user.id, session=session)

        # Filter out internal variables (those starting and ending with __)
        filtered_variables = [
            var for var in all_variables if not (var.name and var.name.startswith("__") and var.name.endswith("__"))
        ]

        # Validate model provider credentials and clear default_fields if invalid
        # Build dict of credential variables for validation
        credential_variables = {var.name: var for var in filtered_variables if var.type == CREDENTIAL_TYPE}
        provider_variable_map = get_model_provider_variable_mapping()

        # Create reverse mapping: variable_name -> provider
        var_to_provider = {var_name: provider for provider, var_name in provider_variable_map.items()}

        # Validate each provider credential once and capture both enabled status and error messages
        validation_results: dict[
            str, tuple[bool, str | None, list[str] | None]
        ] = {}  # var_name -> (is_valid, error, default_fields)

        for var_name in provider_variable_map.values():
            if var_name in credential_variables:
                is_valid = False
                error_message = None
                variable_obj = None

                try:
                    # Get the raw Variable object to access the encrypted value
                    variable_obj = await variable_service.get_variable_object(
                        user_id=current_user.id, name=var_name, session=session
                    )
                    if variable_obj and variable_obj.value:
                        # Decrypt the API key value
                        from langflow.services.deps import get_settings_service

                        settings_service = get_settings_service()
                        decrypted_value = auth_utils.decrypt_api_key(
                            variable_obj.value, settings_service=settings_service
                        )
                        if decrypted_value and decrypted_value.strip():
                            # Validate the key (this will raise ValueError if invalid)
                            await asyncio.to_thread(validate_model_provider_key, var_name, decrypted_value)
                            # Validation passed
                            is_valid = True
                            error_message = None
                        else:
                            error_message = "API key is empty"
                    else:
                        error_message = "Variable value is empty"
                except ValueError as e:
                    # Validation failed - get the error message
                    error_message = str(e)
                except Exception as e:  # noqa: BLE001
                    error_message = f"Validation error: {e!s}"

                # Update default_fields based on validation result
                updated_default_fields = None
                if variable_obj and variable_obj.id:
                    try:
                        if is_valid:
                            # Key is valid - ensure default_fields are set (important for migration)
                            provider_name = var_to_provider.get(var_name)
                            expected_default_fields = [provider_name, "api_key"] if provider_name else []
                            if variable_obj.default_fields != expected_default_fields:
                                await variable_service.update_variable_fields(
                                    user_id=current_user.id,
                                    variable_id=variable_obj.id,
                                    variable=VariableUpdate(
                                        id=variable_obj.id,
                                        default_fields=expected_default_fields,
                                    ),
                                    session=session,
                                )
                            updated_default_fields = expected_default_fields
                        else:
                            # Key is invalid - clear default_fields
                            if variable_obj.default_fields:
                                await variable_service.update_variable_fields(
                                    user_id=current_user.id,
                                    variable_id=variable_obj.id,
                                    variable=VariableUpdate(
                                        id=variable_obj.id,
                                        default_fields=[],
                                    ),
                                    session=session,
                                )
                            updated_default_fields = []
                    except Exception:  # noqa: BLE001
                        # Log but don't fail if we can't update
                        # Use current default_fields if update failed
                        updated_default_fields = variable_obj.default_fields if variable_obj else None

                validation_results[var_name] = (is_valid, error_message, updated_default_fields)

        # Set validation status on each variable and update default_fields in response
        for var in filtered_variables:
            if var.name and var.name in model_provider_variable_mapping.values() and var.type == CREDENTIAL_TYPE:
                result = validation_results.get(var.name)
                if result:
                    is_valid, error_message, updated_default_fields = result
                    var.is_valid = is_valid
                    var.validation_error = error_message
                    # Update default_fields in response to reflect what we set in database
                    # This is important for migration - valid keys will have default_fields set
                    if updated_default_fields is not None:
                        var.default_fields = updated_default_fields
                else:
                    # Variable not found in validation results
                    var.is_valid = False
                    var.validation_error = "Variable not found"
            else:
                # Not a model provider credential, validation fields remain None
                var.is_valid = None
                var.validation_error = None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return filtered_variables


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
