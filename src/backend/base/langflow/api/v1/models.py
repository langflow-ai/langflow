from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_model_providers,
    get_unified_models_detailed,
)

from langflow.api.utils import CurrentActiveUser, DbSession
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
    provider: Annotated[list[str] | None, Query(description="Repeat to include multiple providers")] = None,
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

    # Get filtered models
    filtered_models = get_unified_models_detailed(
        model_name=model_name,
        include_unsupported=include_unsupported,
        model_type=model_type,
        **metadata_filters,
    )
    if selected_providers:
        filtered_models = [m for m in filtered_models if m.get("provider") in selected_providers]
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
        all_variables = await variable_service.get_all(
            user_id=current_user.id, session=session
        )

        # Get all credential variable names (regardless of default_fields)
        # This includes both env variables and explicitly created model provider credentials
        credential_names = {
            var.name for var in all_variables
            if var.type == CREDENTIAL_TYPE
        }

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
