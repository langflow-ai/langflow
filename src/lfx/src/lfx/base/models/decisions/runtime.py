"""Policy and credential boundary shared by decision components and native consumers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest
from lfx.schema.properties import Usage
from lfx.services.variable.request_scope import variable_name_forms
from lfx.utils.secrets import secret_value_to_str

if TYPE_CHECKING:
    from uuid import UUID

    from lfx.base.models.decisions.schema import DecisionResult


def request_variables_of(component: Any) -> Mapping[str, Any] | None:
    """The caller's per-request variables for this run (X-LANGFLOW-GLOBAL-VAR-* headers), if any."""
    context = getattr(getattr(component, "graph", None), "context", None)
    return context.get("request_variables") if isinstance(context, Mapping) else None


def decision_token_usage(result: DecisionResult) -> Usage | None:
    """The tokens a decision used, for the node badge and the Playground; None when the provider sent none."""
    raw = result.usage or {}
    counts = {name: raw.get(name) for name in ("input_tokens", "output_tokens", "total_tokens")}
    # Only whole, non-negative counts: a result built outside parse_response can carry anything.
    counts = {name: value if type(value) is int and value >= 0 else None for name, value in counts.items()}
    if counts["input_tokens"] is None and counts["output_tokens"] is None:
        return None
    if counts["total_tokens"] is None:
        counts["total_tokens"] = (counts["input_tokens"] or 0) + (counts["output_tokens"] or 0)
    return Usage(**counts)


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
            msg = "Pick one Decision Model."
            raise DecisionConfigurationError(msg)
        model = model[0]
    if not isinstance(model, dict):
        msg = "Pick a Decision Model."
        raise DecisionConfigurationError(msg)
    provider, model_name = model.get("provider"), model.get("name")
    if any(not isinstance(value, str) or not value.strip() for value in (provider, model_name)):
        msg = "Pick a Decision Model."
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
        msg = "The Decision Model's provider isn't available here. Pick another Decision Model."
        raise DecisionConfigurationError(msg)
    # Flow-supplied capabilities and endpoints are not authoritative. As for a language model, a run
    # checks policy and the catalog, not Model Providers' on/off switches: those only shape the picker.
    choices = unified_models.get_decision_model_options(provider_policy=policy, require_configured=False)
    selected = next((row for row in choices if row["provider"] == provider and row["name"] == model_name), None)
    if selected is None:
        msg = "The selected Decision Model is no longer offered. Pick another Decision Model."
        raise DecisionConfigurationError(msg)
    if request.kind not in selected.get("metadata", {}).get("capabilities", []):
        msg = (
            f"{model_name} doesn't support the {request.kind.title()} Decision Type. "
            "Pick another Decision Type or Decision Model."
        )
        raise DecisionConfigurationError(msg)

    from lfx.base.models.decisions.providers import evaluate_provider, require_official_openai_endpoint

    # Only the provider's own credential is used; flows cannot supply or name a key. A caller's
    # per-request value for it comes first, in any form a request sends it (X-LANGFLOW-GLOBAL-VAR-*
    # headers arrive dashed, lfx serve keeps x-langflow-global-var-* aliases), then the provider's
    # configured variable, which also accepts a LANGFLOW_-prefixed environment name.
    own_variable = unified_models.get_provider_secret_variable_key(provider)
    requested = request_variables or {}
    requested_key = next(
        (
            key
            for name in variable_name_forms(own_variable)
            if (key := secret_value_to_str(requested.get(name), strip=True))
        ),
        None,
    )
    variables = unified_models.get_all_variables_for_provider(user_id, provider, include_secrets=requested_key is None)
    if provider == "OpenAI":
        # Saved settings still constrain request keys, even when stored as Credential variables.
        require_official_openai_endpoint(variables, requested)
    resolved_key = requested_key or secret_value_to_str(variables.get(own_variable), strip=True)
    if not resolved_key:
        msg = f"Add the {provider} API key in Model Providers, or set {own_variable}."
        raise DecisionConfigurationError(msg)

    # parse_response already validates the evidence against this request.
    return evaluate_provider(provider, model_name, request, api_key=resolved_key, timeout=timeout)
