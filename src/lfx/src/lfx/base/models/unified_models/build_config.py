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


def _filters_from_component_inputs(
    component: Any,
    model_field_name: str,
) -> dict[str, Any]:
    """Read filters from the component's class-level ModelInput declaration.

    This is the canonical source: saved flows persisted before the
    ``filters`` field shipped don't carry it in their stored template, so
    relying on the round-tripped ``build_config`` lets old flows silently
    bypass the constraint. Class-level declarations always reflect the
    current server build.
    """
    inputs = getattr(component, "inputs", None) or getattr(type(component), "inputs", None) or []
    for inp in inputs:
        if getattr(inp, "name", None) != model_field_name:
            continue
        raw = getattr(inp, "filters", None)
        if isinstance(raw, dict):
            return {k: v for k, v in raw.items() if v is not None}
        return {}
    return {}


def _filters_from_build_config(
    build_config: dict,
    model_field_name: str,
) -> dict[str, Any]:
    """Read the declarative ``filters`` dict off the ModelInput's config.

    Returns an empty dict when no filters are declared, so callers can use
    ``if filters:`` to detect the constrained mode. Used as a fallback when
    the calling helper doesn't have a component reference handy.
    """
    field_config = build_config.get(model_field_name)
    if not isinstance(field_config, dict):
        return {}
    raw = field_config.get("filters")
    if not isinstance(raw, dict):
        return {}
    # Drop empty / falsy filter entries so ``{"tool_calling": None}`` is a no-op.
    return {k: v for k, v in raw.items() if v is not None}


def _resolve_filters(component: Any, build_config: dict, model_field_name: str) -> dict[str, Any]:
    """Resolve the active filters dict.

    Prefer the class-level ModelInput declaration (canonical, always
    reflects the current server build) and fall back to ``build_config``
    when the component happens to have no inputs attribute. The build_config
    is also patched in-place so the next round-trip carries the current
    filters back to the frontend.
    """
    filters = _filters_from_component_inputs(component, model_field_name) or _filters_from_build_config(
        build_config, model_field_name
    )
    field_config = build_config.get(model_field_name)
    if isinstance(field_config, dict) and filters and field_config.get("filters") != filters:
        field_config["filters"] = dict(filters)
    return filters


def _augmented_cache_key_prefix(prefix: str, filters: dict[str, Any]) -> str:
    """Namespace the options-cache key by the active filters.

    Without this, switching a single ModelInput's filters between two
    different constraint sets would let stale cached options leak through.
    """
    if not filters:
        return prefix
    suffix = "_".join(f"{k}={filters[k]}" for k in sorted(filters))
    return f"{prefix}__{suffix}"


