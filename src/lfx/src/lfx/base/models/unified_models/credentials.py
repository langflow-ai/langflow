"""Credential resolution and provider validation helpers."""

from __future__ import annotations

import contextlib
import json
import os
import re
from typing import Any
from uuid import UUID

from lfx.log.logger import logger
from lfx.services.deps import get_variable_service, session_scope
from lfx.utils.async_helpers import run_until_complete

from .provider_queries import (
    get_model_provider_variable_mapping,
    get_provider_all_variables,
)


def get_api_key_for_provider(user_id: UUID | str | None, provider: str, api_key: str | None = None) -> str | None:
    """Get API key from component input or global variables.

    When api_key is set to an environment variable name (e.g. ANTHROPIC_API_KEY),
    that name is resolved from os.environ or global variables so imported flows
    can reference credentials without storing the raw key.
    """

    # Resolve variable name (canonical or custom e.g. MY_OPENAI_API_KEY) from env or global vars
    def _resolve_var_name(var_name: str) -> str | None:
        env_value = os.environ.get(var_name)
        if env_value and env_value.strip():
            return env_value.strip()
        if user_id and not (isinstance(user_id, str) and user_id == "None"):

            async def _get_by_var_name():
                async with session_scope() as session:
                    variable_service = get_variable_service()
                    if variable_service is None:
                        return None
                    try:
                        return await variable_service.get_variable(
                            user_id=(UUID(user_id) if isinstance(user_id, str) else user_id),
                            name=var_name,
                            field="",
                            session=session,
                        )
                    except ValueError:
                        return None

            value = run_until_complete(_get_by_var_name())
            if value and str(value).strip():
                return str(value).strip()
        return None

    if api_key and api_key.strip():
        var_name = api_key.strip()
        # Names that look like env/global variables (e.g. MY_OPENAI_API_KEY): resolve from env/DB
        if var_name.replace("_", "").isalnum() and var_name[0].isalpha():
            resolved = _resolve_var_name(var_name)
            if resolved:
                return resolved
            # Unresolved variable name: don't use as literal key
            if re.match(r"^[A-Z][A-Z0-9_]*$", var_name):
                return None
        # Literal API key (e.g. sk-...)
        return var_name

    # If no user_id or user_id is the string "None", we can't look up global variables
    if user_id is None or (isinstance(user_id, str) and user_id == "None"):
        return None

    # Get primary variable (first required secret) from provider metadata
    provider_variable_map = get_model_provider_variable_mapping()
    variable_name = provider_variable_map.get(provider)
    if not variable_name:
        return None

    # Try to get from global variables
    async def _get_variable():
        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return None
            return await variable_service.get_variable(
                user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                name=variable_name,
                field="",
                session=session,
            )

    return run_until_complete(_get_variable())


def get_all_variables_for_provider(user_id: UUID | str | None, provider: str) -> dict[str, str]:
    """Get all configured variables for a provider from database or environment."""
    result: dict[str, str] = {}

    # Get all variable definitions for this provider
    provider_vars = get_provider_all_variables(provider)
    if not provider_vars:
        return result

    # If no user_id, only check environment variables
    if user_id is None or (isinstance(user_id, str) and user_id == "None"):
        for var_info in provider_vars:
            var_key = var_info.get("variable_key")
            if var_key:
                env_value = os.environ.get(var_key)
                if env_value and env_value.strip():
                    result[var_key] = env_value
        return result

    # Try to get from global variables (database)
    async def _get_all_variables():
        async with session_scope() as session:
            variable_service = get_variable_service()
            if variable_service is None:
                return {}

            values = {}
            user_id_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

            for var_info in provider_vars:
                var_key = var_info.get("variable_key")
                if not var_key:
                    continue

                try:
                    value = await variable_service.get_variable(
                        user_id=user_id_uuid,
                        name=var_key,
                        field="",
                        session=session,
                    )
                    if value and str(value).strip():
                        values[var_key] = str(value)
                except (ValueError, Exception):  # noqa: BLE001
                    # Variable not found - check environment
                    env_value = os.environ.get(var_key)
                    if env_value and env_value.strip():
                        values[var_key] = env_value

            return values

    return run_until_complete(_get_all_variables())


