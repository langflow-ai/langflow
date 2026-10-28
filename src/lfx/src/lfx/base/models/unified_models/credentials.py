"""Credential resolution and provider validation helpers."""

from __future__ import annotations

import contextlib
import json
import os
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID

from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed
from lfx.log.logger import logger
from lfx.services.deps import get_variable_service, session_scope
from lfx.services.variable import VariableNotFoundError
from lfx.services.variable.request_scope import is_env_fallback_disabled
from lfx.utils.async_helpers import run_until_complete
from lfx.utils.env_var_security import safe_getenv
from lfx.utils.secrets import secret_value_to_str
from lfx.utils.ssrf_protection import validate_connector_url_for_ssrf

from .provider_queries import (
    _canonical_provider_name,
    get_model_provider_variable_mapping,
    get_model_providers,
    get_provider_all_variables,
    get_provider_secret_variable_key,
)

if TYPE_CHECKING:
    from lfx.services.model_provider_policy import ModelProviderPolicySnapshot

MODEL_STATUS_KEY_SEPARATOR = "::"
MODEL_STATUS_TYPES = ("llm", "embeddings", "decision")


def model_status_key(provider: str, model_name: str, model_type: str | None = None) -> str:
    """Return the stable identity used in persisted model-status variables."""
    if model_type is not None:
        if model_type not in MODEL_STATUS_TYPES:
            msg = f"Unsupported model status type: {model_type}"
            raise ValueError(msg)
        return f"{provider}{MODEL_STATUS_KEY_SEPARATOR}{model_type}{MODEL_STATUS_KEY_SEPARATOR}{model_name}"
    return f"{provider}{MODEL_STATUS_KEY_SEPARATOR}{model_name}"


def parse_model_status_key(entry: str) -> tuple[str | None, str, str | None]:
    """Parse a bare, provider-qualified, or typed model-status identity.

    The split is deliberately bounded so deployment names containing ``::``
    survive intact. Legacy provider-qualified entries have no type; only the
    canonical ``llm``, ``embeddings`` and ``decision`` second segments identify typed keys.
    """
    parts = entry.split(MODEL_STATUS_KEY_SEPARATOR, 2)
    match parts:
        case [bare_name]:
            return None, bare_name, None
        case [provider, model_name]:
            return provider, model_name, None
        case [provider, possible_type, remainder]:
            if possible_type in MODEL_STATUS_TYPES:
                return provider, remainder, possible_type
            return provider, f"{possible_type}{MODEL_STATUS_KEY_SEPARATOR}{remainder}", None
    msg = "Model status key could not be parsed"
    raise ValueError(msg)


def model_status_contains(
    entries: set[str],
    provider: str,
    model_name: str,
    model_type: str | None = None,
) -> bool:
    """Check typed status while honoring provider-qualified and bare legacy entries."""
    if model_status_key(provider, model_name) in entries or model_name in entries:
        return True
    if model_type is not None:
        return model_status_key(provider, model_name, model_type) in entries
    return any(
        model_status_key(provider, model_name, candidate_type) in entries for candidate_type in MODEL_STATUS_TYPES
    )


def _get_standalone_variable(name: str) -> str | None:
    """Resolve native LFX request/in-memory variables without opening an owner-scoped DB lookup."""
    from lfx.services.variable.service import VariableService

    service = get_variable_service()
    if type(service) is VariableService:
        return secret_value_to_str(run_until_complete(service.get_variable(name=name)), strip=True)
    return None


