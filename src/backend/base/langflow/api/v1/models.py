from __future__ import annotations

import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_model_providers,
    get_unified_models_detailed,
)
from pydantic import BaseModel, field_validator

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.auth.utils import get_current_active_user
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE, GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])

# Variable names for storing disabled models and default models
DISABLED_MODELS_VAR = "__disabled_models__"
ENABLED_MODELS_VAR = "__enabled_models__"
DEFAULT_LANGUAGE_MODEL_VAR = "__default_language_model__"
DEFAULT_EMBEDDING_MODEL_VAR = "__default_embedding_model__"

# Security limits
MAX_STRING_LENGTH = 200  # Maximum length for model IDs and provider names
MAX_BATCH_UPDATE_SIZE = 100  # Maximum number of models that can be updated at once


def get_provider_from_variable_name(variable_name: str) -> str | None:
    """Get provider name from a model provider variable name.

    Args:
        variable_name: The variable name (e.g., "OPENAI_API_KEY")

    Returns:
        The provider name (e.g., "OpenAI") or None if not a model provider variable
    """
    provider_mapping = get_model_provider_variable_mapping()
    # Reverse the mapping to get provider from variable name
    for provider, var_name in provider_mapping.items():
        if var_name == variable_name:
            return provider
    return None


def get_model_names_for_provider(provider: str) -> set[str]:
    """Get all model names for a given provider.

    Args:
        provider: The provider name (e.g., "OpenAI")

    Returns:
        A set of model names for that provider
    """
    models_by_provider = get_unified_models_detailed(
        providers=[provider],
        include_unsupported=True,
        include_deprecated=True,
    )

    model_names = set()
    for provider_dict in models_by_provider:
        if provider_dict.get("provider") == provider:
            for model in provider_dict.get("models", []):
                model_names.add(model.get("model_name"))

    return model_names