def _validate_and_get_enabled_providers(
    all_variables: dict[str, Any],
    provider_variable_map: dict[str, str],
    *,
    skip_validation: bool = True,
) -> set[str]:
    """Return set of enabled providers based on credential existence."""
    from langflow.services.auth import utils as auth_utils
    from langflow.services.deps import get_settings_service

    settings_service = get_settings_service()
    enabled = set()

    for provider in provider_variable_map:
        provider_vars = get_provider_all_variables(provider)

        collected_values: dict[str, str] = {}
        all_required_present = True

        for var_info in provider_vars:
            var_key = var_info.get("variable_key")
            if not var_key:
                continue

            is_required = bool(var_info.get("required", False))
            value = None

            if var_key in all_variables:
                variable = all_variables[var_key]
                if variable.value is not None:
                    try:
                        decrypted_value = auth_utils.decrypt_api_key(variable.value, settings_service=settings_service)
                        if decrypted_value and decrypted_value.strip():
                            value = decrypted_value
                    except Exception as e:  # noqa: BLE001
                        raw_value = variable.value
                        if raw_value is not None and str(raw_value).strip():
                            value = str(raw_value)
                        else:
                            logger.debug(
                                "Failed to decrypt variable %s for provider %s: %s",
                                var_key,
                                provider,
                                e,
                            )

            if value is None:
                env_value = os.environ.get(var_key)
                if env_value and env_value.strip() and env_value.strip() != "dummy":
                    value = env_value
                    logger.debug(
                        "Using environment variable %s for provider %s",
                        var_key,
                        provider,
                    )

            if value:
                collected_values[var_key] = value
            elif is_required:
                all_required_present = False

        if not provider_vars:
            enabled.add(provider)
        elif all_required_present and collected_values:
            if skip_validation:
                # Just check existence - validation was done on save
                enabled.add(provider)
            else:
                try:
                    validate_model_provider_key(provider, collected_values)
                    enabled.add(provider)
                except (ValueError, Exception) as e:  # noqa: BLE001
                    logger.debug("Provider %s validation failed: %s", provider, e)

    return enabled


