from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_model_providers,
    get_unified_models_detailed,
)
from pydantic import BaseModel

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/models", tags=["Models"])

# Variable names for storing disabled models and default models
DISABLED_MODELS_VAR = "__disabled_models__"
DEFAULT_LANGUAGE_MODEL_VAR = "__default_language_model__"
DEFAULT_EMBEDDING_MODEL_VAR = "__default_embedding_model__"


class ModelStatusUpdate(BaseModel):
    """Request model for updating model enabled status."""

    provider: str
    model_id: str
    enabled: bool


@router.get("/providers", status_code=200)
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
        except Exception:
            pass  # If we can't get default model, just continue without it

    # Get filtered models
    filtered_models = get_unified_models_detailed(
        model_name=model_name,
        include_unsupported=include_unsupported,
        include_deprecated=include_deprecated,
        model_type=model_type,
        **metadata_filters,
    )
    if selected_providers:
        filtered_models = [m for m in filtered_models if m.get("provider") in selected_providers]
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
    """Get enabled providers for the current user."""
    from lfx.base.models.unified_models import get_model_provider_variable_mapping

    from langflow.services.variable.constants import CREDENTIAL_TYPE

    if providers is None:
        providers = []
    variable_service = get_variable_service()
    try:
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=500,
                detail="Variable service is not an instance of DatabaseVariableService",
            )
        # Get all credential variables for the user
        all_variables = await variable_service.get_all(user_id=current_user.id, session=session)

        # Get all credential variable names (regardless of default_fields)
        # This includes both env variables and explicitly created model provider credentials
        credential_names = {var.name for var in all_variables if var.type == CREDENTIAL_TYPE}

        if not credential_names:
            return {
                "enabled_providers": [],
                "provider_status": {},
            }
        variable_names = credential_names

        # Get the provider-variable mapping
        provider_variable_map = get_model_provider_variable_mapping()

        enabled_providers = []
        provider_status = {}

        for provider, var_name in provider_variable_map.items():
            is_enabled = var_name in variable_names
            provider_status[provider] = is_enabled
            if is_enabled:
                enabled_providers.append(provider)

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return result


async def _get_disabled_models(session: DbSession, current_user: CurrentActiveUser) -> set[str]:
    """Helper function to get the set of disabled model IDs."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return set()

    all_variables = await variable_service.get_all(user_id=current_user.id, session=session)
    for var in all_variables:
        if var.name == DISABLED_MODELS_VAR and var.value is not None:
            try:
                return set(json.loads(var.value))
            except (json.JSONDecodeError, TypeError):
                return set()
    return set()


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

    # Get disabled models list
    disabled_models = await _get_disabled_models(session=session, current_user=current_user)

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

            # Model is enabled if:
            # 1. Provider is enabled
            # 2. Model is not deprecated/unsupported
            # 3. Model is not in the disabled list
            is_enabled = (
                provider_status.get(provider, False)
                and not is_deprecated
                and not is_not_supported
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

    # Get current disabled models
    disabled_models = await _get_disabled_models(session=session, current_user=current_user)

    # Update disabled models based on the request
    for update in updates:
        if update.enabled:
            # Remove from disabled list (enable the model)
            disabled_models.discard(update.model_id)
        else:
            # Add to disabled list (disable the model)
            disabled_models.add(update.model_id)

    # Save updated disabled models list
    disabled_models_json = json.dumps(list(disabled_models))

    # Check if the variable already exists
    all_variables = await variable_service.get_all(user_id=current_user.id, session=session)
    existing_var = next((var for var in all_variables if var.name == DISABLED_MODELS_VAR), None)

    try:
        if existing_var:
            # Update existing variable
            from langflow.services.database.models.variable.model import VariableUpdate

            await variable_service.update_variable_fields(
                user_id=current_user.id,
                variable_id=existing_var.id,
                variable=VariableUpdate(
                    id=existing_var.id, name=DISABLED_MODELS_VAR, value=disabled_models_json, type=GENERIC_TYPE
                ),
                session=session,
            )
        else:
            # Create new variable
            await variable_service.create_variable(
                user_id=current_user.id,
                name=DISABLED_MODELS_VAR,
                value=disabled_models_json,
                type_=GENERIC_TYPE,
                session=session,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Return the updated disabled models list
    return {"disabled_models": list(disabled_models)}


class DefaultModelRequest(BaseModel):
    """Request model for setting default model."""

    model_name: str
    provider: str
    model_type: str  # 'language' or 'embedding'


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

    all_variables = await variable_service.get_all(user_id=current_user.id, session=session)
    for var in all_variables:
        if var.name == var_name and var.value:
            try:
                return {"default_model": json.loads(var.value)}
            except (json.JSONDecodeError, TypeError):
                return {"default_model": None}
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

    # Prepare the model data
    model_data = {
        "model_name": request.model_name,
        "provider": request.provider,
        "model_type": request.model_type,
    }
    model_json = json.dumps(model_data)

    # Check if the variable already exists
    all_variables = await variable_service.get_all(user_id=current_user.id, session=session)
    existing_var = next((var for var in all_variables if var.name == var_name), None)

    try:
        if existing_var:
            # Update existing variable
            from langflow.services.database.models.variable.model import VariableUpdate

            await variable_service.update_variable_fields(
                user_id=current_user.id,
                variable_id=existing_var.id,
                variable=VariableUpdate(id=existing_var.id, name=var_name, value=model_json, type=GENERIC_TYPE),
                session=session,
            )
        else:
            # Create new variable
            await variable_service.create_variable(
                user_id=current_user.id,
                name=var_name,
                value=model_json,
                type_=GENERIC_TYPE,
                session=session,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

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

    # Check if the variable exists
    all_variables = await variable_service.get_all(user_id=current_user.id, session=session)
    existing_var = next((var for var in all_variables if var.name == var_name), None)

    if existing_var and existing_var.name:
        try:
            await variable_service.delete_variable(user_id=current_user.id, name=existing_var.name, session=session)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    return {"default_model": None}
