"""Langflow Assistant API router.

This module provides the HTTP endpoints for the Langflow Assistant.
All business logic is delegated to service modules.
"""

import asyncio
import contextlib
import json
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from lfx.base.models.provider_registry import is_api_key_optional
from lfx.base.models.unified_models import (
    get_all_variables_for_provider,
    get_provider_required_variable_keys,
    get_provider_secret_variable_key,
    get_unified_models_detailed,
)
from lfx.log.logger import logger
from lfx.services.deps import get_settings_service
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.agentic.api.deps import require_agentic_experience
from langflow.agentic.api.schemas import AssistantRequest, HeadlessAssistantRequest
from langflow.agentic.helpers.sse import format_complete_event, format_error_event
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
    PREFERRED_PROVIDERS,
    build_live_only_provider_entries,
    get_default_model,
    get_enabled_providers_for_user,
    list_installed_tool_calling_models,
)
from langflow.api.utils.core import CurrentActiveUser, DbSession

router = APIRouter(prefix="/agentic", tags=["Agentic"])


@dataclass(frozen=True)
class _AssistantContext:
    """Resolved provider, model, and execution context for assistant endpoints."""

    provider: str
    model_name: str
    api_key_name: str | None
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

    api_key_name = get_provider_secret_variable_key(provider)
    if not api_key_name and not is_api_key_optional(provider):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    model_name = request.model_name or get_default_model(provider, user_id=user_id) or ""

    # Get all configured variables for the provider
    provider_vars = get_all_variables_for_provider(user_id, provider)

    # Validate all required variables are present
    required_keys = get_provider_required_variable_keys(provider)
    missing_keys = [key for key in required_keys if not provider_vars.get(key)]

    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Missing required configuration for {provider}: {', '.join(missing_keys)}. "
                "Please configure these in Settings > Model Providers."
            ),
        )

    global_vars: dict[str, str] = {
        "USER_ID": str(user_id),
        "FLOW_ID": request.flow_id,
        "MODEL_NAME": model_name,
        "PROVIDER": provider,
    }

    # Seeded here (not per-endpoint) so /assist and /execute/{flow_name}
    # honor the budget the same way /assist/stream does.
    if request.iterations_limit is not None:
        global_vars["ITERATIONS_LIMIT"] = str(request.iterations_limit)

    # Inject all provider variables into the global context
    global_vars.update(provider_vars)

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