class ModelStatusUpdate(BaseModel):
    """Request model for updating model enabled status."""

    provider: str
    model_id: str
    enabled: bool

    @field_validator("model_id", "provider")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure strings are non-empty and reasonable length."""
        if not v or not v.strip():
            msg = "Field cannot be empty"
            raise ValueError(msg)
        if len(v) > MAX_STRING_LENGTH:
            msg = f"Field exceeds maximum length of {MAX_STRING_LENGTH} characters"
            raise ValueError(msg)
        return v.strip()


@router.get("/providers", status_code=200, dependencies=[Depends(get_current_active_user)])
async def list_model_providers() -> list[str]:
    """Return available model providers."""
    return get_model_providers()


@router.get("", status_code=200)
async def list_models(
    *,
    provider: Annotated[list[str] | None, Query(description="Repeat to include multiple providers")] = None,
    model_name: str | None = None,
    model_type: str | None = None,
    include_unsupported: bool = False,
    include_deprecated: bool = False,
    # common metadata filters
    tool_calling: bool | None = None,
    reasoning: bool | None = None,
    search: bool | None = None,
    preview: bool | None = None,
    deprecated: bool | None = None,
    not_supported: bool | None = None,
    session: DbSession,
    current_user: CurrentActiveUser,
):
    """Return model catalog filtered by query parameters.

    Pass providers as repeated query params, e.g. `?provider=OpenAI&provider=Anthropic`.
    """
    selected_providers: list[str] | None = provider
    metadata_filters = {
        k: v
        for k, v in {
            "tool_calling": tool_calling,
            "reasoning": reasoning,
            "search": search,
            "preview": preview,
            "deprecated": deprecated,
            "not_supported": not_supported,
        }.items()
        if v is not None
    }

    # Get enabled providers status
    enabled_providers_result = await get_enabled_providers(session=session, current_user=current_user)
    provider_status = enabled_providers_result.get("provider_status", {})

    # Get default model if model_type is specified
    default_provider = None
    if model_type:
        try:
            default_model_result = await get_default_model(
                session=session, current_user=current_user, model_type=model_type
            )
            if default_model_result.get("default_model"):
                default_provider = default_model_result["default_model"].get("provider")
        except Exception:  # noqa: BLE001
            # Default model fetch failed, continue without it
            # This is not critical for the main operation - we suppress to avoid breaking the list
            logger.debug("Failed to fetch default model, continuing without it", exc_info=True)

    # Get filtered models - pass providers directly to avoid filtering after
    filtered_models = get_unified_models_detailed(
        providers=selected_providers,
        model_name=model_name,
        include_unsupported=include_unsupported,
        include_deprecated=include_deprecated,
        model_type=model_type,
        **metadata_filters,
    )
    # Add enabled status to each provider
    for provider_dict in filtered_models:
        provider_dict["is_enabled"] = provider_status.get(provider_dict.get("provider"), False)

    # Sort providers:
    # 1. Provider with default model first
    # 2. Enabled providers next
    # 3. Alphabetically after that
    def sort_key(provider_dict):
        provider_name = provider_dict.get("provider", "")
        is_enabled = provider_dict.get("is_enabled", False)
        is_default = provider_name == default_provider

        # Return tuple for sorting: (not is_default, not is_enabled, provider_name)
        # This way default comes first (False < True), then enabled, then alphabetical
        return (not is_default, not is_enabled, provider_name)

    filtered_models.sort(key=sort_key)

    return filtered_models


@router.get("/provider-variable-mapping", status_code=200)
async def get_model_provider_mapping() -> dict[str, str]:
    return get_model_provider_variable_mapping()


@router.get("/enabled_providers", status_code=200)
async def get_enabled_providers(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    providers: Annotated[list[str] | None, Query()] = None,
):
    """Get enabled providers for the current user.

    Only providers with valid API keys are marked as enabled. This prevents
    providers from appearing enabled when they have invalid credentials.
    """
    variable_service = get_variable_service()
    try:
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=500,
                detail="Variable service is not an instance of DatabaseVariableService",
            )
        # Get all variables to check which credential variables exist
        all_variables = await variable_service.get_all(user_id=current_user.id, session=session)

        # Get all credential variable names (regardless of default_fields)
        # This includes both env variables and explicitly created model provider credentials
        credential_variable_names = {var.name for var in all_variables if var.type == CREDENTIAL_TYPE}

        if not credential_variable_names:
            return {
                "enabled_providers": [],
                "provider_status": {},
            }

        # Get the provider-variable mapping
        provider_variable_map = get_model_provider_variable_mapping()

        # Build credential_variables dict with objects that have encrypted values
        # VariableRead sets value=None for CREDENTIAL_TYPE (via validator), but _validate_and_get_enabled_providers
        # needs the encrypted value to decrypt and validate. So we create simple objects with the encrypted value.
        credential_variables = {}

        for var_name in credential_variable_names:
            if var_name and var_name in provider_variable_map.values():
                try:
                    # Get the raw Variable object to access the encrypted value
                    variable_obj = await variable_service.get_variable_object(
                        user_id=current_user.id, name=var_name, session=session
                    )
                    if variable_obj and variable_obj.value:
                        # Create a simple object with the encrypted value
                        # _validate_and_get_enabled_providers only needs .value attribute
                        class VarWithValue:
                            def __init__(self, value):
                                self.value = value

                        credential_variables[var_name] = VarWithValue(variable_obj.value)
                except (ValueError, Exception) as e:  # noqa: BLE001
                    # Variable not found or error accessing it - skip
                    logger.debug("Skipping variable %s due to error: %s", var_name, e)
                    continue

        # Use shared helper to validate and get enabled providers
        from lfx.base.models.unified_models import _validate_and_get_enabled_providers

        enabled_providers_set = _validate_and_get_enabled_providers(credential_variables, provider_variable_map)
        enabled_providers = list(enabled_providers_set)

        # Build provider_status dict for all providers
        provider_status = {provider: provider in enabled_providers_set for provider in provider_variable_map}

        result = {
            "enabled_providers": enabled_providers,
            "provider_status": provider_status,
        }

        if providers:
            # Filter enabled_providers and provider_status by requested providers
            filtered_enabled = [p for p in result["enabled_providers"] if p in providers]
            provider_status_dict = result.get("provider_status", {})
            if not isinstance(provider_status_dict, dict):
                provider_status_dict = {}
            filtered_status = {p: v for p, v in provider_status_dict.items() if p in providers}
            return {
                "enabled_providers": filtered_enabled,
                "provider_status": filtered_status,
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get enabled providers for user %s", current_user.id)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve enabled providers. Please try again later.",
        ) from e
    else:
        return result


async def _get_disabled_models(session: DbSession, current_user: CurrentActiveUser) -> set[str]:
    """Helper function to get the set of disabled model IDs."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return set()

    try:
        var = await variable_service.get_variable_object(
            user_id=current_user.id, name=DISABLED_MODELS_VAR, session=session
        )
        if var.value is not None:
            try:
                parsed_value = json.loads(var.value)
                # Validate it's a list of strings
                if not isinstance(parsed_value, list):
                    logger.warning("Invalid disabled models format for user %s: not a list", current_user.id)
                    return set()
                # Ensure all items are strings
                return {str(item) for item in parsed_value if isinstance(item, str)}
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse disabled models for user %s", current_user.id, exc_info=True)
                return set()
    except ValueError:
        # Variable not found, return empty set
        pass
    return set()


