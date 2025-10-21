from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_model_providers,
    get_unified_models_detailed,
)
from langflow.services.deps import get_variable_service
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/models", tags=["Models"])


@router.get("/providers", status_code=200)
async def list_model_providers() -> list[str]:
    """Return available model providers."""
    return get_model_providers()


@router.get("", status_code=200)
async def list_models(
    *,
    providers: Annotated[
        list[str] | None, Query(description="Repeat to include multiple providers", alias="providers")
    ] = None,
    model_name: str | None = None,
    model_type: str | None = None,
    include_unsupported: bool = False,
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

    Pass providers as repeated query params, e.g. `?providers=OpenAI&providers=Anthropic`.
    """
    selected_providers: list[str] | None = providers  # Build metadata filters dict excluding None values
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

    # Get filtered models
    filtered_models = get_unified_models_detailed(
        providers=selected_providers,
        model_name=model_name,
        include_unsupported=include_unsupported,
        model_type=model_type,
        **metadata_filters,
    )

    # Add enabled status to each provider
    for provider_dict in filtered_models:
        provider_dict["is_enabled"] = provider_status.get(provider_dict.get("provider"), False)

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
    from langflow.base.models.unified_models import get_model_provider_variable_mapping
    from langflow.services.variable.constants import CATEGORY_LLM

    if providers is None:
        providers = []
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        msg = "Variable service is not an instance of DatabaseVariableService"
        raise TypeError(msg)
    try:
        # Get all LLM category variables for the user
        variables = await variable_service.get_by_category(
            user_id=current_user.id, category=CATEGORY_LLM, session=session
        )
        if not variables:
            return {
                "enabled_providers": [],
                "provider_status": {},
            }
        variable_names = {variable.name for variable in variables if variable}

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
            filtered_status = {p: v for p, v in result["provider_status"].items() if p in providers}
            return {
                "enabled_providers": filtered_enabled,
                "provider_status": filtered_status,
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    else:
        return result
