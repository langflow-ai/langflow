from __future__ import annotations

import json
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query
from lfx.base.models.model_metadata import EXPLICIT_ENABLE_ONLY_PROVIDERS
from lfx.base.models.model_utils import inject_custom_enabled_models, replace_with_live_models
from lfx.base.models.provider_registry import is_api_key_optional, provider_id_for
from lfx.base.models.unified_models import (
    get_live_only_providers,
    get_model_provider_metadata,
    get_model_provider_variable_mapping,
    get_model_providers,
    get_provider_all_variables,
    get_unified_models_detailed,
)
from lfx.base.models.unified_models.credentials import (
    model_status_contains,
    model_status_key,
    parse_model_status_key,
)
from lfx.services.model_provider_policy import (
    ModelProviderPolicyError,
    ModelProviderPolicyPurpose,
    resolve_model_provider_policy,
)
from loguru import logger
from pydantic import BaseModel, field_validator

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.authorization import VariableAction, ensure_variable_permission
from langflow.services.deps import get_variable_service
from langflow.services.variable.constants import GENERIC_TYPE
from langflow.services.variable.service import DatabaseVariableService

router = APIRouter(prefix="/models", tags=["Models"], include_in_schema=False)

# Variable names for storing disabled models and default models
DISABLED_MODELS_VAR = "__disabled_models__"
ENABLED_MODELS_VAR = "__enabled_models__"
DEFAULT_LANGUAGE_MODEL_VAR = "__default_language_model__"
DEFAULT_EMBEDDING_MODEL_VAR = "__default_embedding_model__"

# Security limits
MAX_STRING_LENGTH = 200  # Maximum length for model IDs and provider names
MAX_BATCH_UPDATE_SIZE = 100  # Maximum number of models that can be updated at once


def _resolve_policy(current_user: CurrentActiveUser, purpose: ModelProviderPolicyPurpose):
    return resolve_model_provider_policy(
        user_id=current_user.id,
        providers=get_model_providers(),
        purpose=purpose,
    )


def _require_provider(
    current_user: CurrentActiveUser,
    provider: str,
    purpose: ModelProviderPolicyPurpose,
) -> None:
    try:
        _resolve_policy(current_user, purpose).require(provider)
    except ModelProviderPolicyError as exc:
        # Do not confirm whether a hidden provider is registered or merely blocked.
        raise HTTPException(status_code=404, detail="Model provider not found") from exc


def get_provider_from_variable_name(variable_name: str) -> str | None:
    """Get provider name from a model provider variable name.

    Args:
        variable_name: The variable name (e.g., "OPENAI_API_KEY")

    Returns:
        The provider name (e.g., "OpenAI") or None if not a model provider variable
    """
    # Resolve against every declared provider variable, not just the primary
    # API-key mapping. This remains dynamic so providers registered by an
    # extension during startup participate without a process restart cache.
    for provider in get_model_providers():
        if any(variable.get("variable_key") == variable_name for variable in get_provider_all_variables(provider)):
            return provider
    return None


class ModelStatusUpdate(BaseModel):
    """Request model for updating model enabled status."""

    provider: str
    model_id: str
    enabled: bool
    model_type: Literal["llm", "embeddings"] | None = None

    @field_validator("model_id", "provider")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure strings are non-empty and reasonable length."""
        if not v or not v.strip():
            msg = "Field cannot be empty"
            raise ValueError(msg)
        if len(v) > MAX_STRING_LENGTH:
            msg = f"Field exceeds maximum length of {MAX_STRING_LENGTH} characters"
            raise ValueError(msg)
        return v.strip()


class ValidateProviderRequest(BaseModel):
    """Request model for validating provider credentials."""

    provider: str
    variables: dict[str, str]  # {variable_key: value}

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Ensure provider name is valid."""
        if not v or not v.strip():
            msg = "Provider cannot be empty"
            raise ValueError(msg)
        if len(v) > MAX_STRING_LENGTH:
            msg = f"Provider exceeds maximum length of {MAX_STRING_LENGTH} characters"
            raise ValueError(msg)
        return v.strip()


class ValidateProviderResponse(BaseModel):
    """Response model for provider validation."""

    valid: bool
    error: str | None = None


@router.get("/providers", status_code=200)
async def list_model_providers(current_user: CurrentActiveUser) -> list[str]:
    """Return available model providers."""
    policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.DISCOVER)
    return policy.filter(get_model_providers())