async def _get_enabled_models(session: DbSession, current_user: CurrentActiveUser) -> set[str]:
    """Helper function to get the set of explicitly enabled model IDs.

    These are models that were NOT default but were explicitly enabled by the user.
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return set()

    try:
        var = await variable_service.get_variable_object(
            user_id=current_user.id, name=ENABLED_MODELS_VAR, session=session
        )
        if var.value is not None:
            try:
                parsed_value = json.loads(var.value)
                # Validate it's a list of strings
                if not isinstance(parsed_value, list):
                    logger.warning("Invalid enabled models format for user %s: not a list", current_user.id)
                    return set()
                # Ensure all items are strings
                return {str(item) for item in parsed_value if isinstance(item, str)}
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse enabled models for user %s", current_user.id, exc_info=True)
                return set()
    except ValueError:
        # Variable not found, return empty set
        pass
    return set()


def _build_model_default_flags() -> dict[str, bool]:
    """Build a map of model names to their default flag status.

    Returns:
        Dictionary mapping model names to whether they are default models
    """
    all_models_by_provider = get_unified_models_detailed(
        include_unsupported=True,
        include_deprecated=True,
    )

    is_default_model = {}
    for provider_dict in all_models_by_provider:
        for model in provider_dict.get("models", []):
            model_name = model.get("model_name")
            is_default = model.get("metadata", {}).get("default", False)
            is_default_model[model_name] = is_default

    return is_default_model


def _update_model_sets(
    updates: list[ModelStatusUpdate],
    disabled_models: set[str],
    explicitly_enabled_models: set[str],
    is_default_model: dict[str, bool],
) -> None:
    """Update disabled and enabled model sets based on user requests.

    Args:
        updates: List of model status updates from user
        disabled_models: Set of disabled model IDs (modified in place)
        explicitly_enabled_models: Set of explicitly enabled model IDs (modified in place)
        is_default_model: Map of model names to their default flag status
    """
    for update in updates:
        model_is_default = is_default_model.get(update.model_id, False)

        if update.enabled:
            # User wants to enable the model
            disabled_models.discard(update.model_id)
            # If it's not a default model, add to explicitly enabled list
            if not model_is_default:
                explicitly_enabled_models.add(update.model_id)
        else:
            # User wants to disable the model
            disabled_models.add(update.model_id)
            explicitly_enabled_models.discard(update.model_id)


async def _save_model_list_variable(
    variable_service: DatabaseVariableService,
    session: DbSession,
    current_user: CurrentActiveUser,
    var_name: str,
    model_set: set[str],
) -> None:
    """Save or update a model list variable.

    Args:
        variable_service: The database variable service
        session: Database session
        current_user: Current active user
        var_name: Name of the variable to save
        model_set: Set of model names to save

    Raises:
        HTTPException: If there's an error saving the variable
    """
    from langflow.services.database.models.variable.model import VariableUpdate

    models_json = json.dumps(list(model_set))

    try:
        existing_var = await variable_service.get_variable_object(
            user_id=current_user.id, name=var_name, session=session
        )
        if existing_var is None or existing_var.id is None:
            msg = f"Variable {var_name} not found"
            raise ValueError(msg)

        # Update or delete based on whether there are models
        if model_set or var_name == DISABLED_MODELS_VAR:
            # Always update disabled models, even if empty
            # Only update enabled models if non-empty
            await variable_service.update_variable_fields(
                user_id=current_user.id,
                variable_id=existing_var.id,
                variable=VariableUpdate(id=existing_var.id, name=var_name, value=models_json, type=GENERIC_TYPE),
                session=session,
            )
        else:
            # No explicitly enabled models, delete the variable
            await variable_service.delete_variable(user_id=current_user.id, name=var_name, session=session)
    except ValueError:
        # Variable not found, create new one if there are models
        if model_set:
            await variable_service.create_variable(
                user_id=current_user.id,
                name=var_name,
                value=models_json,
                type_=GENERIC_TYPE,
                session=session,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to save model list variable %s for user %s",
            var_name,
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save model configuration. Please try again later.",
        ) from e


@router.get("/enabled_models", status_code=200)
async def get_enabled_models(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    model_names: Annotated[list[str] | None, Query()] = None,
):
    """Get enabled models for the current user."""
    # Get all models - this returns a list of provider dicts with nested models
    all_models_by_provider = get_unified_models_detailed(
        include_unsupported=True,
        include_deprecated=True,
    )

    # Get enabled providers status
    enabled_providers_result = await get_enabled_providers(session=session, current_user=current_user)
    provider_status = enabled_providers_result.get("provider_status", {})

    # Get disabled and explicitly enabled models lists
    disabled_models = await _get_disabled_models(session=session, current_user=current_user)
    explicitly_enabled_models = await _get_enabled_models(session=session, current_user=current_user)

    # Build model status based on provider enablement
    enabled_models: dict[str, dict[str, bool]] = {}

    # Iterate through providers and their models
    for provider_dict in all_models_by_provider:
        provider = provider_dict.get("provider")
        models = provider_dict.get("models", [])

        # Initialize provider dict if not exists
        if provider not in enabled_models:
            enabled_models[provider] = {}

        for model in models:
            model_name = model.get("model_name")
            metadata = model.get("metadata", {})

            # Check if model is deprecated or not supported
            is_deprecated = metadata.get("deprecated", False)
            is_not_supported = metadata.get("not_supported", False)
            is_default = metadata.get("default", False)

            # Model is enabled if:
            # 1. Provider is enabled
            # 2. Model is not deprecated/unsupported
            # 3. Model is either:
            #    - Marked as default (default=True), OR
            #    - Explicitly enabled by user (in explicitly_enabled_models), AND
            #    - NOT explicitly disabled by user (not in disabled_models)
            is_enabled = (
                provider_status.get(provider, False)
                and not is_deprecated
                and not is_not_supported
                and (is_default or model_name in explicitly_enabled_models)
                and model_name not in disabled_models
            )
            # Store model status per provider (true/false)
            enabled_models[provider][model_name] = is_enabled

    result = {
        "enabled_models": enabled_models,
    }

    if model_names:
        # Filter enabled_models by requested models
        filtered_enabled: dict[str, dict[str, bool]] = {}
        for provider, models_dict in enabled_models.items():
            filtered_models = {m: v for m, v in models_dict.items() if m in model_names}
            if filtered_models:
                filtered_enabled[provider] = filtered_models
        return {
            "enabled_models": filtered_enabled,
        }

    return result


@router.post("/enabled_models", status_code=200)
async def update_enabled_models(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    updates: list[ModelStatusUpdate],
):
    """Update enabled status for specific models.

    Accepts a list of model IDs with their desired enabled status.
    This only affects model-level enablement - provider credentials must still be configured.
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        raise HTTPException(
            status_code=500,
            detail="Variable service is not an instance of DatabaseVariableService",
        )

    # Limit batch size to prevent abuse
    if len(updates) > MAX_BATCH_UPDATE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update more than {MAX_BATCH_UPDATE_SIZE} models at once",
        )

    # Get current disabled and explicitly enabled models
    disabled_models = await _get_disabled_models(session=session, current_user=current_user)
    explicitly_enabled_models = await _get_enabled_models(session=session, current_user=current_user)

    # Build map of model names to their default flag
    is_default_model = _build_model_default_flags()

    # Update model sets based on user requests
    _update_model_sets(updates, disabled_models, explicitly_enabled_models, is_default_model)

    # Log the operation for audit trail
    logger.info(
        "User %s updated model status: %d models affected",
        current_user.id,
        len(updates),
    )

    # Save updated model lists
    await _save_model_list_variable(variable_service, session, current_user, DISABLED_MODELS_VAR, disabled_models)
    await _save_model_list_variable(
        variable_service, session, current_user, ENABLED_MODELS_VAR, explicitly_enabled_models
    )

    # Return the updated model status
    return {
        "disabled_models": list(disabled_models),
        "enabled_models": list(explicitly_enabled_models),
    }