async def _validate_flow_access(flow_id: str | None, user_id: UUID, session: AsyncSession) -> None:
    """Reject an unknown or not-owned flow_id before the model is invoked.

    A missing flow_id is allowed (the assistant runs with no canvas context).
    A supplied id must reference a flow the caller can access, mirroring the
    per-user 404 of the /run and webhook endpoints; not-found and cross-user
    both surface 404 so a flow's existence is not leaked by id.
    """
    if not flow_id:
        return

    from langflow.services.database.models.flow import Flow

    try:
        flow_uuid = UUID(flow_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid flow_id: not a valid UUID.") from exc

    flow = await session.get(Flow, flow_uuid)
    if flow is None or (flow.user_id is not None and str(flow.user_id) != str(user_id)):
        raise HTTPException(status_code=404, detail="Flow not found.")


@router.post("/execute/{flow_name}", dependencies=[Depends(require_agentic_experience)])
async def execute_named_flow(
    flow_name: str,
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Execute a named flow from the flows directory.

    Named assistant flows embed an Agent that needs provider/model/api-key
    context. Resolving it here (instead of running the raw file) turns a
    silent 500 into a successful run, or a clear 4xx when no provider is set.
    """
    ctx = await _resolve_assistant_context(request, current_user.id, session)

    global_vars = dict(ctx.global_vars)
    if request.component_id:
        global_vars["COMPONENT_ID"] = request.component_id
    if request.field_name:
        global_vars["FIELD_NAME"] = request.field_name

    return await execute_flow_file(
        flow_filename=f"{flow_name}.json",
        input_value=request.input_value,
        global_variables=global_vars,
        verbose=True,
        user_id=str(current_user.id),
        session_id=ctx.session_id,
        provider=ctx.provider,
        model_name=ctx.model_name,
        api_key_var=ctx.api_key_name,
    )


@router.get("/check-config")
async def check_assistant_config(
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Check if the Langflow Assistant is properly configured.

    Returns available providers with their configured status and available models, plus
    ``enabled``: whether ``agentic_experience`` gates the assistant off. Provider config and
    the feature gate are independent failure modes -- without ``enabled`` a caller cannot tell
    "no provider connected" from "feature disabled", and every /assist call 404s with no way
    to explain why. This probe stays ungated so that distinction survives the gate.
    """
    user_id = current_user.id
    enabled = get_settings_service().settings.agentic_experience
    enabled_providers, _ = await get_enabled_providers_for_user(user_id, session)

    all_providers = []

    if enabled_providers:
        models_by_provider = get_unified_models_detailed(
            providers=enabled_providers,
            include_unsupported=False,
            include_deprecated=False,
            model_type="llm",
        )
        for provider_dict in models_by_provider:
            provider_name = provider_dict.get("provider")
            if not provider_name:
                continue
            installed = list_installed_tool_calling_models(provider_name, user_id)
            if installed:
                provider_dict["models"] = [{"model_name": name, "metadata": {}} for name in installed]
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

            default_model = get_default_model(provider_name)
            if model_list and default_model not in {m["name"] for m in model_list}:
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

    # Live providers with an all-deprecated static catalog (e.g. IBM WatsonX) are dropped above
    # before their live fetch runs; re-add them from live tool-calling models.
    if enabled_providers:
        all_providers.extend(
            build_live_only_provider_entries(
                enabled_providers,
                {p["name"] for p in all_providers},
                user_id,
            )
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
        "enabled": enabled,
        "configured": len(enabled_providers) > 0,
        "configured_providers": enabled_providers,
        "providers": all_providers,
        "default_provider": default_provider,
        "default_model": default_model,
    }


@router.post("/assist", dependencies=[Depends(require_agentic_experience)])
async def assist(
    request: AssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> dict:
    """Chat with the Langflow Assistant."""
    await _validate_flow_access(request.flow_id, current_user.id, session)
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


@router.post("/assist/stream", dependencies=[Depends(require_agentic_experience)])
async def assist_stream(
    request: AssistantRequest,
    http_request: Request,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> StreamingResponse:
    """Chat with the Langflow Assistant with streaming progress updates."""
    await _validate_flow_access(request.flow_id, current_user.id, session)
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
            is_disconnected=http_request.is_disconnected,
            is_superuser=bool(current_user.is_superuser),
            history_limit=request.history_limit,
            iterations_limit=request.iterations_limit,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.post("/assist/run", dependencies=[Depends(require_agentic_experience)])
async def assist_headless(
    request: HeadlessAssistantRequest,
    current_user: CurrentActiveUser,
    session: DbSession,
) -> StreamingResponse:
    """Run the assistant headlessly: canvas changes are applied, not proposed.

    ``/assist/stream`` leaves a canvas change as a proposal the user approves in
    a UI card. A headless caller (the MCP ``run_assistant`` tool) has no card, so
    its edits would be silently dropped — this route persists them through
    ``run_assistant_and_persist`` and streams the same ``progress`` events,
    ending in ``complete`` (or ``error``).
    """
    # Local import: assistant_runner imports this module's helpers, so a top-level
    # import here would close the cycle at startup.
    from langflow.agentic.utils.assistant_runner import run_assistant_and_persist

    if request.flow_id:
        await _validate_flow_access(request.flow_id, current_user.id, session)

    async def _stream() -> AsyncIterator[str]:
        queue: asyncio.Queue[dict | None] = asyncio.Queue()

        async def on_progress(event: dict) -> None:
            await queue.put(event)

        async def _drive() -> dict:
            try:
                return await run_assistant_and_persist(
                    session=session,
                    user_id=current_user.id,
                    instruction=request.instruction,
                    flow_id=request.flow_id,
                    provider=request.provider,
                    model_name=request.model_name,
                    session_id=request.session_id,
                    on_progress=on_progress,
                )
            finally:
                await queue.put(None)

        task = asyncio.create_task(_drive())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                # Re-emit the assistant's own progress event verbatim: it already carries
                # the step/attempt shape the SSE formatter would rebuild.
                yield f"data: {json.dumps(event)}\n\n"
            try:
                result = await task
            except Exception as exc:  # noqa: BLE001
                logger.exception("Headless assistant run failed")
                yield format_error_event(str(exc))
                return
            yield format_complete_event(result)
        finally:
            # Client disconnect cancels this generator mid-yield; without this the
            # orphaned task keeps writing to the DB on a tearing-down session.
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
