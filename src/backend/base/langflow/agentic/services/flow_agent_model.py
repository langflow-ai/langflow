"""Static detection of Agent nodes that have no model configured.

`Agent has no model selected` only raises when the Agent vertex runs
(``agent.py::get_agent_requirements``). Discovering it that way would
cost a real LLM-less-but-graph run and is fragile. It is, however,
trivially decidable from the flow JSON: an Agent whose ``model`` field
is empty and which has no legacy ``agent_llm``+``model_name`` pair has
no model. This module is the pure decision; it performs no I/O.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from lfx.log.logger import logger

_AGENT_TYPE = "Agent"


class AgentModelOutcome(Enum):
    """Result of trying to make every Agent in a flow have a model."""

    NONE_NEEDED = "none_needed"  # no Agent was missing a model
    ASSIGNED = "assigned"  # the request's model was injected into Agent(s)
    NO_PROVIDER = "no_provider"  # nothing usable — caller delivers a caveat


def _field_value(template: dict[str, Any], name: str) -> Any:
    field = template.get(name)
    return field.get("value") if isinstance(field, dict) else None


def _has_model(template: dict[str, Any]) -> bool:
    """True when the Agent template resolves to a model.

    Either the modern ``model`` field carries a value, or the legacy
    ``agent_llm`` + ``model_name`` pair is fully populated.
    """
    if _field_value(template, "model"):
        return True
    return bool(_field_value(template, "agent_llm")) and bool(_field_value(template, "model_name"))


def find_agents_missing_model(flow: dict[str, Any]) -> list[str]:
    """Return the ids of Agent nodes that have no model configured.

    Args:
        flow: The working-flow dict.

    Returns:
        Node ids (in document order) of every ``Agent`` node that cannot
        resolve a model. Malformed Agent nodes (no template) are flagged
        too — they cannot prove they have one.
    """
    nodes = (flow or {}).get("data", {}).get("nodes", []) or []
    missing: list[str] = []
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_data = node.get("data") or {}
        if node_data.get("type") != _AGENT_TYPE:
            continue
        template = (node_data.get("node") or {}).get("template") or {}
        if _has_model(template):
            continue
        node_id = node.get("id") or node_data.get("id") or ""
        if node_id:
            missing.append(node_id)
    return missing


def ensure_agent_models(
    *,
    flow: dict[str, Any],
    provider: str | None,
    model_name: str | None,
    api_key_var: str | None,
) -> AgentModelOutcome:
    """Make every Agent in ``flow`` have a model, or report it can't.

    No Agent missing a model → ``NONE_NEEDED``. If the request carries a
    usable provider/model (the model the assistant itself ran with), it
    is injected into the model-less Agent node(s) → ``ASSIGNED``.
    Otherwise (no usable model, or an unknown provider) the flow is left
    untouched and ``NO_PROVIDER`` is returned so the caller can deliver
    an honest caveat — this case is NEVER looped on.

    Args:
        flow: The working-flow dict (mutated in place on ASSIGNED).
        provider: The request's provider (e.g. "OpenAI").
        model_name: The request's model name (e.g. "gpt-4o").
        api_key_var: The provider's API-key variable name.

    Returns:
        The :class:`AgentModelOutcome`.
    """
    if not find_agents_missing_model(flow):
        return AgentModelOutcome.NONE_NEEDED
    if not (provider and model_name):
        return AgentModelOutcome.NO_PROVIDER

    # Reuse the existing, deterministic injector (no LLM tokens). An
    # unknown provider raises ValueError — degrade to NO_PROVIDER so a
    # missing model can never explode the build.
    from langflow.agentic.services.flow_preparation import inject_model_into_flow

    try:
        inject_model_into_flow(flow, provider, model_name, api_key_var)
    except ValueError as exc:
        logger.warning("assistant.flow_validation.agent_model_inject_failed provider=%s: %s", provider, exc)
        return AgentModelOutcome.NO_PROVIDER
    return AgentModelOutcome.ASSIGNED
