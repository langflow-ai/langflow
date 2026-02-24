"""Langflow Assistant API router.

This module provides the HTTP endpoints for the Langflow Assistant.
All business logic is delegated to service modules.
"""

import uuid
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_unified_models_detailed,
)
from lfx.log.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.agentic.api.schemas import AssistantRequest
from langflow.agentic.services.assistant_service import (
    execute_flow_with_validation,
    execute_flow_with_validation_streaming,
)
from langflow.agentic.services.flow_executor import execute_flow_file
from langflow.agentic.services.flow_types import (
    LANGFLOW_ASSISTANT_FLOW,
    MAX_VALIDATION_RETRIES,
)
from langflow.agentic.services.provider_service import (
    DEFAULT_MODELS,
    PREFERRED_PROVIDERS,
    check_api_key,
    get_enabled_providers_for_user,
)
from langflow.api.utils.core import CurrentActiveUser, DbSession
from langflow.services.deps import get_variable_service

router = APIRouter(prefix="/agentic", tags=["Agentic"])


@dataclass(frozen=True)
class _AssistantContext:
    """Resolved provider, model, and execution context for assistant endpoints."""

    provider: str
    model_name: str
    api_key_name: str
    session_id: str
    global_vars: dict[str, str]
    max_retries: int


async def _resolve_assistant_context(
    request: AssistantRequest,
    user_id: UUID,
    session: AsyncSession,
) -> _AssistantContext:
    """Resolve provider, model, API key, and build execution context.

    Raises:
        HTTPException: If provider is not configured or API key is missing.
    """
    provider_variable_map = get_model_provider_variable_mapping()
    enabled_providers, _ = await get_enabled_providers_for_user(user_id, session)

    if not enabled_providers:
        raise HTTPException(
            status_code=400,
            detail="No model provider is configured. Please configure at least one model provider in Settings.",
        )

    provider = request.provider
    if not provider:
        for preferred in PREFERRED_PROVIDERS:
            if preferred in enabled_providers:
                provider = preferred
                break
        if not provider:
            provider = enabled_providers[0]

    if provider not in enabled_providers:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{provider}' is not configured. Available providers: {enabled_providers}",
        )

    api_key_name = provider_variable_map.get(provider)
    if not api_key_name:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    model_name = request.model_name or DEFAULT_MODELS.get(provider) or ""

    variable_service = get_variable_service()
    api_key = await check_api_key(variable_service, user_id, api_key_name, session)

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{api_key_name} is required for the Langflow Assistant with {provider}. "
                "Please configure it in Settings > Model Providers."
            ),
        )

    global_vars: dict[str, str] = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
        api_key_name: api_key,
        "MODEL_NAME": model_name,
        "PROVIDER": provider,
    }

    session_id = request.session_id or str(uuid.uuid4())
    max_retries = request.max_retries if request.max_retries is not None else MAX_VALIDATION_RETRIES

    return _AssistantContext(
        provider=provider,
        model_name=model_name,
        api_key_name=api_key_name,
        session_id=session_id,
        global_vars=global_vars,
        max_retries=max_retries,
    )


@router.post("/execute/{flow_name}")
async def execute_named_flow(
    flow_name: str,
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Execute a named flow from the flows directory."""
    variable_service = get_variable_service()
    user_id = current_user.id

    global_vars = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
    }

    if request.component_id:
        global_vars["COMPONENT_ID"] = request.component_id
    if request.field_name:
        global_vars["FIELD_NAME"] = request.field_name

    try:
        openai_key = await variable_service.get_variable(user_id, "OPENAI_API_KEY", "", session)
        global_vars["OPENAI_API_KEY"] = openai_key
    except (ValueError, HTTPException):
        logger.debug("OPENAI_API_KEY not configured, continuing without it")

    flow_filename = f"{flow_name}.json"
    # Generate unique session_id per request to isolate memory
    session_id = str(uuid.uuid4())

    return await execute_flow_file(
        flow_filename=flow_filename,
        input_value=request.input_value,
        global_variables=global_vars,
        verbose=True,
        session_id=session_id,
    )


@router.get("/check-config")
async def check_assistant_config(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Check if the Langflow Assistant is properly configured.

    Returns available providers with their configured status and available models.
    """
    user_id = current_user.id
    enabled_providers, _ = await get_enabled_providers_for_user(user_id, session)

    all_providers = []

    if enabled_providers:
        models_by_provider = get_unified_models_detailed(
            providers=enabled_providers,
            include_unsupported=False,
            include_deprecated=False,
            model_type="language",
        )

        for provider_dict in models_by_provider:
            provider_name = provider_dict.get("provider")
            models = provider_dict.get("models", [])

            model_list = []
            for model in models:
                model_name = model.get("model_name")
                display_name = model.get("display_name", model_name)
                metadata = model.get("metadata", {})

                is_deprecated = metadata.get("deprecated", False)
                is_not_supported = metadata.get("not_supported", False)

                if not is_deprecated and not is_not_supported:
                    model_list.append(
                        {
                            "name": model_name,
                            "display_name": display_name,
                        }
                    )

            default_model = DEFAULT_MODELS.get(provider_name)
            if not default_model and model_list:
                default_model = model_list[0]["name"]

            if model_list:
                all_providers.append(
                    {
                        "name": provider_name,
                        "configured": True,
                        "default_model": default_model,
                        "models": model_list,
                    }
                )

    default_provider = None
    default_model = None

    providers_with_models = [p["name"] for p in all_providers]

    for preferred in PREFERRED_PROVIDERS:
        if preferred in providers_with_models:
            default_provider = preferred
            for p in all_providers:
                if p["name"] == preferred:
                    default_model = p["default_model"]
                    break
            break

    if not default_provider and all_providers:
        default_provider = all_providers[0]["name"]
        default_model = all_providers[0]["default_model"]

    return {
        "configured": len(enabled_providers) > 0,
        "configured_providers": enabled_providers,
        "providers": all_providers,
        "default_provider": default_provider,
        "default_model": default_model,
    }


@router.post("/assist")
async def assist(
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Chat with the Langflow Assistant."""
    ctx = await _resolve_assistant_context(request, current_user.id, session)

    logger.info(f"Executing {LANGFLOW_ASSISTANT_FLOW} with {ctx.provider}/{ctx.model_name}")

    return await execute_flow_with_validation(
        flow_filename=LANGFLOW_ASSISTANT_FLOW,
        input_value=request.input_value or "",
        global_variables=ctx.global_vars,
        max_retries=ctx.max_retries,
        user_id=str(current_user.id),
        session_id=ctx.session_id,
        provider=ctx.provider,
        model_name=ctx.model_name,
        api_key_var=ctx.api_key_name,
    )


@router.post("/assist/stream")
async def assist_stream(
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> StreamingResponse:
    """Chat with the Langflow Assistant with streaming progress updates."""
    ctx = await _resolve_assistant_context(request, current_user.id, session)

    return StreamingResponse(
        execute_flow_with_validation_streaming(
            flow_filename=LANGFLOW_ASSISTANT_FLOW,
            input_value=request.input_value or "",
            global_variables=ctx.global_vars,
            max_retries=ctx.max_retries,
            user_id=str(current_user.id),
            session_id=ctx.session_id,
            provider=ctx.provider,
            model_name=ctx.model_name,
            api_key_var=ctx.api_key_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