def get_api_key_for_provider(user_id: UUID | str | None, provider: str, api_key: Any = None) -> str | None:
    """Get API key from component input or global variables.

    When api_key is set to an environment variable name (e.g. ANTHROPIC_API_KEY),
    that name is resolved from os.environ or global variables so imported flows
    can reference credentials without storing the raw key.
    """
    # SecretStrInput-backed fields arrive as SecretStr to prevent leakage through
    # stringification. Unwrap here because provider clients need the raw value.
    api_key = secret_value_to_str(api_key, strip=True)

    # Resolve variable name (canonical or custom e.g. MY_OPENAI_API_KEY) from
    # global vars or env. The user's per-user, encrypted DB global variable is
    # the source of truth (it's what the Agent component resolves via
    # load_from_db) and MUST win over a process-wide ``.env`` value — otherwise
    # a stale/revoked .env key silently shadows the key the user configured in
    # the UI (and, in multi-tenant deploys, every user shares a server-wide env
    # key). Env is the fallback for the no-user (lfx run) / no-DB-value case.
    def _resolve_var_name(var_name: str) -> str | None:
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
                    except VariableNotFoundError:
                        return None

            value = run_until_complete(_get_by_var_name())
            value = secret_value_to_str(value, strip=True)
            if value:
                return value
        # Honor the request's no-env-fallback contract: skip os.environ when disabled so a
        # served flow stays isolated from process-wide credentials (matches VariableService).
        if not is_env_fallback_disabled():
            # safe_getenv denies reserved names (LANGFLOW_SECRET_KEY, DATABASE_URL, ...) so a
            # tenant-supplied api_key field cannot exfiltrate the server's own secrets via the
            # env fallback (the resolved value is otherwise used as a live provider key).
            env_value = safe_getenv(var_name)
            if env_value and env_value.strip():
                return env_value.strip()
        return None

    if api_key and api_key.strip():
        var_name = api_key.strip()
        # A malformed or legacy component can point its api_key field at any
        # global variable name. Never reinterpret declared non-secret provider
        # configuration (for example, a base URL) as bearer credentials.
        if any(
            variable.get("variable_key") == var_name and not variable.get("is_secret")
            for variable in get_provider_all_variables(provider)
        ):
            return None
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

    # Get primary variable (first required secret) from provider metadata
    variable_name = get_provider_secret_variable_key(provider)
    if not variable_name:
        return None

    # Try the database-backed variable service first when a user_id is available.
    # Fall through to os.environ regardless so lfx run (no user_id) can still pick
    # up canonical credentials from the shell.
    has_user = user_id is not None and not (isinstance(user_id, str) and user_id == "None")
    api_key = None
    if has_user:

        async def _get_variable():
            async with session_scope() as session:
                variable_service = get_variable_service()
                if variable_service is None:
                    return None
                try:
                    return await variable_service.get_variable(
                        user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
                        name=variable_name,
                        field="",
                        session=session,
                    )
                except VariableNotFoundError:
                    return None

        api_key = run_until_complete(_get_variable())
    else:
        api_key = _get_standalone_variable(variable_name)

    api_key = secret_value_to_str(api_key, strip=True)
    if api_key:
        return api_key

    if is_env_fallback_disabled():
        return None
    env_value = safe_getenv(variable_name)
    return env_value.strip() if env_value and env_value.strip() else None


def provider_variable_from_env(var_key: str) -> str | None:
    """Read a provider variable from the environment, accepting a LANGFLOW_ alias.

    The single answer to "what is this provider variable's environment value".
    Live model discovery resolves the same variables, so it shares this helper
    rather than reading ``os.environ`` directly — two readers that disagreed on
    accepted name shapes would leave a provider enabled but undiscoverable.

    Provider keys are conventionally bare (``GOOGLE_API_KEY``), but some .env
    templates prefix everything with ``LANGFLOW_`` (matching how Langflow reads
    its own settings). Accept ``LANGFLOW_<VAR>`` as a fallback so e.g.
    ``LANGFLOW_GOOGLE_API_KEY`` enables Gemini exactly like ``GOOGLE_API_KEY``.
    The bare name keeps precedence — no behavior change when it is set. The
    resolved value is always stored under the bare canonical key by callers, so
    downstream detection (available_model_providers, get_llm) is unaffected.
    """
    value = os.environ.get(var_key)
    if value and value.strip():
        return value
    prefixed = os.environ.get(f"LANGFLOW_{var_key}")
    if prefixed and prefixed.strip():
        return prefixed
    return None


