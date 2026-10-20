"""Policy and credential boundary shared by decision components and native consumers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest
from lfx.utils.secrets import secret_value_to_str

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.base.models.decisions.schema import DecisionResult


def request_variables_of(component: Any) -> Mapping[str, Any] | None:
    """The caller's per-request variables for this run (X-LANGFLOW-GLOBAL-VAR-* headers), if any."""
    context = getattr(getattr(component, "graph", None), "context", None)
    return context.get("request_variables") if isinstance(context, Mapping) else None


def evaluate_decision(
    request: DecisionRequest,
    *,
    model: list[dict[str, Any]] | dict[str, Any],
    user_id: UUID | str | None = None,
    request_variables: Mapping[str, Any] | None = None,
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
        # A caller's per-request endpoint counts too, so a key meant for a proxy never reaches the hosted API.
        require_official_openai_endpoint(variables, request_variables or {})

    # Only the provider's own credential is used; flows cannot supply or name a key. A caller's
    # per-request value for it (X-LANGFLOW-GLOBAL-VAR-*) comes first, then the provider's configured
    # variable, which also accepts a LANGFLOW_-prefixed environment name.
    own_variable = unified_models.get_provider_secret_variable_key(provider)
    resolved_key = secret_value_to_str((request_variables or {}).get(own_variable), strip=True) or secret_value_to_str(
        variables.get(own_variable), strip=True
    )
    if not resolved_key:
        msg = f"Configure an API key for the {provider} decision model."
        raise DecisionConfigurationError(msg)

    # parse_response already validates the evidence against this request.
    return evaluate_provider(provider, model_name, request, api_key=resolved_key, timeout=timeout)