class _VarWithValue:
    """Simple wrapper for passing raw variable values to _validate_and_get_enabled_providers."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


async def _get_model_status(user_id: UUID | str) -> tuple[set[str], set[str]]:
    """Fetch disabled and explicitly enabled model sets for a user.

    Returns:
        A tuple of (disabled_models, explicitly_enabled_models).
    """
    async with session_scope() as session:
        variable_service = get_variable_service()
        if variable_service is None:
            return set(), set()
        from langflow.services.variable.service import DatabaseVariableService

        if not isinstance(variable_service, DatabaseVariableService):
            return set(), set()
        all_vars = await variable_service.get_all(
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            session=session,
        )
        disabled: set[str] = set()
        enabled: set[str] = set()
        for var in all_vars:
            if var.name == "__disabled_models__" and var.value:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    disabled = set(json.loads(var.value))
            elif var.name == "__enabled_models__" and var.value:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    enabled = set(json.loads(var.value))
        return disabled, enabled


async def _fetch_enabled_providers_for_user(user_id: UUID | str) -> set[str]:
    """Shared helper for get_language_model_options and get_embedding_model_options."""
    async with session_scope() as session:
        variable_service = get_variable_service()
        if variable_service is None:
            return set()

        from langflow.services.variable.service import DatabaseVariableService

        if not isinstance(variable_service, DatabaseVariableService):
            return set()

        # Get all variable names (VariableRead has value=None for credentials)
        all_vars = await variable_service.get_all(
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            session=session,
        )
        all_var_names = {var.name for var in all_vars}

        provider_variable_map = get_model_provider_variable_mapping()

        # Build dict with raw Variable values (encrypted for secrets, plaintext for others)
        # We need to fetch raw Variable objects because VariableRead has value=None for credentials
        all_provider_variables = {}
        user_id_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

        for provider in provider_variable_map:
            # Get ALL variables for this provider (not just the primary one)
            provider_vars = get_provider_all_variables(provider)

            for var_info in provider_vars:
                var_name = var_info.get("variable_key")
                if not var_name or var_name not in all_var_names:
                    # Variable not configured by user
                    continue

                if var_name in all_provider_variables:
                    # Already fetched
                    continue

                try:
                    # Get the raw Variable object to access the actual value
                    variable_obj = await variable_service.get_variable_object(
                        user_id=user_id_uuid, name=var_name, session=session
                    )
                    if variable_obj and variable_obj.value:
                        all_provider_variables[var_name] = _VarWithValue(variable_obj.value)
                except Exception as e:  # noqa: BLE001
                    # Variable not found or error accessing it - skip
                    logger.error(f"Error accessing variable {var_name} for provider {provider}: {e}")
                    continue

        # Use shared helper to validate and get enabled providers
        return _validate_and_get_enabled_providers(all_provider_variables, provider_variable_map)


def validate_model_provider_key(provider: str, variables: dict[str, str], model_name: str | None = None) -> None:
    """Validate a model provider by making a minimal test call."""
    if not provider:
        return

    first_model = None
    try:
        from .model_catalog import get_unified_models_detailed

        models = get_unified_models_detailed(providers=[provider])
        if models and models[0].get("models"):
            first_model = models[0]["models"][0]["model_name"]
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting unified models for provider {provider}: {e}")

    # For providers that need a model to test credentials
    if not first_model and provider in [
        "OpenAI",
        "Anthropic",
        "Google Generative AI",
        "IBM WatsonX",
    ]:
        return

    try:
        if provider == "OpenAI":
            from langchain_openai import ChatOpenAI  # type: ignore  # noqa: PGH003

            api_key = variables.get("OPENAI_API_KEY")
            if not api_key:
                return
            llm = ChatOpenAI(api_key=api_key, model_name=first_model, max_tokens=1)
            llm.invoke("test")

        elif provider == "Anthropic":
            from langchain_anthropic import ChatAnthropic  # type: ignore  # noqa: PGH003

            api_key = variables.get("ANTHROPIC_API_KEY")
            if not api_key:
                return
            llm = ChatAnthropic(anthropic_api_key=api_key, model=first_model, max_tokens=1)
            llm.invoke("test")

        elif provider == "Google Generative AI":
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore  # noqa: PGH003

            api_key = variables.get("GOOGLE_API_KEY")
            if not api_key:
                return
            llm = ChatGoogleGenerativeAI(google_api_key=api_key, model=first_model, max_tokens=1)
            llm.invoke("test")

        elif provider == "IBM WatsonX":
            from langchain_ibm import ChatWatsonx

            api_key = variables.get("WATSONX_APIKEY")
            project_id = variables.get("WATSONX_PROJECT_ID")
            url = variables.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
            if not api_key or not project_id:
                return
            llm = ChatWatsonx(
                apikey=api_key,
                url=url,
                model_id=first_model,
                project_id=project_id,
                params={"max_new_tokens": 1},
            )
            llm.invoke("test")

        elif provider == "Ollama":
            import requests

            base_url = variables.get("OLLAMA_BASE_URL")
            if not base_url:
                msg = "Invalid Ollama base URL"
                logger.error(msg)
                raise ValueError(msg)

            base_url = base_url.rstrip("/")
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            response.raise_for_status()

            data = response.json()
            if not isinstance(data, dict) or "models" not in data:
                msg = "Invalid Ollama base URL"
                logger.error(msg)
                raise ValueError(msg)

            if model_name:
                available_models = [m.get("name") for m in data["models"]]
                # Exact match or match with :latest
                if model_name not in available_models and f"{model_name}:latest" not in available_models:
                    # Lenient check for missing tag
                    if ":" not in model_name:
                        if not any(m.startswith(f"{model_name}:") for m in available_models):
                            available_str = ", ".join(available_models[:3])
                            msg = f"Model '{model_name}' not found on Ollama server. Available: {available_str}"
                            logger.error(msg)
                            raise ValueError(msg)
                    else:
                        available_str = ", ".join(available_models[:3])
                        msg = f"Model '{model_name}' not found on Ollama server. Available: {available_str}"
                        logger.error(msg)
                        raise ValueError(msg)

    except ValueError:
        raise
    except Exception as e:
        error_msg = str(e).lower()
        if any(word in error_msg for word in ["401", "authentication", "api key"]):
            msg = f"Invalid API key for {provider}"
            logger.error(f"Invalid API key for {provider}: {e}")
            raise ValueError(msg) from e

        # Rethrow specific Ollama errors with a user-facing message
        if provider == "Ollama":
            msg = "Invalid Ollama base URL"
            logger.error(msg)
            raise ValueError(msg) from e

        # For others, log and return (allow saving despite minor errors)
        return
