"""Provider configuration service."""

import os
import re
from uuid import UUID

from lfx.base.models.model_metadata import CONDITIONAL_LIVE_MODEL_PROVIDERS, LIVE_MODEL_PROVIDERS
from lfx.base.models.model_utils import get_live_models_for_provider
from lfx.base.models.unified_models import (
    get_model_provider_variable_mapping,
    get_provider_required_variable_keys,
    get_unified_models_detailed,
)
from lfx.log.logger import logger
from lfx.utils.secrets import secret_value_to_str
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.services.deps import get_variable_service
from langflow.services.variable.service import DatabaseVariableService, VariableService

# Preferred providers in order of priority
PREFERRED_PROVIDERS = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"]


async def get_enabled_providers_for_user(
    user_id: UUID | str,
    session: AsyncSession,
) -> tuple[list[str], dict[str, bool]]:
    """Get enabled providers for a user.

    Returns:
        Tuple of (enabled_providers list, provider_status dict)
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return [], {}

    all_variables = await variable_service.get_all(user_id=user_id, session=session)
    # Include all variable types (credentials and regular variables)
    # so providers like Ollama (which use non-secret variables) are detected
    all_variable_names = {var.name for var in all_variables}

    provider_variable_map = get_model_provider_variable_mapping()

    enabled_providers = []
    provider_status = {}

    for provider in provider_variable_map:
        # Check if ALL required variables for this provider are present
        # in either database variables or environment variables
        required_keys = get_provider_required_variable_keys(provider)
        is_enabled = all(key in all_variable_names or os.getenv(key) for key in required_keys)

        provider_status[provider] = is_enabled
        if is_enabled:
            enabled_providers.append(provider)

    return enabled_providers, provider_status


async def check_api_key(
    variable_service: VariableService,
    user_id: UUID | str,
    key_name: str,
    session: AsyncSession,
) -> str | None:
    """Check if an API key is available from global variables or environment."""
    api_key = None

    try:
        api_key = await variable_service.get_variable(user_id, key_name, "", session)
    except ValueError:
        logger.debug(f"{key_name} not found in global variables, checking environment")

    api_key = secret_value_to_str(api_key)
    if not api_key:
        api_key = os.getenv(key_name)

    return api_key


def _is_cloud_model(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith((":cloud", "-cloud"))


_SMALL_PARAM_PATTERN = re.compile(r"(?<![\d])([1-9]|1[0-3])b\b", re.IGNORECASE)
_LARGE_PARAM_PATTERN = re.compile(r"(?<![\d.])(1[4-9]|[2-9]\d|\d{3,})b\b", re.IGNORECASE)
_SMALL_DEFAULT_BASE_NAMES = frozenset(
    {
        "llama2",
        "llama3",
        "llama3.1",
        "llama3.2",
        "llama3-groq-tool-use",
        "mistral",
        "mistral-nemo",
        "qwen",
        "qwen2",
        "qwen2.5",
        "qwen2.5-coder",
        "qwen3",
        "gemma",
        "gemma2",
        "gemma3",
        "smollm2",
        "hermes3",
        "granite3-dense",
        "granite3.1-dense",
        "granite3-moe",
        "aya-expanse",
        "cogito",
    }
)


def is_probably_small_model(model_name: str | None) -> bool:
    """True for open-weights models ≤ 13B (by param count or known small-default tag).

    Deliberately narrower than the frontend strength hint: only explicit
    size signals count, so hosted "mini"-style models (which drive tools
    fine) are never flagged. Verified live 2026-06-12: ≤ 13B models emit
    zero native tool calls under the assistant prompt, so retrying them
    on a no-action build is predictably futile.
    """
    if not model_name:
        return False
    name = model_name.lower()
    if _LARGE_PARAM_PATTERN.search(name):
        return False
    if name.split(":")[0] in _SMALL_DEFAULT_BASE_NAMES:
        return True
    return bool(_SMALL_PARAM_PATTERN.search(name))


def list_installed_tool_calling_models(provider: str, user_id: UUID | str | None) -> list[str]:
    """Names of the live (installed) tool-calling LLMs on a live provider.

    Local models come first: Ollama ``:cloud`` models 403 without an
    ollama.com subscription, so they must never win the default slot when
    a locally runnable model exists.

    Returns [] when the provider is catalog-only, no user is available to
    resolve credentials, or the live fetch fails — callers then keep the
    static catalog behavior.
    """
    if not user_id or provider not in {*LIVE_MODEL_PROVIDERS, *CONDITIONAL_LIVE_MODEL_PROVIDERS}:
        return []
    try:
        live_models = get_live_models_for_provider(user_id, provider, "llm")
    except Exception as exc:  # noqa: BLE001 — fail-open: any fetch error degrades to catalog behavior
        logger.debug(f"Live model fetch failed for provider={provider}: {exc}")
        return []
    names = [model["name"] for model in live_models if model.get("name") and model.get("tool_calling", True)]
    return sorted(names, key=_is_cloud_model)


def get_default_model(provider: str, user_id: UUID | str | None = None) -> str | None:
    """Get the default model for a provider.

    For live providers (Ollama, WatsonX, OpenRouter) with a ``user_id``,
    the default must be a model that is actually installed/available —
    the static catalog default may not exist on the user's server.
    """
    catalog_default = None
    models_by_provider = get_unified_models_detailed(
        providers=[provider],
        include_unsupported=False,
        include_deprecated=False,
        only_defaults=True,
    )
    for provider_dict in models_by_provider:
        models = provider_dict.get("models", [])
        if models:
            catalog_default = models[0].get("model_name")
            break

    installed = list_installed_tool_calling_models(provider, user_id)
    if installed:
        return catalog_default if catalog_default in installed else installed[0]
    return catalog_default


def get_provider_model_candidates(provider: str, user_id: UUID | str | None = None) -> list[str]:
    """Return the ordered model candidates the assistant may try on this provider.

    The catalog's "default" model isn't guaranteed to be callable for the
    requesting account (e.g. OpenAI 403 ``model_not_found`` because the
    project lacks access to a newly-released default — PR-12575 Bug 1).
    When the chosen model fails the streamer walks down this list, so
    order matters: the catalog default is first (kept for backward
    compatibility with the existing default-picking logic), then every
    other non-deprecated / non-unsupported language model on the provider
    in catalog order.
    """
    if not provider:
        return []

    installed = list_installed_tool_calling_models(provider, user_id)
    if installed:
        return installed

    models_by_provider = get_unified_models_detailed(
        providers=[provider],
        include_unsupported=False,
        include_deprecated=False,
        model_type="llm",
    )

    default = get_default_model(provider)
    seen: set[str] = set()
    ordered: list[str] = []
    if default:
        ordered.append(default)
        seen.add(default)

    for provider_dict in models_by_provider:
        for model in provider_dict.get("models", []):
            name = model.get("model_name")
            if not name or name in seen:
                continue
            ordered.append(name)
            seen.add(name)

    return ordered