@router.get("", status_code=200)
async def list_models(
    *,
    provider: Annotated[list[str] | None, Query(description="Repeat to include multiple providers")] = None,
    model_name: str | None = None,
    model_type: str | None = None,
    include_unsupported: bool = False,
    include_deprecated: bool = False,
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
    provider_policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.DISCOVER)
    selected_providers: list[str] | None = provider_policy.filter(provider) if provider is not None else None
    if provider is not None and not selected_providers:
        return []
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

    # Get enabled providers status (now just checks if variables exist)
    enabled_providers_result = await get_enabled_providers(session=session, current_user=current_user)
    provider_configured_status = enabled_providers_result.get("provider_status", {})

    # Get enabled models map for current user to determine "active" providers
    enabled_models_result = await get_enabled_models(session=session, current_user=current_user)
    enabled_models_map = enabled_models_result.get("enabled_models", {})

    # Get default model if model_type is specified
    default_provider = None
    if model_type:
        try:
            default_model_result = await get_default_model(
                session=session, current_user=current_user, model_type=model_type
            )
            if default_model_result.get("default_model"):
                default_provider = default_model_result["default_model"].get("provider")
        except Exception:  # noqa: BLE001
            # Default model fetch failed, continue without it
            # This is not critical for the main operation - we suppress to avoid breaking the list
            logger.debug("Failed to fetch default model, continuing without it", exc_info=True)

    # Get filtered models - pass providers directly to avoid filtering after
    filtered_models = get_unified_models_detailed(
        providers=selected_providers,
        model_name=model_name,
        include_unsupported=include_unsupported,
        include_deprecated=include_deprecated,
        model_type=model_type,
        **metadata_filters,
    )

    # Live-discovery-only providers (contributed by extension bundles, e.g. vLLM or
    # OpenAI Compatible) ship no static catalog rows, so the catalog query above can
    # never emit them, and replace_with_live_models below only fills providers that
    # are already configured. Union them in with an empty model list so the Model
    # Providers dialog can offer their configuration form in the first place; once
    # configured, replace_with_live_models fills this same entry with the endpoint's
    # discovered models. Skipped for model_name/metadata queries, which ask about
    # concrete models rather than which providers exist.
    if model_name is None and not metadata_filters:
        provider_metadata = get_model_provider_metadata()
        listed_providers = {provider_dict.get("provider") for provider_dict in filtered_models}
        for live_only_provider in get_live_only_providers():
            if not provider_policy.allows(live_only_provider):
                continue
            if live_only_provider in listed_providers:
                continue
            if selected_providers and live_only_provider not in selected_providers:
                continue
            filtered_models.append(
                {
                    **provider_metadata.get(live_only_provider, {}),
                    "provider": live_only_provider,
                    "models": [],
                    "num_models": 0,
                }
            )

    # Run before status is computed so live-only providers appended here (e.g. IBM WatsonX,
    # whose static catalog is fully deprecated) still receive is_enabled/is_configured (#13735).
    configured_providers = {p for p, configured in provider_configured_status.items() if configured}
    configured_providers = {provider for provider in configured_providers if provider_policy.allows(provider)}
    replace_with_live_models(filtered_models, current_user.id, configured_providers, model_type)

    # Merge free-text custom deployments into the catalog (honors list_models filters).
    explicitly_enabled_models = await _get_enabled_models(session=session, current_user=current_user)
    inject_custom_enabled_models(
        filtered_models,
        explicitly_enabled_models,
        model_name=model_name,
        model_type=model_type,
        metadata_filters=metadata_filters or None,
    )
    filtered_models = [
        provider_data for provider_data in filtered_models if provider_policy.allows(provider_data.get("provider", ""))
    ]

    # replace_with_live_models iterates every live-capable provider regardless of
    # the ?provider= filter, so it can append providers the caller excluded (e.g.
    # a configured OpenRouter appearing in a ?provider=OpenAI response). Re-apply
    # the filter so the response honors its own contract.
    if selected_providers:
        filtered_models = [p for p in filtered_models if p.get("provider") in selected_providers]

    for provider_dict in filtered_models:
        prov_name = provider_dict.get("provider")
        provider_dict["provider_id"] = provider_id_for(prov_name) if isinstance(prov_name, str) else None
        provider_dict["is_configured"] = provider_configured_status.get(prov_name, False)
        prov_models_status = enabled_models_map.get(prov_name, {})
        has_active_model = any(prov_models_status.values())
        provider_dict["is_enabled"] = has_active_model

    def sort_key(provider_dict):
        provider_name = provider_dict.get("provider", "")
        is_configured = provider_dict.get("is_configured", False)
        is_default = provider_name == default_provider
        # default first, then configured, then alphabetical (False sorts before True)
        return (not is_default, not is_configured, provider_name)

    filtered_models.sort(key=sort_key)

    return filtered_models


