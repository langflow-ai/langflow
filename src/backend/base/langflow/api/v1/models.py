from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from langflow.base.models.unified_models import get_model_providers, get_unified_models_detailed

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
):
    """Return model catalog filtered by query parameters.

    Pass providers as repeated query params, e.g. `?providers=OpenAI&providers=Anthropic`.
    """
    selected_providers: list[str] | None = providers

    metadata_filters = {
        "tool_calling": tool_calling,
        "reasoning": reasoning,
        "search": search,
        "preview": preview,
        "deprecated": deprecated,
        "not_supported": not_supported,
    }
    metadata_filters = {k: v for k, v in metadata_filters.items() if v is not None}

    return get_unified_models_detailed(
        providers=selected_providers,
        model_name=model_name,
        include_unsupported=include_unsupported,
        model_type=model_type,
        **metadata_filters,
    )