def _saved_model_passes_filters(
    saved_name: str,
    saved_provider: str,
    filters: dict[str, Any],
) -> bool:
    """Check whether the saved model matches every active metadata filter.

    Looks up the model in the *unfiltered* catalog (deprecated + unsupported
    included) so we don't false-reject a model just because it's currently
    deprecated. Returns ``True`` conservatively when the model isn't in the
    catalog at all (e.g. a user-supplied custom model) — that preserves
    today's "inject and let the user configure" behavior for cases this
    check doesn't actually know how to evaluate.
    """
    if not filters:
        return True
    from .model_catalog import get_unified_models_detailed

    providers = [saved_provider] if saved_provider else None
    rows = get_unified_models_detailed(
        providers=providers,
        model_name=saved_name,
        include_unsupported=True,
        include_deprecated=True,
    )
    for prov_block in rows:
        for m in prov_block.get("models", []):
            if m.get("model_name") == saved_name:
                metadata = m.get("metadata") or {}
                return all(metadata.get(k) == v for k, v in filters.items())
    return True


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
                # Decide whether to install this provider's variable key on
                # the field.  Cases:
                #
                # 1. Empty field — auto-populate.
                # 2. ``load_from_db=True`` with a value that doesn't match
                #    this provider's ``var_key`` — stale cross-provider
                #    credential (e.g. ``ANTHROPIC_API_KEY`` left over after
                #    switching to OpenAI).  Replace with the current
                #    provider's var_key.
                # 3. ``load_from_db=True`` with a value that matches
                #    ``var_key`` — already correct, preserve.
                # 4. ``load_from_db=False`` with a value — user-typed raw
                #    credential.  Preserve so it survives refresh cycles.
                #    We cannot tell from the backend whether a raw value is
                #    stale after a provider switch, so we err on the side
                #    of preservation; the user can overwrite it manually.
                current_value = field_config.get("value")
                current_load_from_db = field_config.get("load_from_db", False)
                is_empty = not current_value
                is_stale_cross_provider_var = current_load_from_db and current_value != var_key
                if is_empty or is_stale_cross_provider_var:
                    field_config["value"] = var_key
                    field_config["load_from_db"] = True
                    logger.debug(
                        "Set field %s to var name %s (value resolved at runtime)",
                        field_name,
                        var_key,
                    )
                else:
                    logger.debug(
                        "Skipping auto-set for field %s - user has already supplied a value",
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

    # Sticky-default: if the currently saved value references a model that
    # isn't in the freshly-fetched options list (e.g. an imported flow whose
    # exporter had providers the importing user hasn't enabled, or a model
    # whose provider was toggled off after saving), inject the saved value
    # into the options list with a ``not_enabled_locally`` metadata flag.
    # The frontend surfaces a "configure" wrench next to the trigger when it
    # sees this flag so the user can enable the provider without silently
    # losing their selection.
    current_value = build_config.get(model_field_name, {}).get("value")
    if (
        isinstance(current_value, list)
        and current_value
        and isinstance(current_value[0], dict)
        and current_value[0].get("name")
    ):
        saved = current_value[0]
        saved_name = saved["name"]
        saved_provider = saved.get("provider", "")
        options_list = build_config[model_field_name]["options"]
        already_present = any(
            opt.get("name") == saved_name and opt.get("provider", "") == saved_provider for opt in options_list
        )
        if not already_present:
            # When the ModelInput declares filters (e.g. Agent passes
            # ``filters={"tool_calling": True}``) and the saved selection
            # exists in the catalog but doesn't satisfy them, the regular
            # ``not_enabled_locally`` injection would put a model in the
            # dropdown that crashes at run time. Clear the saved value so
            # the downstream auto-default falls through to a compatible
            # model instead. ``_resolve_filters`` reads the class-level
            # declaration so saved flows that predate the filter shipping
            # cannot bypass the constraint.
            filters = _resolve_filters(component, build_config, model_field_name)
            saved_passes_filters = _saved_model_passes_filters(saved_name, saved_provider, filters) if filters else True
            if filters and not saved_passes_filters:
                logger.debug(
                    "Dropping saved model %s/%s that does not satisfy filters %s",
                    saved_provider,
                    saved_name,
                    filters,
                )
                build_config[model_field_name]["value"] = None
            else:
                injected = {**saved, "metadata": {**(saved.get("metadata") or {}), "not_enabled_locally": True}}
                build_config[model_field_name]["options"] = [*options_list, injected]

    # Set default value on initial load when the model field has no value.
    # We check the model field's own value (not field_value, which is the value
    # of whatever field triggered the update — e.g. api_key text).  Using
    # field_value here would incorrectly reset the model selection whenever a
    # non-model field (like api_key) is cleared or set to a global variable.
    current_model_value = build_config.get(model_field_name, {}).get("value")
    if not current_model_value:
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


def _is_model_name_only(value: Any) -> bool:
    """True when ``value`` is a non-empty model name (or list of names).

    ModelInput accepts a bare model name; the list-of-dicts shape is what
    the rest of the lifecycle expects. An empty/falsy value is NOT a name
    (it must keep its existing reset-to-default behavior).
    """
    if isinstance(value, str):
        return bool(value.strip())
    return isinstance(value, list) and bool(value) and all(isinstance(item, str) for item in value)


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

    # If get_options_func is not provided, derive one from the declarative
    # ``filters`` dict on the ModelInput (e.g. Agent declares
    # ``filters={"tool_calling": True}``). The cache prefix is namespaced by
    # the sorted filter key/value pairs so different filter configurations
    # don't poison each other's caches. ``_resolve_filters`` reads the
    # class-level declaration as the canonical source so saved flows that
    # were persisted before the filter shipped (and therefore don't carry
    # ``filters`` in their stored template) still get the constraint applied.
    filters = _resolve_filters(component, build_config, model_field_name)
    if get_options_func is None:
        if filters:
            cache_key_prefix = _augmented_cache_key_prefix(cache_key_prefix, filters)

            def get_options_func(user_id=None, _filters=filters):
                return unified_models_module.get_language_model_options(user_id=user_id, filters=_filters)
        else:
            get_options_func = unified_models_module.get_language_model_options

    # ModelInput documents that a single model name / list of names is
    # auto-converted to the list-of-dicts shape. Honor that contract here
    # (e.g. the assistant's configure_component can persist a bare model
    # name like "gpt-5.4") so the rest of the lifecycle never indexes a
    # str as a dict — TypeError: string indices must be integers.
    if _is_model_name_only(field_value):
        from .model_catalog import normalize_model_names_to_dicts

        field_value = normalize_model_names_to_dicts(field_value)
        if field_name == model_field_name and isinstance(build_config.get(model_field_name), dict):
            build_config[model_field_name]["value"] = field_value

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

    # If the model field is in connection mode (user chose "Connect other models"),
    # skip auto-selection and provider re-population so credentials stay cleared.
    if build_config.get(model_field_name, {}).get("_connection_mode"):
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

    # Step 2: Hide all provider-specific fields.  We do NOT clear values
    # here — the frontend has already mutated ``template[model]["value"]``
    # to the new selection before POSTing, so the backend can't distinguish
    # a real provider switch from a same-provider refresh based on the
    # incoming build_config alone.  Instead,
    # ``apply_provider_variable_config_to_build_config`` (Step 3) handles
    # the credential swap by detecting stale cross-provider variable keys
    # in provider-mapped fields and replacing them with the current
    # provider's var key.  Raw user-typed values are preserved in all cases.
    for field in provider_mapped_fields:
        if field in build_config:
            field_config = build_config[field]
            field_config["show"] = False
            field_config["required"] = False

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

    # Hide and clear the API key field when the selected provider doesn't use one
    # (e.g. Ollama). ``apply_provider_variable_config_to_build_config`` already
    # sets ``show=True`` for providers whose metadata maps a variable to the
    # ``api_key`` field; if it wasn't shown, the provider has no api_key
    # variable and the previous provider's credential must not leak across
    # the switch.
    if "api_key" in build_config and not build_config["api_key"].get("show", False):
        build_config["api_key"]["value"] = ""
        build_config["api_key"]["load_from_db"] = False

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