@router.get("/provider-variable-mapping", status_code=200)
async def get_model_provider_mapping(current_user: CurrentActiveUser) -> dict[str, list[dict]]:
    """Return provider variables mapping with full variable info.

    Each provider maps to a list of variable objects containing:
    - variable_name: Display name shown to user
    - variable_key: Environment variable key
    - description: Help text for the variable
    - required: Whether the variable is required
    - is_secret: Whether to treat as credential
    - is_list: Whether it accepts multiple values
    - options: Predefined options for dropdowns
    """
    metadata = get_model_provider_metadata()
    policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.CONFIGURE)
    return {provider: meta.get("variables", []) for provider, meta in metadata.items() if policy.allows(provider)}


@router.get("/enabled_providers", status_code=200)
async def get_enabled_providers(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    providers: Annotated[list[str] | None, Query()] = None,
):
    """Get enabled providers for the current user.

    Providers are considered enabled if they have a credential variable stored.
    API key validation is performed when credentials are saved, not on every read,
    to avoid latency from external API calls.
    """
    provider_policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.CONFIGURE)
    variable_service = get_variable_service()
    try:
        if not isinstance(variable_service, DatabaseVariableService):
            raise HTTPException(
                status_code=500,
                detail="Variable service is not an instance of DatabaseVariableService",
            )
        # Get all variables (VariableRead objects)
        all_variables = await variable_service.get_all(user_id=current_user.id, session=session)

        # Build a set of all variable names we have
        all_variable_names = {var.name for var in all_variables}

        provider_variable_map = get_model_provider_variable_mapping()
        provider_candidates = [
            *provider_variable_map,
            *(
                provider
                for provider in get_model_providers()
                if provider not in provider_variable_map and is_api_key_optional(provider)
            ),
        ]

        # Check which providers have all required variables saved
        enabled_providers = []
        provider_status = {}

        for provider in provider_candidates:
            if not provider_policy.allows(provider):
                continue
            # Get ALL variables for this provider
            provider_vars = get_provider_all_variables(provider)

            # Check if all REQUIRED variables are present
            required_vars = [v for v in provider_vars if v.get("required", False)]
            all_required_present = (
                is_api_key_optional(provider)
                if not provider_vars
                else all(v.get("variable_key") in all_variable_names for v in required_vars)
            )

            provider_status[provider] = all_required_present
            if all_required_present:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get enabled providers for user %s", current_user.id)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve enabled providers. Please try again later.",
        ) from e
    else:
        return result


@router.post("/validate-provider", status_code=200, response_model=ValidateProviderResponse)
async def validate_provider(
    request: ValidateProviderRequest,
    current_user: CurrentActiveUser,
) -> ValidateProviderResponse:
    """Validate provider credentials before saving.

    This endpoint checks if the provided credentials are valid by attempting
    to connect to the provider. Use this for real-time validation in the UI.
    """
    _require_provider(current_user, request.provider, ModelProviderPolicyPurpose.CONFIGURE)

    from lfx.base.models.unified_models import validate_model_provider_key

    try:
        # Validate the credentials
        validate_model_provider_key(request.provider, request.variables)
        return ValidateProviderResponse(valid=True, error=None)
    except ValueError as e:
        return ValidateProviderResponse(valid=False, error=str(e))
    except (ConnectionError, TimeoutError, RuntimeError, KeyError, AttributeError, TypeError) as e:
        logger.exception("Unexpected error validating provider %s", request.provider)
        return ValidateProviderResponse(valid=False, error=f"Validation failed: {e}")