class DefaultModelRequest(BaseModel):
    """Request model for setting default model."""

    model_name: str
    provider: str
    model_type: str  # 'language' or 'embedding'

    @field_validator("model_name", "provider")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure strings are non-empty and reasonable length."""
        if not v or not v.strip():
            msg = "Field cannot be empty"
            raise ValueError(msg)
        if len(v) > MAX_STRING_LENGTH:
            msg = f"Field exceeds maximum length of {MAX_STRING_LENGTH} characters"
            raise ValueError(msg)
        return v.strip()

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        """Ensure model_type is valid."""
        if v not in ("language", "embedding"):
            msg = "model_type must be 'language' or 'embedding'"
            raise ValueError(msg)
        return v


@router.get("/default_model", status_code=200)
async def get_default_model(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    model_type: Annotated[str, Query(description="Type of model: 'language' or 'embedding'")] = "language",
):
    """Get the default model for the current user."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return {"default_model": None}

    var_name = DEFAULT_LANGUAGE_MODEL_VAR if model_type == "language" else DEFAULT_EMBEDDING_MODEL_VAR

    try:
        var = await variable_service.get_variable_object(user_id=current_user.id, name=var_name, session=session)
        if var.value:
            try:
                parsed_value = json.loads(var.value)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse default model for user %s", current_user.id, exc_info=True)
                return {"default_model": None}
            else:
                # Validate structure
                if not isinstance(parsed_value, dict) or not all(
                    k in parsed_value for k in ("model_name", "provider", "model_type")
                ):
                    logger.warning("Invalid default model format for user %s", current_user.id)
                    return {"default_model": None}
                return {"default_model": parsed_value}
    except ValueError:
        # Variable not found
        pass
    return {"default_model": None}


