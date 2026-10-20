"""Policy and credential boundary shared by decision components and native consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.base.models.decisions.schema import DecisionResult


def evaluate_decision(
    request: DecisionRequest,
    *,
    model: list[dict[str, Any]] | dict[str, Any],
    user_id: UUID | str | None = None,
    timeout: float = 60,
) -> DecisionResult:
    """Authorize the canonical catalog identity before resolving credentials or invoking HTTP."""
    if isinstance(model, list):
        if len(model) != 1:
            msg = "Select exactly one decision model."
            raise DecisionConfigurationError(msg)
        model = model[0]
    if not isinstance(model, dict):
        msg = "A decision model selection is required."
        raise DecisionConfigurationError(msg)
    provider, model_name = model.get("provider"), model.get("name")
    if any(not isinstance(value, str) or not value.strip() for value in (provider, model_name)):
        msg = "The decision model selection requires a provider and model name."
        raise DecisionConfigurationError(msg)

    from lfx.services.model_provider_policy import ModelProviderPolicyPurpose, resolve_model_provider_policy

    policy = resolve_model_provider_policy(
        user_id=user_id, providers=[provider], purpose=ModelProviderPolicyPurpose.USE
    )
    policy.require_model(provider, model_name, model_type="decision")

    from lfx.base.models import unified_models
    from lfx.base.models.provider_registry import provider_name_for_id, resolve_provider_id

    provider = provider_name_for_id(resolve_provider_id(provider))
    if provider is None:
        msg = "The decision provider is not registered."
        raise DecisionConfigurationError(msg)
    # Flow-supplied capabilities and endpoints are not authoritative.
    choices = unified_models.get_decision_model_options(
        user_id=user_id, provider_policy=policy, require_configured=False
    )
    selected = next((row for row in choices if row["provider"] == provider and row["name"] == model_name), None)
    if selected is None:
        msg = "The selected decision model is disabled or unavailable."
        raise DecisionConfigurationError(msg)
    if request.kind not in selected.get("metadata", {}).get("capabilities", []):
        msg = "The selected decision model does not support this question kind."
        raise DecisionConfigurationError(msg)

    from lfx.base.models.decisions.providers import evaluate_provider, require_official_openai_endpoint

    variables = unified_models.get_all_variables_for_provider(user_id, provider)
    if provider == "OpenAI":
        from lfx.base.models.unified_models.credentials import provider_variable_from_env
        from lfx.services.variable.request_scope import is_env_fallback_disabled

        if not is_env_fallback_disabled() and "OPENAI_API_BASE" not in variables:
            variables["OPENAI_API_BASE"] = provider_variable_from_env("OPENAI_API_BASE")
        require_official_openai_endpoint(variables)
    # Only the provider's own credential is used; flows cannot supply or name a key.
    resolved_key = unified_models.get_api_key_for_provider(user_id, provider)
    if not resolved_key:
        msg = f"Configure an API key for the {provider} decision model."
        raise DecisionConfigurationError(msg)

    # parse_response already validates the evidence against this request.
    return evaluate_provider(provider, model_name, request, api_key=resolved_key, timeout=timeout)