async def _get_disabled_models(session: DbSession, current_user: CurrentActiveUser) -> set[str]:
    """Helper function to get the set of disabled model IDs."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return set()

    try:
        var = await variable_service.get_variable_object(
            user_id=current_user.id, name=DISABLED_MODELS_VAR, session=session
        )
        if var.value:  # This checks for both None and empty string
            try:
                parsed_value = json.loads(var.value)
                # Validate it's a list of strings
                if not isinstance(parsed_value, list):
                    logger.warning("Invalid disabled models format for user %s: not a list", current_user.id)
                    return set()
                # Ensure all items are strings
                return {str(item) for item in parsed_value if isinstance(item, str)}
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse disabled models for user %s", current_user.id, exc_info=True)
                return set()
    except ValueError:
        # Variable not found, return empty set
        pass
    return set()


async def _get_enabled_models(session: DbSession, current_user: CurrentActiveUser) -> set[str]:
    """Helper function to get the set of explicitly enabled model IDs.

    These are models that were NOT default but were explicitly enabled by the user.
    """
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return set()

    try:
        var = await variable_service.get_variable_object(
            user_id=current_user.id, name=ENABLED_MODELS_VAR, session=session
        )
        # Strip whitespace and check if value is non-empty
        if var.value and (value_stripped := var.value.strip()):
            try:
                parsed_value = json.loads(value_stripped)
                # Validate it's a list of strings
                if not isinstance(parsed_value, list):
                    logger.warning("Invalid enabled models format for user %s: not a list", current_user.id)
                    return set()
                # Ensure all items are strings
                return {str(item) for item in parsed_value if isinstance(item, str)}
            except (json.JSONDecodeError, TypeError):
                # Log at debug level to avoid flooding logs with expected edge cases
                logger.debug("Failed to parse enabled models for user %s: %s", current_user.id, var.value)
                return set()
    except ValueError:
        # Variable not found, return empty set
        pass
    return set()


def build_model_providers_by_name(
    all_models_by_provider: list[dict] | None = None,
) -> dict[str, set[str]]:
    """Build a catalog index used to migrate legacy bare-name status entries."""
    if all_models_by_provider is None:
        all_models_by_provider = get_unified_models_detailed(
            include_unsupported=True,
            include_deprecated=True,
        )

    providers_by_name: dict[str, set[str]] = {}
    for provider_dict in all_models_by_provider:
        provider = provider_dict.get("provider")
        if not isinstance(provider, str):
            continue
        for model in provider_dict.get("models", []):
            model_name = model.get("model_name")
            if isinstance(model_name, str):
                providers_by_name.setdefault(model_name, set()).add(provider)
    return providers_by_name


def normalize_model_status_entries(
    entries: set[str],
    providers_by_name: dict[str, set[str]],
) -> set[str]:
    """Expand known legacy bare names to every matching provider identity.

    Bare entries historically applied globally. Expanding all matching catalog
    providers preserves that state while allowing the current write to change a
    single provider. Unknown bare names remain intact for read compatibility.
    """
    normalized: set[str] = set()
    for entry in entries:
        providers = providers_by_name.get(entry)
        if providers:
            normalized.update(model_status_key(provider, entry) for provider in providers)
        else:
            normalized.add(entry)
    return normalized


def _build_model_default_flags(
    all_models_by_provider: list[dict] | None = None,
) -> dict[str, bool]:
    """Build a map of typed and legacy model identities to default status.

    Returns:
        Dictionary mapping model-status identities to default status
    """
    if all_models_by_provider is None:
        all_models_by_provider = get_unified_models_detailed(
            include_unsupported=True,
            include_deprecated=True,
        )

    is_default_model: dict[str, bool] = {}
    for provider_dict in all_models_by_provider:
        provider = provider_dict.get("provider")
        if not isinstance(provider, str):
            continue
        for model in provider_dict.get("models", []):
            model_name = model.get("model_name")
            if not isinstance(model_name, str):
                continue
            metadata = model.get("metadata", {})
            is_default = metadata.get("default", False)
            model_type = metadata.get("model_type", "llm")
            legacy_key = model_status_key(provider, model_name)
            # OR defaults across typed rows sharing a provider/name identity.
            is_default_model[legacy_key] = is_default_model.get(legacy_key, False) or is_default
            if model_type in {"llm", "embeddings"}:
                is_default_model[model_status_key(provider, model_name, model_type)] = is_default

    return is_default_model


def _build_model_types_by_identity(
    all_models_by_provider: list[dict] | None = None,
) -> dict[str, set[str]]:
    """Build a map of provider-qualified model identities to catalog model types."""
    if all_models_by_provider is None:
        all_models_by_provider = get_unified_models_detailed(
            include_unsupported=True,
            include_deprecated=True,
        )

    model_types_by_identity: dict[str, set[str]] = {}
    for provider_dict in all_models_by_provider:
        provider = provider_dict.get("provider")
        if not isinstance(provider, str):
            continue
        for model in provider_dict.get("models", []):
            model_name = model.get("model_name")
            if not isinstance(model_name, str):
                continue
            model_type = model.get("metadata", {}).get("model_type", "llm")
            if model_type not in {"llm", "embeddings"}:
                continue
            identity = model_status_key(provider, model_name)
            model_types_by_identity.setdefault(identity, set()).add(model_type)

    return model_types_by_identity


def _discard_typed_status_variants(entries: set[str], provider: str, model_name: str) -> None:
    """Remove typed statuses for one provider/name while leaving legacy identities intact."""
    for entry in tuple(entries):
        entry_provider, entry_model_name, entry_model_type = parse_model_status_key(entry)
        if entry_provider == provider and entry_model_name == model_name and entry_model_type is not None:
            entries.discard(entry)


def _expand_matching_legacy_status(
    entries: set[str],
    provider: str,
    model_name: str,
    model_types: set[str],
) -> None:
    """Replace one legacy provider/name status with its typed equivalents."""
    legacy_key = model_status_key(provider, model_name)
    if legacy_key not in entries:
        return

    entries.discard(legacy_key)
    entries.update(model_status_key(provider, model_name, model_type) for model_type in model_types)


def _update_model_sets(
    updates: list[ModelStatusUpdate],
    disabled_models: set[str],
    explicitly_enabled_models: set[str],
    is_default_model: dict[str, bool],
    model_types_by_identity: dict[str, set[str]] | None = None,
) -> None:
    """Update disabled and enabled model sets based on user requests.

    Args:
        updates: List of model status updates from user
        disabled_models: Set of disabled model IDs (modified in place)
        explicitly_enabled_models: Set of explicitly enabled model IDs (modified in place)
        is_default_model: Map of provider-qualified model identities to default status
        model_types_by_identity: Catalog model types keyed by provider-qualified identity
    """
    model_types_by_identity = model_types_by_identity or {}

    for update in updates:
        legacy_key = model_status_key(update.provider, update.model_id)

        if update.model_type is not None:
            # Expand legacy name-level status to typed keys before a typed update.
            legacy_types = model_types_by_identity.get(legacy_key) or {"llm"}
            _expand_matching_legacy_status(
                disabled_models,
                update.provider,
                update.model_id,
                legacy_types,
            )
            _expand_matching_legacy_status(
                explicitly_enabled_models,
                update.provider,
                update.model_id,
                legacy_types,
            )
            status_key = model_status_key(update.provider, update.model_id, update.model_type)
        else:
            # Clear typed variants before writing legacy name-level state.
            _discard_typed_status_variants(disabled_models, update.provider, update.model_id)
            _discard_typed_status_variants(explicitly_enabled_models, update.provider, update.model_id)
            status_key = legacy_key

        model_is_default = is_default_model.get(status_key, is_default_model.get(legacy_key, False))

        if update.enabled:
            # User wants to enable the model
            disabled_models.discard(status_key)
            # Foundry seed defaults are suggestions; keep them explicitly enabled.
            if update.provider in EXPLICIT_ENABLE_ONLY_PROVIDERS or not model_is_default:
                explicitly_enabled_models.add(status_key)
            else:
                explicitly_enabled_models.discard(status_key)
        else:
            # User wants to disable the model
            disabled_models.add(status_key)
            explicitly_enabled_models.discard(status_key)


async def _save_model_list_variable(
    variable_service: DatabaseVariableService,
    session: DbSession,
    current_user: CurrentActiveUser,
    var_name: str,
    model_set: set[str],
) -> None:
    """Save or update a model list variable.

    Args:
        variable_service: The database variable service
        session: Database session
        current_user: Current active user
        var_name: Name of the variable to save
        model_set: Set of model names to save

    Raises:
        HTTPException: If there's an error saving the variable
    """
    from langflow.services.database.models.variable.model import VariableUpdate

    models_json = json.dumps(list(model_set))

    try:
        existing_var = await variable_service.get_variable_object(
            user_id=current_user.id, name=var_name, session=session
        )
        if existing_var is None or existing_var.id is None:
            msg = f"Variable {var_name} not found"
            raise ValueError(msg)

        # Update or delete based on whether there are models
        if model_set or var_name == DISABLED_MODELS_VAR:
            # Always update disabled models, even if empty
            # Only update enabled models if non-empty
            await variable_service.update_variable_fields(
                user_id=current_user.id,
                variable_id=existing_var.id,
                variable=VariableUpdate(id=existing_var.id, name=var_name, value=models_json, type=GENERIC_TYPE),
                session=session,
            )
        else:
            # No explicitly enabled models, delete the variable
            await variable_service.delete_variable(user_id=current_user.id, name=var_name, session=session)
    except ValueError:
        # Variable not found, create new one if there are models
        if model_set:
            await variable_service.create_variable(
                user_id=current_user.id,
                name=var_name,
                value=models_json,
                type_=GENERIC_TYPE,
                session=session,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to save model list variable %s for user %s",
            var_name,
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to save model configuration. Please try again later.",
        ) from e


@router.get("/enabled_models", status_code=200)
async def get_enabled_models(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    model_names: Annotated[list[str] | None, Query()] = None,
):
    """Get enabled models for the current user."""
    provider_policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.CONFIGURE)
    all_models_by_provider = get_unified_models_detailed(
        include_unsupported=True,
        include_deprecated=True,
    )

    enabled_providers_result = await get_enabled_providers(session=session, current_user=current_user)
    provider_status = enabled_providers_result.get("provider_status", {})

    all_models_by_provider = [
        provider_data
        for provider_data in all_models_by_provider
        if provider_policy.allows(provider_data.get("provider", ""))
    ]
    configured_providers = {
        provider for provider, configured in provider_status.items() if configured and provider_policy.allows(provider)
    }
    replace_with_live_models(all_models_by_provider, current_user.id, configured_providers)

    # Get disabled and explicitly enabled models lists
    disabled_models = await _get_disabled_models(session=session, current_user=current_user)
    explicitly_enabled_models = await _get_enabled_models(session=session, current_user=current_user)
    inject_custom_enabled_models(all_models_by_provider, explicitly_enabled_models)
    all_models_by_provider = [
        provider_data
        for provider_data in all_models_by_provider
        if provider_policy.allows(provider_data.get("provider", ""))
    ]

    enabled_models: dict[str, dict[str, bool]] = {}
    enabled_models_by_type: dict[str, dict[str, dict[str, bool]]] = {}

    for provider_dict in all_models_by_provider:
        provider = provider_dict.get("provider")
        models = provider_dict.get("models", [])

        # Initialize provider dict if not exists
        if provider not in enabled_models:
            enabled_models[provider] = {}
            enabled_models_by_type[provider] = {}

        for model in models:
            model_name = model.get("model_name")
            metadata = model.get("metadata", {})

            # Check if model is deprecated or not supported
            is_deprecated = metadata.get("deprecated", False)
            is_not_supported = metadata.get("not_supported", False)
            is_default = metadata.get("default", False)
            model_type = metadata.get("model_type", "llm")
            if model_type not in {"llm", "embeddings"}:
                model_type = "llm"

            # Foundry requires explicit enable; seed defaults are not auto-on.
            requires_explicit = provider in EXPLICIT_ENABLE_ONLY_PROVIDERS
            explicitly_on = model_status_contains(
                explicitly_enabled_models,
                provider,
                model_name,
                model_type=model_type,
            )
            explicitly_off = model_status_contains(
                disabled_models,
                provider,
                model_name,
                model_type=model_type,
            )
            is_enabled = (
                provider_status.get(provider, False)
                and not is_deprecated
                and not is_not_supported
                and (explicitly_on if requires_explicit else (is_default or explicitly_on))
                and not explicitly_off
            )
            # Per-type map is exact; flat map ORs rows that share provider/name.
            models_for_type = enabled_models_by_type[provider].setdefault(model_type, {})
            models_for_type[model_name] = models_for_type.get(model_name, False) or is_enabled
            enabled_models[provider][model_name] = enabled_models[provider].get(model_name, False) or is_enabled

    result = {
        "enabled_models": enabled_models,
        "enabled_models_by_type": enabled_models_by_type,
    }

    if model_names:
        # Filter enabled_models by requested models
        filtered_enabled: dict[str, dict[str, bool]] = {}
        for provider, models_dict in enabled_models.items():
            filtered_models = {m: v for m, v in models_dict.items() if m in model_names}
            if filtered_models:
                filtered_enabled[provider] = filtered_models

        filtered_enabled_by_type: dict[str, dict[str, dict[str, bool]]] = {}
        for provider, models_by_type in enabled_models_by_type.items():
            filtered_models_by_type: dict[str, dict[str, bool]] = {}
            for model_type, models_dict in models_by_type.items():
                filtered_models = {m: v for m, v in models_dict.items() if m in model_names}
                if filtered_models:
                    filtered_models_by_type[model_type] = filtered_models
            if filtered_models_by_type:
                filtered_enabled_by_type[provider] = filtered_models_by_type

        return {
            "enabled_models": filtered_enabled,
            "enabled_models_by_type": filtered_enabled_by_type,
        }

    return result


@router.post("/enabled_models", status_code=200)
async def update_enabled_models(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    updates: list[ModelStatusUpdate],
):
    """Update enabled status for specific models.

    Accepts a list of model IDs with their desired enabled status.
    This only affects model-level enablement - provider credentials must still be configured.
    """
    # Persists the enabled/disabled model lists as the user's own Variables: a
    # variable WRITE. Enforce so the external access ceiling caps a "viewer";
    # the owner with no ceiling fast-paths via owner-override.
    await ensure_variable_permission(
        current_user,
        VariableAction.WRITE,
        variable_user_id=current_user.id,
    )
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        raise HTTPException(
            status_code=500,
            detail="Variable service is not an instance of DatabaseVariableService",
        )

    # Limit batch size to prevent abuse
    if len(updates) > MAX_BATCH_UPDATE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update more than {MAX_BATCH_UPDATE_SIZE} models at once",
        )

    # Get current disabled and explicitly enabled models
    disabled_models = await _get_disabled_models(session=session, current_user=current_user)
    explicitly_enabled_models = await _get_enabled_models(session=session, current_user=current_user)

    all_models_by_provider = get_unified_models_detailed(
        include_unsupported=True,
        include_deprecated=True,
    )
    is_default_model = _build_model_default_flags(all_models_by_provider)
    model_types_by_identity = _build_model_types_by_identity(all_models_by_provider)
    providers_by_name = build_model_providers_by_name(all_models_by_provider)
    # Live/custom models may not be in the static catalog. The provider in this
    # request still gives a known identity for migrating a matching bare entry.
    for update in updates:
        providers_by_name.setdefault(update.model_id, set()).add(update.provider)

    disabled_models = normalize_model_status_entries(disabled_models, providers_by_name)
    explicitly_enabled_models = normalize_model_status_entries(explicitly_enabled_models, providers_by_name)

    unavailable_models: dict[tuple[str, str], str] = {}
    for provider_dict in all_models_by_provider:
        provider = provider_dict.get("provider")
        if not isinstance(provider, str):
            continue
        for model in provider_dict.get("models", []):
            model_name = model.get("model_name")
            if not isinstance(model_name, str):
                continue
            metadata = model.get("metadata", {})
            if metadata.get("deprecated", False):
                unavailable_models[(provider, model_name)] = "deprecated"
            elif metadata.get("not_supported", False):
                unavailable_models[(provider, model_name)] = "not supported"

    # Update model sets based on user requests
    # For any model being enabled, validate the provider credentials
    for update in updates:
        if update.enabled:
            _require_provider(current_user, update.provider, ModelProviderPolicyPurpose.CONFIGURE)
            unavailable_reason = unavailable_models.get((update.provider, update.model_id))
            if unavailable_reason:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot enable {unavailable_reason} model: {update.model_id}",
                )

            from lfx.base.models.unified_models import get_all_variables_for_provider, validate_model_provider_key

            # Get variables from DB or environment
            variables = get_all_variables_for_provider(current_user.id, update.provider)

            try:
                # Validate the credentials
                validate_model_provider_key(update.provider, variables, model_name=update.model_id)
            except ValueError as e:
                # Validation failed - return 400 with error message
                raise HTTPException(
                    status_code=400,
                    detail=f"Validation failed for {update.provider}: {e}",
                ) from e
            except Exception as e:
                logger.exception("Unexpected error validating provider %s", update.provider)
                raise HTTPException(
                    status_code=400,
                    detail=f"Validation failed for {update.provider}: {e}",
                ) from e

    _update_model_sets(
        updates,
        disabled_models,
        explicitly_enabled_models,
        is_default_model,
        model_types_by_identity=model_types_by_identity,
    )

    # Log the operation for audit trail
    logger.info(
        "User %s updated model status: %d models affected",
        current_user.id,
        len(updates),
    )

    # Save updated model lists
    await _save_model_list_variable(variable_service, session, current_user, DISABLED_MODELS_VAR, disabled_models)
    await _save_model_list_variable(
        variable_service, session, current_user, ENABLED_MODELS_VAR, explicitly_enabled_models
    )

    # Cleanup of a now-hidden provider remains allowed, but the response must
    # not echo hidden provider identities from persisted legacy state.
    provider_policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.CONFIGURE)

    def _visible_status_entries(entries: set[str]) -> list[str]:
        visible = []
        for entry in entries:
            provider, _model_name, _model_type = parse_model_status_key(entry)
            if provider is None or provider_policy.allows(provider):
                visible.append(entry)
        return visible

    return {
        "disabled_models": _visible_status_entries(disabled_models),
        "enabled_models": _visible_status_entries(explicitly_enabled_models),
    }


class DefaultModelRequest(BaseModel):
    """Request model for setting default model."""

    model_name: str
    provider: str
    model_type: str  # 'language' or 'embedding'

    @field_validator("model_name", "provider")
    @classmethod
    def validate_non_empty_string(cls, v: str) -> str:
        """Ensure strings are non-empty and reasonable length."""
        if not v or not v.strip():
            msg = "Field cannot be empty"
            raise ValueError(msg)
        if len(v) > MAX_STRING_LENGTH:
            msg = f"Field exceeds maximum length of {MAX_STRING_LENGTH} characters"
            raise ValueError(msg)
        return v.strip()

    @field_validator("model_type")
    @classmethod
    def validate_model_type(cls, v: str) -> str:
        """Ensure model_type is valid."""
        if v not in ("language", "embedding"):
            msg = "model_type must be 'language' or 'embedding'"
            raise ValueError(msg)
        return v


@router.get("/default_model", status_code=200)
async def get_default_model(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    model_type: Annotated[str, Query(description="Type of model: 'language' or 'embedding'")] = "language",
):
    """Get the default model for the current user."""
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        return {"default_model": None}

    var_name = DEFAULT_LANGUAGE_MODEL_VAR if model_type == "language" else DEFAULT_EMBEDDING_MODEL_VAR

    try:
        var = await variable_service.get_variable_object(user_id=current_user.id, name=var_name, session=session)
        if var.value:
            try:
                parsed_value = json.loads(var.value)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to parse default model for user %s", current_user.id, exc_info=True)
                return {"default_model": None}
            else:
                # Validate structure
                if not isinstance(parsed_value, dict) or not all(
                    k in parsed_value for k in ("model_name", "provider", "model_type")
                ):
                    logger.warning("Invalid default model format for user %s", current_user.id)
                    return {"default_model": None}
                policy = _resolve_policy(current_user, ModelProviderPolicyPurpose.USE)
                if not policy.allows(parsed_value["provider"]):
                    return {"default_model": None}
                return {"default_model": parsed_value}
    except ValueError:
        # Variable not found
        pass
    return {"default_model": None}


@router.post("/default_model", status_code=200)
async def set_default_model(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    request: DefaultModelRequest,
):
    """Set the default model for the current user."""
    _require_provider(current_user, request.provider, ModelProviderPolicyPurpose.USE)
    # Creating/updating the default-model Variable is a variable WRITE. Enforce
    # so the external access ceiling caps a "viewer"; the owner with no ceiling
    # fast-paths via owner-override.
    await ensure_variable_permission(
        current_user,
        VariableAction.WRITE,
        variable_user_id=current_user.id,
    )
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        raise HTTPException(
            status_code=500,
            detail="Variable service is not an instance of DatabaseVariableService",
        )

    var_name = DEFAULT_LANGUAGE_MODEL_VAR if request.model_type == "language" else DEFAULT_EMBEDDING_MODEL_VAR

    # Log the operation for audit trail
    logger.info(
        "User %s setting default %s model to %s (%s)",
        current_user.id,
        request.model_type,
        request.model_name,
        request.provider,
    )

    # Prepare the model data
    model_data = {
        "model_name": request.model_name,
        "provider": request.provider,
        "model_type": request.model_type,
    }
    model_json = json.dumps(model_data)

    # Check if the variable already exists
    try:
        existing_var = await variable_service.get_variable_object(
            user_id=current_user.id, name=var_name, session=session
        )
        if existing_var is None or existing_var.id is None:
            msg = f"Variable {DISABLED_MODELS_VAR} not found"
            raise ValueError(msg)
        # Update existing variable
        from langflow.services.database.models.variable.model import VariableUpdate

        await variable_service.update_variable_fields(
            user_id=current_user.id,
            variable_id=existing_var.id,
            variable=VariableUpdate(id=existing_var.id, name=var_name, value=model_json, type=GENERIC_TYPE),
            session=session,
        )
    except ValueError:
        # Variable not found, create new one
        await variable_service.create_variable(
            user_id=current_user.id,
            name=var_name,
            value=model_json,
            type_=GENERIC_TYPE,
            session=session,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to set default model for user %s",
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to set default model. Please try again later.",
        ) from e

    return {"default_model": model_data}


@router.delete("/default_model", status_code=200)
async def clear_default_model(
    *,
    session: DbSession,
    current_user: CurrentActiveUser,
    model_type: Annotated[str, Query(description="Type of model: 'language' or 'embedding'")] = "language",
):
    """Clear the default model for the current user."""
    # Deleting the default-model Variable is a variable DELETE. Enforce so the
    # external access ceiling caps a "viewer"; the owner with no ceiling
    # fast-paths via owner-override.
    await ensure_variable_permission(
        current_user,
        VariableAction.DELETE,
        variable_user_id=current_user.id,
    )
    variable_service = get_variable_service()
    if not isinstance(variable_service, DatabaseVariableService):
        raise HTTPException(
            status_code=500,
            detail="Variable service is not an instance of DatabaseVariableService",
        )

    var_name = DEFAULT_LANGUAGE_MODEL_VAR if model_type == "language" else DEFAULT_EMBEDDING_MODEL_VAR

    # Log the operation for audit trail
    logger.info(
        "User %s clearing default %s model",
        current_user.id,
        model_type,
    )

    # Check if the variable exists and delete it
    try:
        existing_var = await variable_service.get_variable_object(
            user_id=current_user.id, name=var_name, session=session
        )
        await variable_service.delete_variable(user_id=current_user.id, name=existing_var.name, session=session)
    except ValueError:
        # Variable not found, nothing to delete
        pass
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to clear default model for user %s",
            current_user.id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to clear default model. Please try again later.",
        ) from e

    return {"default_model": None}