def get_all_variables_for_provider(
    user_id: UUID | str | None, provider: str, *, include_secrets: bool = True
) -> dict[str, str]:
    """Get configured provider variables, optionally resolving only non-secret settings."""
    result: dict[str, str] = {}

    # Get all variable definitions for this provider
    provider_vars = get_provider_all_variables(provider)
    if not include_secrets:
        provider_vars = [variable for variable in provider_vars if not variable.get("is_secret")]
    if not provider_vars:
        return result

    # Native LFX request-scoped variables must win over ambient credentials,
    # including requests with no represented user and no environment fallback.
    if user_id is None or (isinstance(user_id, str) and user_id == "None"):
        for var_info in provider_vars:
            var_key = var_info.get("variable_key")
            if var_key:
                value = _get_standalone_variable(var_key)
                if not value and not is_env_fallback_disabled():
                    value = provider_variable_from_env(var_key)
                if value:
                    result[var_key] = value
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
                    value = secret_value_to_str(value, strip=True)
                    if value:
                        values[var_key] = value
                except VariableNotFoundError:
                    # Variable not found - check environment, unless the request disables
                    # env fallback (keeps served flows isolated from process-wide credentials).
                    if is_env_fallback_disabled():
                        continue
                    env_value = provider_variable_from_env(var_key)
                    if env_value:
                        values[var_key] = env_value

            return values

    db_values = run_until_complete(_get_all_variables())

    # decrypt_api_key swallows Fernet InvalidToken silently and returns "",
    # so a SECRET_KEY rotation leaves required keys missing from db_values
    # even when the env var is set. Mirror get_api_key_for_provider's
    # post-async env fallback so the assistant doesn't reject the request
    # with "Missing required configuration" while the env var is present.
    for var_info in provider_vars:
        var_key = var_info.get("variable_key")
        if not var_key or db_values.get(var_key):
            continue
        # Honor the request's no-env-fallback contract: a served flow under
        # no_env_fallback must stay isolated from process-wide credentials even on
        # this post-DB-miss rotation fallback.
        if is_env_fallback_disabled():
            continue
        env_value = provider_variable_from_env(var_key)
        if env_value:
            db_values[var_key] = env_value

    return db_values


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
    from lfx.base.models.provider_registry import is_api_key_optional

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
            if is_api_key_optional(provider):
                enabled.add(provider)
        elif all_required_present and (collected_values or is_api_key_optional(provider)):
            if skip_validation or not collected_values:
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


def _keeps_model_settings() -> bool:
    """Whether Model Providers settings are saved anywhere.

    Standalone LFX has none: `lfx serve` uses the env-backed VariableService and `lfx run` has no
    variable service at all, only a generated user id. Policy and request-scoped credentials
    still apply there.
    """
    from lfx.services.variable.service import VariableService

    variable_service = get_variable_service()
    return not (variable_service is None or type(variable_service) is VariableService)


async def _get_model_status(user_id: UUID | str, *, strict: bool = False) -> tuple[set[str], set[str]]:
    """Fetch disabled and explicitly enabled model sets for a user.

    Returns:
        A tuple of (disabled_models, explicitly_enabled_models).
    """
    variable_service = get_variable_service()
    # A variable service of any type but standalone LFX's still fails closed below.
    if strict and not _keeps_model_settings():
        return set(), set()
    async with session_scope() as session:
        if variable_service is None:
            return set(), set()
        from langflow.services.variable.service import DatabaseVariableService

        if not isinstance(variable_service, DatabaseVariableService):
            if strict:
                msg = "User model configuration cannot be read from this variable service"
                raise RuntimeError(msg)
            return set(), set()
        all_vars = await variable_service.get_all(
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            session=session,
        )
        disabled: set[str] = set()
        enabled: set[str] = set()
        for var in all_vars:
            if strict and var.name in {"__disabled_models__", "__enabled_models__"}:
                parsed = json.loads(var.value)
                if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
                    msg = "Invalid persisted model enablement configuration"
                    raise ValueError(msg)
                if var.name == "__disabled_models__":
                    disabled = set(parsed)
                else:
                    enabled = set(parsed)
                continue
            if var.name == "__disabled_models__" and var.value:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    disabled = set(json.loads(var.value))
            elif var.name == "__enabled_models__" and var.value:
                with contextlib.suppress(json.JSONDecodeError, TypeError):
                    enabled = set(json.loads(var.value))
        return disabled, enabled