@router.post("/default_model", status_code=200)
async def set_default_model(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    request: DefaultModelRequest,
):
    """Set the default model for the current user."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        raise HTTPException(
            status_code=500,
            detail="Variable service is not an instance of DatabaseVariableService",
        )

    var_name = DEFAULT_LANGUAGE_MODEL_VAR if request.model_type == "language" else DEFAULT_EMBEDDING_MODEL_VAR

    # Log the operation for audit trail
    logger.info(
        "User %s setting default %s model to %s (%s)",
        current_user.id,
        request.model_type,
        request.model_name,
        request.provider,
    )

    # Prepare the model data
    model_data = {
        "model_name": request.model_name,
        "provider": request.provider,
        "model_type": request.model_type,
    }
    model_json = json.dumps(model_data)

    # Check if the variable already exists
    try:
        existing_var = await variable_service.get_variable_object(
            user_id=current_user.id, name=var_name, session=session
        )
        if existing_var is None or existing_var.id is None:
            msg = f"Variable {DISABLED_MODELS_VAR} not found"
            raise ValueError(msg)
        # Update existing variable
        from langflow.services.database.models.variable.model import VariableUpdate

        await variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=existing_var.id,
            variable=VariableUpdate(id=existing_var.id, name=var_name, value=model_json, type=GENERIC_TYPE),
            session=session,
        )
    except ValueError:
        # Variable not found, create new one
        await variable_service.create_variable(
            user_id=current_user.id,
            name=var_name,
            value=model_json,
            type_=GENERIC_TYPE,
            session=session,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to set default model for user %s",
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to set default model. Please try again later.",
        ) from e

    return {"default_model": model_data}


@router.delete("/default_model", status_code=200)
async def clear_default_model(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    model_type: Annotated[str, Query(description="Type of model: 'language' or 'embedding'")] = "language",
):
    """Clear the default model for the current user."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        raise HTTPException(
            status_code=500,
            detail="Variable service is not an instance of DatabaseVariableService",
        )

    var_name = DEFAULT_LANGUAGE_MODEL_VAR if model_type == "language" else DEFAULT_EMBEDDING_MODEL_VAR

    # Log the operation for audit trail
    logger.info(
        "User %s clearing default %s model",
        current_user.id,
        model_type,
    )

    # Check if the variable exists and delete it
    try:
        existing_var = await variable_service.get_variable_object(
            user_id=current_user.id, name=var_name, session=session
        )
        await variable_service.delete_variable(user_id=current_user.id, name=existing_var.name, session=session)
    except ValueError:
        # Variable not found, nothing to delete
        pass
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to clear default model for user %s",
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to clear default model. Please try again later.",
        ) from e

    return {"default_model": None}
