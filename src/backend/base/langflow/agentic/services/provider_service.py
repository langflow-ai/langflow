"""Provider configuration service."""

import os
from uuid import UUID

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


def get_default_model(provider: str) -> str | None:
    """Get the default model for a provider dynamically from the unified models registry."""
    models_by_provider = get_unified_models_detailed(
        providers=[provider],
        include_unsupported=False,
        include_deprecated=False,
        only_defaults=True,
    )
    for provider_dict in models_by_provider:
        models = provider_dict.get("models", [])
        if models:
            return models[0].get("model_name")
    return None


def get_provider_model_candidates(provider: str) -> list[str]:
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