async def _fetch_enabled_providers_for_user(
    user_id: UUID | str,
    *,
    provider_policy: ModelProviderPolicySnapshot | None = None,
) -> set[str]:
    """Return credential-enabled providers allowed for configuration and by the caller."""
    variable_service = get_variable_service()
    if variable_service is None:
        return set()

    from langflow.services.variable.service import DatabaseVariableService

    if not isinstance(variable_service, DatabaseVariableService):
        return set()

    provider_variable_map = get_model_provider_variable_mapping()
    providers = get_model_providers()
    from lfx.services.model_provider_policy import ModelProviderPolicyPurpose, aresolve_model_provider_policy

    configuration_policy = await aresolve_model_provider_policy(
        user_id=user_id,
        providers=providers,
        purpose=ModelProviderPolicyPurpose.CONFIGURE,
        attributes=provider_policy.context.attributes if provider_policy is not None else None,
    )
    from lfx.base.models.provider_registry import is_api_key_optional

    provider_candidates = {
        **provider_variable_map,
        **{
            provider: ""
            for provider in providers
            if provider not in provider_variable_map and is_api_key_optional(provider)
        },
    }
    provider_candidates = {
        provider: variable
        for provider, variable in provider_candidates.items()
        if configuration_policy.allows(provider) and (provider_policy is None or provider_policy.allows(provider))
    }
    if not provider_candidates:
        return set()

    async with session_scope() as session:
        # Get all variable names (VariableRead has value=None for credentials)
        all_vars = await variable_service.get_all(
            user_id=UUID(user_id) if isinstance(user_id, str) else user_id,
            session=session,
        )
        all_var_names = {var.name for var in all_vars}

        # Build dict with raw Variable values (encrypted for secrets, plaintext for others)
        # We need to fetch raw Variable objects because VariableRead has value=None for credentials
        all_provider_variables = {}
        user_id_uuid = UUID(user_id) if isinstance(user_id, str) else user_id

        for provider in provider_candidates:
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
        return _validate_and_get_enabled_providers(all_provider_variables, provider_candidates)


def _is_decision_only_model(provider: str, model_name: str) -> bool:
    """Whether the catalog lists this provider/model as a decision model and not as a chat model."""
    from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED

    if not any(row["provider"] == provider and row["name"] == model_name for row in DECISION_MODELS_DETAILED):
        return False
    from .model_catalog import get_unified_models_detailed

    chat_rows = get_unified_models_detailed(
        providers=[provider], model_type="llm", include_deprecated=True, include_unsupported=True
    )
    return not any(row.get("model_name") == model_name for group in chat_rows for row in group.get("models", []))


