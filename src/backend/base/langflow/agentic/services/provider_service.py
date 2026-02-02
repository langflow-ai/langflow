"""Provider configuration service."""

import os
from uuid import UUID

from lfx.base.models.unified_models import get_model_provider_variable_mapping
from lfx.log.logger import logger
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import CREDENTIAL_TYPE
from langflow.services.variable.service import DatabaseVariableService, VariableService

# Preferred providers in order of priority
PREFERRED_PROVIDERS = ["Anthropic", "OpenAI", "Google Generative AI", "Groq"]

# Default models per provider
DEFAULT_MODELS: dict[str, str] = {
    "Anthropic": "claude-sonnet-4-5-20250514",
    "OpenAI": "gpt-5.2",
    "Google Generative AI": "gemini-2.0-flash",
    "Groq": "llama-3.3-70b-versatile",
}


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
    credential_names = {var.name for var in all_variables if var.type == CREDENTIAL_TYPE}

    if not credential_names:
        return [], {}

    provider_variable_map = get_model_provider_variable_mapping()

    enabled_providers = []
    provider_status = {}

    for provider, var_name in provider_variable_map.items():
        is_enabled = var_name in credential_names
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

    if not api_key:
        api_key = os.getenv(key_name)

    return api_key


def get_default_provider(enabled_providers: list[str]) -> str | None:
    """Get the default provider from enabled providers based on priority."""
    for preferred in PREFERRED_PROVIDERS:
        if preferred in enabled_providers:
            return preferred
    return enabled_providers[0] if enabled_providers else None


def get_default_model(provider: str) -> str | None:
    """Get the default model for a provider."""
    return DEFAULT_MODELS.get(provider)
