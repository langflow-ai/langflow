from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.base.models.unified_models import get_model_provider_variable_mapping, validate_model_provider_key
from sqlalchemy.exc import NoResultFound

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.database.models.variable.model import VariableCreate, VariableRead, VariableUpdate
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/variables", tags=["Variables"])
model_provider_variable_mapping = get_model_provider_variable_mapping()


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
        try:
            validate_model_provider_key(variable.name, variable.value)
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
        return await variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=variable_id,
            variable=variable,
            session=session,
        )
    except NoResultFound as e:
        raise HTTPException(status_code=404, detail="Variable not found") from e

    except Exception as e:
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
        import json

        from langflow.api.v1.models import (
            DISABLED_MODELS_VAR,
            ENABLED_MODELS_VAR,
            get_model_names_for_provider,
            get_provider_from_variable_name,
        )

        provider = get_provider_from_variable_name(variable_to_delete.name)

        # Delete the variable
        await variable_service.delete_variable_by_id(user_id=current_user.id, variable_id=variable_id, session=session)

        # If this was a provider credential, clean up disabled and enabled models for that provider
        if provider:
            try:
                # Get all model names for this provider
                provider_models = get_model_names_for_provider(provider)

                # Clean up disabled models
                try:
                    disabled_var = await variable_service.get_variable_object(
                        user_id=current_user.id, name=DISABLED_MODELS_VAR, session=session
                    )
                    if disabled_var and disabled_var.value:
                        try:
                            disabled_models = set(json.loads(disabled_var.value))
                        except (json.JSONDecodeError, TypeError):
                            disabled_models = set()

                        # Remove provider's models from disabled list
                        disabled_models_filtered = disabled_models - provider_models

                        # Update the disabled models variable if anything changed
                        if disabled_models_filtered != disabled_models:
                            if disabled_models_filtered:
                                # Update with filtered list
                                from langflow.services.database.models.variable.model import VariableUpdate
                                from langflow.services.variable.constants import GENERIC_TYPE

                                await variable_service.update_variable_fields(
                                    user_id=current_user.id,
                                    variable_id=disabled_var.id,
                                    variable=VariableUpdate(
                                        id=disabled_var.id,
                                        name=DISABLED_MODELS_VAR,
                                        value=json.dumps(list(disabled_models_filtered)),
                                        type=GENERIC_TYPE,
                                    ),
                                    session=session,
                                )
                            else:
                                # No disabled models left for any provider, delete the variable
                                await variable_service.delete_variable(
                                    user_id=current_user.id, name=DISABLED_MODELS_VAR, session=session
                                )
                except ValueError:
                    # DISABLED_MODELS_VAR doesn't exist, nothing to clean up
                    pass

                # Clean up explicitly enabled models
                try:
                    enabled_var = await variable_service.get_variable_object(
                        user_id=current_user.id, name=ENABLED_MODELS_VAR, session=session
                    )
                    if enabled_var and enabled_var.value:
                        try:
                            enabled_models = set(json.loads(enabled_var.value))
                        except (json.JSONDecodeError, TypeError):
                            enabled_models = set()

                        # Remove provider's models from enabled list
                        enabled_models_filtered = enabled_models - provider_models

                        # Update the enabled models variable if anything changed
                        if enabled_models_filtered != enabled_models:
                            if enabled_models_filtered:
                                # Update with filtered list
                                from langflow.services.database.models.variable.model import VariableUpdate
                                from langflow.services.variable.constants import GENERIC_TYPE

                                await variable_service.update_variable_fields(
                                    user_id=current_user.id,
                                    variable_id=enabled_var.id,
                                    variable=VariableUpdate(
                                        id=enabled_var.id,
                                        name=ENABLED_MODELS_VAR,
                                        value=json.dumps(list(enabled_models_filtered)),
                                        type=GENERIC_TYPE,
                                    ),
                                    session=session,
                                )
                            else:
                                # No enabled models left for any provider, delete the variable
                                await variable_service.delete_variable(
                                    user_id=current_user.id, name=ENABLED_MODELS_VAR, session=session
                                )
                except ValueError:
                    # ENABLED_MODELS_VAR doesn't exist, nothing to clean up
                    pass
            except ValueError:
                # Log the exception if provider model retrieval fails
                import logging

                logger = logging.getLogger(__name__)
                logger.exception("Provider model retrieval failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
