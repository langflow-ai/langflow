"""Build-config lifecycle helpers for ModelInput-based components."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any
from uuid import UUID

from lfx.log.logger import logger
from lfx.services.deps import get_variable_service, session_scope
from lfx.utils.async_helpers import run_until_complete

from .provider_queries import _get_all_provider_specific_field_names

# TTL for the per-user model-options cache inside update_model_options_in_build_config.
# Short enough to pick up global-variable changes quickly.
_MODEL_OPTIONS_CACHE_TTL_SECONDS = 30


def apply_provider_variable_config_to_build_config(
    build_config: dict,
    provider: str,
) -> dict:
    """Apply provider variable metadata to component build config fields."""
    # Resolve helpers via package namespace so tests patching
    # lfx.base.models.unified_models.<name> keep working.
    from lfx.base.models import unified_models as unified_models_module

    provider_vars = unified_models_module.get_provider_all_variables(provider)

    """
    First hides all provider-specific fields (so switching e.g. IBM -> OpenAI
    does not leave IBM fields visible), then shows and configures only the
    current provider's fields.
    """
    all_provider_fields = _get_all_provider_specific_field_names()
    for field_name in all_provider_fields:
        if field_name in build_config:
            build_config[field_name]["show"] = False
            build_config[field_name]["required"] = False

    vars_by_field = {}
    for v in provider_vars:
        component_meta = v.get("component_metadata", {})
        mapping_field = component_meta.get("mapping_field")
        if mapping_field:
            vars_by_field[mapping_field] = v

    # Apply the current provider's variable metadata to show/configure the right fields and pre-populate credentials.
    for field_name, var_info in vars_by_field.items():
        if field_name not in build_config:
            continue

        field_config = build_config[field_name]
        component_meta = var_info.get("component_metadata", {})

        # Apply required from component_metadata
        required = component_meta.get("required", False)
        field_config["required"] = required

        # Apply advanced from component_metadata
        advanced = component_meta.get("advanced", False)
        field_config["advanced"] = advanced

        # Apply info from component_metadata
        info = component_meta.get("info")
        if info:
            field_config["info"] = info

        field_config["show"] = True

        # Pre-populate with the variable name (never the raw secret) when a
        # credential is available in the database or environment.  Setting
        # load_from_db=True tells the runtime to resolve the actual value.
        var_key = var_info.get("variable_key")
        if var_key:
            # DropdownInput fields don't support load_from_db because the
            # variable key name (e.g. "WATSONX_URL") isn't a valid dropdown
            # option.  These fields are resolved separately by
            # _resolve_dropdown_provider_values in handle_model_input_update.
            input_type = field_config.get("_input_type", "")
            if input_type == "DropdownInput":
                logger.debug(
                    "Skipping load_from_db for DropdownInput field %s (will resolve separately)",
                    field_name,
                )
            else:
                # Only set the value if the field is currently empty or not already set to load from db
                # This prevents overwriting user-selected global variables
                current_value = field_config.get("value")
                current_load_from_db = field_config.get("load_from_db", False)
                if not current_value or (not current_load_from_db):
                    field_config["value"] = var_key
                    field_config["load_from_db"] = True
                    logger.debug(
                        "Set field %s to var name %s (value resolved at runtime)",
                        field_name,
                        var_key,
                    )
                else:
                    logger.debug(
                        "Skipping auto-set for field %s - user has already selected a value (load_from_db=True)",
                        field_name,
                    )

    return build_config


def update_model_options_in_build_config(
    component: Any,
    build_config: dict,
    cache_key_prefix: str,
    get_options_func,
    field_name: str | None = None,
    field_value: Any = None,
    model_field_name: str = "model",
) -> dict:
    """Helper function to update build config with cached model options."""
    import time

    # Check if component specified static options - if so, preserve them
    # The cache key for static options detection
    static_options_cache_key = f"{cache_key_prefix}_static_options_detected"

    # On initial load, check if the component has static options
    if field_name is None and static_options_cache_key not in component.cache:
        # Check if the model field in build_config already has options set
        existing_options = build_config.get(model_field_name, {}).get("options")
        if existing_options:
            # Component specified static options - mark them as static
            component.cache[static_options_cache_key] = True
        else:
            component.cache[static_options_cache_key] = False

    # If component has static options, skip the refresh logic entirely
    if component.cache.get(static_options_cache_key, False):
        # Static options - don't override them
        # Just handle the visibility logic and return
        if field_value == "connect_other_models":
            # User explicitly selected "Connect other models", show the handle
            if cache_key_prefix == "embedding_model_options":
                build_config[model_field_name]["input_types"] = ["Embeddings"]
            else:
                build_config[model_field_name]["input_types"] = ["LanguageModel"]
        else:
            # Default case or model selection: hide the handle
            build_config[model_field_name]["input_types"] = []
        return build_config

    # Cache key based on user_id
    cache_key = f"{cache_key_prefix}_{component.user_id}"
    cache_timestamp_key = f"{cache_key}_timestamp"
    cache_ttl = _MODEL_OPTIONS_CACHE_TTL_SECONDS

    # Check if cache is expired
    cache_expired = False
    if cache_timestamp_key in component.cache:
        time_since_cache = time.time() - component.cache[cache_timestamp_key]
        cache_expired = time_since_cache > cache_ttl

    # Check if we need to refresh
    should_refresh = (
        field_name == "api_key"  # API key changed
        or field_name is None  # Initial load
        or field_name == model_field_name  # Model field refresh button clicked
        or cache_key not in component.cache  # Cache miss
        or cache_expired  # Cache expired
    )

    if should_refresh:
        # Fetch options based on user's enabled models
        try:
            options = get_options_func(user_id=component.user_id)
            # Cache the results with timestamp
            component.cache[cache_key] = {"options": options}
            component.cache[cache_timestamp_key] = time.time()
        except KeyError as exc:
            # If we can't get user-specific options, fall back to empty.
            # Logged as warning (not debug) so silent UI failures are visible
            # in server logs for easier troubleshooting.
            logger.warning("Failed to fetch user-specific model options: %s", exc)
            component.cache[cache_key] = {"options": []}
            component.cache[cache_timestamp_key] = time.time()

    # Use cached results
    cached = component.cache.get(cache_key, {"options": []})
    build_config[model_field_name]["options"] = cached["options"]

    # Set default value on initial load when field is empty
    # Fetch from user's default model setting in the database
    if not field_value or field_value == "":
        options = cached.get("options", [])
        if options:
            # Determine model type based on cache_key_prefix
            model_type = "embeddings" if cache_key_prefix == "embedding_model_options" else "language"

            # Try to get user's default model from the variable service
            default_model_name = None
            default_model_provider = None
            try:

                async def _get_default_model():
                    async with session_scope() as session:
                        variable_service = get_variable_service()
                        if variable_service is None:
                            return None, None
                        from langflow.services.variable.service import (
                            DatabaseVariableService,
                        )

                        if not isinstance(variable_service, DatabaseVariableService):
                            return None, None

                        # Variable names match those in the API
                        var_name = (
                            "__default_embedding_model__"
                            if model_type == "embeddings"
                            else "__default_language_model__"
                        )

                        try:
                            var = await variable_service.get_variable_object(
                                user_id=(
                                    UUID(component.user_id) if isinstance(component.user_id, str) else component.user_id
                                ),
                                name=var_name,
                                session=session,
                            )
                            if var and var.value:
                                parsed_value = json.loads(var.value)
                                if isinstance(parsed_value, dict):
                                    return parsed_value.get("model_name"), parsed_value.get("provider")
                        except (ValueError, json.JSONDecodeError, TypeError):
                            # Variable not found or invalid format
                            logger.info(
                                "Variable not found or invalid format: var_name=%s, user_id=%s, model_type=%s",
                                var_name,
                                component.user_id,
                                model_type,
                                exc_info=True,
                            )
                        return None, None

                default_model_name, default_model_provider = run_until_complete(_get_default_model())
            except Exception:  # noqa: BLE001
                # If we can't get default model, continue without it
                logger.info("Failed to get default model, continue without it", exc_info=True)

            # Find the default model in options
            default_model = None
            if default_model_name and default_model_provider:
                # Look for the user's preferred default model
                for opt in options:
                    if opt.get("name") == default_model_name and opt.get("provider") == default_model_provider:
                        default_model = opt
                        break

            # If user's default not found, fallback to first option
            if not default_model and options:
                default_model = options[0]

            # Set the value
            if default_model:
                build_config[model_field_name]["value"] = [default_model]

    # Handle visibility of the model input handle based on selection
    if cache_key_prefix == "embedding_model_options":
        build_config[model_field_name]["input_types"] = ["Embeddings"]
    else:
        build_config[model_field_name]["input_types"] = ["LanguageModel"]

    return build_config


@lru_cache(maxsize=1)
def _get_all_provider_mapped_fields() -> set[str]:
    """Backward-compatible alias for provider mapped field names."""
    return _get_all_provider_specific_field_names()


def handle_model_input_update(
    component: Any,
    build_config: dict,
    field_value: Any,
    field_name: str | None = None,
    *,
    cache_key_prefix: str = "language_model_options",
    get_options_func=None,
    model_field_name: str = "model",
) -> dict:
    """Full update_build_config lifecycle for any component with a ModelInput."""
    from lfx.base.models import unified_models as unified_models_module

    # If get_options_func is not provided, use the default based on cache_key_prefix
    if get_options_func is None:
        get_options_func = unified_models_module.get_language_model_options

    # Step 1: Refresh/cache model options, set defaults and input_types
    build_config = update_model_options_in_build_config(
        component=component,
        build_config=build_config,
        cache_key_prefix=cache_key_prefix,
        get_options_func=get_options_func,
        field_name=field_name,
        field_value=field_value,
        model_field_name=model_field_name,
    )

    # When the user directly edits a provider-specific field (e.g. api_key),
    # skip the provider reset/re-population so their value is preserved.
    provider_mapped_fields = _get_all_provider_mapped_fields()
    if field_name in provider_mapped_fields:
        return build_config

    # When the user changes the model selection, we need to reset/hide fields that may no longer apply
    if field_name == model_field_name:
        options = build_config[model_field_name].get("options", [])
        build_config[model_field_name]["options"] = options

        value_missing = not field_value or field_value[0] not in options
        if value_missing:
            # If the current value is not in the options (e.g. user switched to a model that
            # is no longer available), reset to avoid confusion so the user can pick a valid one.
            option_names = {opt["name"] for opt in options}
            value_is_valid = bool(field_value) and field_value[0]["name"] in option_names

            # If the value is invalid, reset to the first option if available, otherwise empty.
            build_config[model_field_name]["value"] = field_value if value_is_valid else [options[0]] if options else ""
            field_value = build_config[model_field_name]["value"]

    # Step 2: Hide all provider-specific fields and clear their values by default.
    # Clearing values ensures that when Step 3 re-configures for the newly selected
    # provider, the auto-population logic can set the correct credential (e.g.
    # switching OpenAI → Anthropic replaces OPENAI_API_KEY with ANTHROPIC_API_KEY).
    for field in provider_mapped_fields:
        if field in build_config:
            build_config[field]["show"] = False
            build_config[field]["required"] = False
            build_config[field]["value"] = ""

    # Step 3: Show/configure the right fields for the selected provider
    # Use field_value when the user actively changed the model selection;
    # otherwise (initial load with empty field_value, or other field changes)
    # fall back to the value in build_config (which Step 1 may have set to the default model).
    current_model_value = (
        field_value
        if field_name == model_field_name and field_value
        else build_config.get(model_field_name, {}).get("value")
    )
    if isinstance(current_model_value, list) and len(current_model_value) > 0:
        provider = current_model_value[0].get("provider", "")
        if provider:
            build_config = unified_models_module.apply_provider_variable_config_to_build_config(build_config, provider)

            # Resolve DropdownInput field values from the provider's configured
            # variables.  load_from_db doesn't work for dropdowns because the
            # variable key name isn't a valid dropdown option.
            if hasattr(component, "user_id") and component.user_id:
                _resolve_dropdown_provider_values(component.user_id, build_config, provider)

        # Also handle WatsonX-specific embedding fields that are not in provider metadata
        if cache_key_prefix == "embedding_model_options":
            is_watsonx = provider == "IBM WatsonX"
            if "truncate_input_tokens" in build_config:
                build_config["truncate_input_tokens"]["show"] = is_watsonx
            if "input_text" in build_config:
                build_config["input_text"]["show"] = is_watsonx

    # Ensure the API key field is always visible regardless of provider selection
    if "api_key" in build_config:
        build_config["api_key"]["show"] = True

    return build_config


def _resolve_dropdown_provider_values(
    user_id,
    build_config: dict,
    provider: str,
) -> None:
    """Resolve actual values for DropdownInput fields from provider variables.

    DropdownInput fields cannot use the load_from_db mechanism because the
    variable key name (e.g. ``WATSONX_URL``) is not a valid dropdown option.
    Instead, we resolve the stored value from the database/environment and
    set it directly on the field.
    """
    from lfx.base.models import unified_models as unified_models_module

    provider_vars = unified_models_module.get_provider_all_variables(provider)

    # Collect dropdown fields that need resolution
    dropdown_var_keys: dict[str, str] = {}  # var_key -> mapping_field
    for var_info in provider_vars:
        component_meta = var_info.get("component_metadata", {})
        mapping_field = component_meta.get("mapping_field")
        if not mapping_field or mapping_field not in build_config:
            continue

        field_config = build_config[mapping_field]
        if field_config.get("_input_type") != "DropdownInput":
            continue

        var_key = var_info.get("variable_key")
        if var_key:
            dropdown_var_keys[var_key] = mapping_field

    if not dropdown_var_keys:
        return

    # Resolve all provider variables at once
    all_vars = unified_models_module.get_all_variables_for_provider(user_id, provider)

    for var_key, field_name in dropdown_var_keys.items():
        field_config = build_config[field_name]
        resolved_value = all_vars.get(var_key)
        if resolved_value:
            field_config["value"] = resolved_value
            field_config["load_from_db"] = False
            logger.debug(
                "Resolved DropdownInput field %s to %s",
                field_name,
                resolved_value,
            )
        else:
            # If we can't resolve, fall back to the first dropdown option
            options = field_config.get("options", [])
            if options:
                field_config["value"] = options[0]
            field_config["load_from_db"] = False
            logger.debug(
                "Could not resolve variable %s for DropdownInput field %s, using default",
                var_key,
                field_name,
            )