def validate_model_provider_key(
    provider: str,
    variables: dict[str, str],
    model_name: str | None = None,
    *,
    model_type: str | None = None,
    user_id: UUID | str | None = None,
    policy_attributes: dict[str, Any] | None = None,
) -> None:
    """Validate a model provider by making a minimal test call."""
    if not provider:
        return

    from lfx.base.models.decision_constants import DECISION_ONLY_PROVIDERS

    # A key gets one billed check, for the kind of model it is about to serve, never one per kind.
    # Decision-only providers (TypeSafe, and Perplexity, whose chat models live in its own component
    # rather than in Model Providers) always get a decision check. A mixed provider such as OpenAI is
    # checked for the kind the caller names: Model Providers asks for "decision" when it was opened
    # from a decision picker and otherwise names none, which means a chat check. Every other kind is
    # checked when it is registered: update_enabled_models validates each model switched on with that
    # model's own type. If Perplexity chat models join Model Providers, Perplexity becomes a mixed
    # provider and follows the same rule.
    # Provider IDs such as "typesafe" and display names reach the same decision checks.
    decision_provider = _canonical_provider_name(provider)
    if model_type is None and model_name and _is_decision_only_model(decision_provider, model_name):
        # An untyped request for a model that exists only as a decision model, such as a legacy
        # status update, must not be validated as a chat completion.
        model_type = "decision"

    from lfx.services.model_provider_policy import ModelProviderPolicyPurpose, resolve_model_provider_policy

    # A check runs a real model, so it needs the same model-level permission as a flow run, for a
    # model the caller names and for one chosen by default.
    policy = resolve_model_provider_policy(
        user_id=user_id,
        providers=[decision_provider],
        purpose=ModelProviderPolicyPurpose.USE,
        attributes=policy_attributes,
    )
    if model_type == "decision" or decision_provider in DECISION_ONLY_PROVIDERS:
        from lfx.base.models.decision_constants import DECISION_MODELS_DETAILED
        from lfx.base.models.decisions.providers import validate_decision_provider_key

        offered = [row["name"] for row in DECISION_MODELS_DETAILED if row["provider"] == decision_provider]
        if not model_name and not offered:
            msg = f"{decision_provider} has no decision models."
            raise ValueError(msg)
        # The caller names the kind, so a name that isn't a catalogued decision model, such as a chat
        # model policy blocks, never reaches a decisions endpoint or gets switched on as one.
        if model_name and model_name not in offered:
            msg = f"{decision_provider} has no decision model by that name."
            raise ValueError(msg)
        # As for chat, the default is the first decision model policy allows, so one blocked model
        # does not stop a key from being saved for the others.
        effective_model = model_name or next(
            (name for name in offered if policy.allows_model(decision_provider, name, model_type="decision")),
            offered[0],
        )
        policy.require_model(decision_provider, effective_model, model_type="decision")
        validate_decision_provider_key(decision_provider, variables, effective_model)
        return

    if model_name:
        policy.require_model(provider, model_name, model_type=model_type)
    # The check below is a chat call, so it only runs a chat model. A model named for another kind,
    # such as an embedding model, was authorized for its own kind above; the key is then checked with
    # the first chat model policy allows, never with that name as a chat model.
    chat_model_name = model_name if model_type in (None, "llm") else None
    first_model = None
    provider_models: list[dict[str, Any]] = []
    try:
        from .model_catalog import get_unified_models_detailed

        models = get_unified_models_detailed(providers=[provider], model_type="llm")
        if models and models[0].get("models"):
            provider_models = models[0]["models"]
            first_model = next(
                (
                    row["model_name"]
                    for row in provider_models
                    if policy.allows_model(provider, row["model_name"], model_type="llm")
                ),
                None,
            )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting unified models for provider {provider}: {e}")

    # WatsonX's static catalog is not region-specific. When no model was
    # requested, select one from the configured endpoint below instead.
    validation_model = chat_model_name if provider == "IBM WatsonX" else chat_model_name or first_model
    validation_metadata = next(
        (model.get("metadata", {}) for model in provider_models if model.get("model_name") == validation_model),
        {},
    )
    is_reasoning_model = validation_metadata.get("reasoning", False) is True

    # Providers contributed by extension bundles validate through their own
    # callable (registered via provider_registry; imported lazily to avoid an
    # import cycle). A registered provider that ships no validator falls through
    # to a no-op generic pass. The callable raises ValueError on failure, which
    # matches this function's contract.
    from lfx.base.models.provider_registry import is_registered, validator_for

    if is_registered(provider):
        bundle_validator = validator_for(provider)
        if bundle_validator is not None:
            try:
                bundle_validator(provider, variables, validation_model)
            except ValueError:
                raise
            except Exception as exc:
                # Normalize bundle/transport errors to this function's ValueError contract.
                msg = f"Could not validate credentials for {provider}: {exc}"
                logger.warning(msg)
                raise ValueError(msg) from exc
        return

    # For providers that need a model to test credentials
    if not validation_model and provider in [
        "OpenAI",
        "Anthropic",
        "Google Generative AI",
    ]:
        return

    try:
        if provider == "OpenAI":
            from langchain_openai import ChatOpenAI  # type: ignore  # noqa: PGH003

            api_key = variables.get("OPENAI_API_KEY")
            if not api_key:
                return
            llm_kwargs = {"api_key": api_key, "model_name": validation_model}
            if not is_reasoning_model:
                llm_kwargs["max_tokens"] = 1
            base_url = variables.get("OPENAI_BASE_URL")
            if base_url:
                from lfx.utils.util import transform_localhost_url

                transformed_base_url = transform_localhost_url(base_url)
                validate_connector_url_for_ssrf(transformed_base_url)
                # A key from the server's environment may only go to OpenAI's own endpoint or an
                # operator-allowlisted host, as for a flow's OpenAI components: a user's saved base URL
                # must not receive it when they switch a model on without a key of their own.
                ensure_credential_endpoint_allowed(
                    api_key, transformed_base_url, default_url="https://api.openai.com/v1"
                )
                llm_kwargs["base_url"] = transformed_base_url
            llm = ChatOpenAI(**llm_kwargs)
            llm.invoke("test")

        elif provider == "Anthropic":
            from langchain_anthropic import ChatAnthropic  # type: ignore  # noqa: PGH003

            api_key = variables.get("ANTHROPIC_API_KEY")
            if not api_key:
                return
            llm = ChatAnthropic(anthropic_api_key=api_key, model=validation_model, max_tokens=1)
            llm.invoke("test")

        elif provider == "Google Generative AI":
            from langchain_google_genai import ChatGoogleGenerativeAI  # type: ignore  # noqa: PGH003

            api_key = variables.get("GOOGLE_API_KEY")
            if not api_key:
                return
            llm = ChatGoogleGenerativeAI(google_api_key=api_key, model=validation_model, max_tokens=1)
            llm.invoke("test")

        elif provider == "IBM WatsonX":
            api_key = variables.get("WATSONX_APIKEY")
            project_id = variables.get("WATSONX_PROJECT_ID")
            url = variables.get("WATSONX_URL") or "https://us-south.ml.cloud.ibm.com"
            if not api_key or not project_id:
                return
            validate_connector_url_for_ssrf(url)

            if not validation_model:
                from lfx.base.models.model_utils import get_watsonx_llm_models

                # Static WatsonX seeds may all be deprecated and filtered out.
                # Use a current regional chat model instead of skipping validation.
                live_models = get_watsonx_llm_models(url, default_models=[])
                validation_model = next(
                    (name for name in live_models if policy.allows_model(provider, name, model_type="llm")), None
                )
                if not validation_model:
                    msg = "No IBM WatsonX chat model is available to validate credentials"
                    logger.warning(msg)
                    raise ValueError(msg)

            from langchain_ibm import ChatWatsonx

            llm = ChatWatsonx(
                apikey=api_key,
                url=url,
                model_id=validation_model,
                project_id=project_id,
                params={"max_new_tokens": 1},
            )
            llm.invoke("test")

        elif provider == "OpenRouter":
            from http import HTTPStatus

            import requests

            api_key = variables.get("OPENROUTER_API_KEY")
            if not api_key:
                return

            # ``/api/v1/models`` is a public OpenRouter endpoint (200 for any
            # bearer, including missing/invalid). Use ``/api/v1/auth/key``
            # instead — it's documented for key validation, returns 401 on
            # invalid keys, and only costs a tiny metadata round-trip.
            try:
                response = requests.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {api_key}"},
                    timeout=5,
                )
                if response.status_code == HTTPStatus.UNAUTHORIZED:
                    msg = "Invalid OpenRouter API key"
                    logger.error(msg)
                    raise ValueError(msg)
                response.raise_for_status()
            except ValueError:
                raise
            except requests.RequestException as e:
                # Network/timeout/5xx during validation: surface as ValueError so
                # the variable API returns a user-facing 400 instead of an
                # unhandled 500 (api/v1/variable.py only catches ValueError).
                msg = f"Could not reach OpenRouter to validate the API key: {e}"
                logger.warning(msg)
                raise ValueError(msg) from e

        elif provider == "Azure AI Foundry":
            try:
                from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
            except ImportError as e:
                msg = (
                    "Azure AI Foundry credential validation requires the "
                    "'langchain-azure-ai' package, but it is not installed."
                )
                raise ValueError(msg) from e

            if AzureAIOpenAIApiChatModel is None:
                msg = "Azure AI Foundry model support is unavailable."
                raise ValueError(msg)

            from lfx.base.models.model_utils import request_azure_ai_foundry_model_entries

            api_key = variables.get("AZURE_AI_FOUNDRY_API_KEY")
            endpoint = variables.get("AZURE_AI_FOUNDRY_ENDPOINT")
            api_version = variables.get("AZURE_AI_FOUNDRY_API_VERSION")
            if not api_key or not endpoint:
                return
            try:
                # Validate connection without requiring a seed catalog model name.
                request_azure_ai_foundry_model_entries(endpoint, api_key, api_version)
            except Exception as e:  # noqa: BLE001 - normalize provider/network failures for the UI
                msg = "Could not validate Azure AI Foundry credentials. Check the endpoint, API key, and network."
                logger.warning(f"{msg} Error type: {type(e).__name__}")
                raise ValueError(msg) from None

        elif provider == "Ollama":
            import requests

            base_url = variables.get("OLLAMA_BASE_URL")
            if not base_url:
                msg = "Invalid Ollama base URL"
                logger.error(msg)
                raise ValueError(msg)

            base_url = base_url.rstrip("/")
            tags_url = f"{base_url}/api/tags"
            # OLLAMA_BASE_URL is tenant-controlled: block SSRF to internal/cloud-metadata hosts.
            validate_connector_url_for_ssrf(tags_url)
            response = requests.get(tags_url, timeout=5, allow_redirects=False)
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
        if provider == "IBM WatsonX":
            msg = f"Could not validate IBM WatsonX credentials: {e}"
            logger.warning(msg)
            raise ValueError(msg) from e

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
