"""Synthesize a CronTrigger canvas node from a user-facing config.

Used by the ``POST /api/v1/triggers`` endpoint to materialise a new
node inside ``flow.data["nodes"]`` without the user having to open the
canvas. The output matches the shape a freshly-dragged node would
have, so the canvas can later render and edit it exactly like any
other node.

The factory leans on Langflow's own ``create_component_template``
helper to produce the canvas-ready template dict — same path the
canvas hits when it asks the backend "what does CronTrigger look
like?". We only override the values the user provided and let
:meth:`CronTriggerComponent.update_build_config` recompute the
derived cron + visibility.

Why the indirection (not building the dict by hand): the template
carries dozens of metadata keys (display_name, info, type, multiline,
trace_*, etc.) per field. Hand-coding that here would fork from the
canonical component definition every time someone touches a field;
calling the same helper the canvas uses keeps both ends in sync by
construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from lfx.components.triggers.cron_trigger import CronTriggerComponent

# Position constants for the freshly-created node. The canvas can
# auto-layout later; this just guarantees the node is somewhere
# visible when the user opens the flow editor.
_DEFAULT_NODE_X = 200.0
_DEFAULT_NODE_Y = 200.0

# Suffix length matching the canvas convention (``CronTrigger-abc12``).
_NODE_ID_SUFFIX_LEN = 5


@dataclass(frozen=True)
class CronTriggerNodeConfig:
    """User-supplied schedule configuration for a new CronTrigger node.

    Mirrors the controls visible on the canvas component, kept as a
    dataclass so the API layer (Pydantic body) maps to this shape one
    field at a time without any name massaging.
    """

    at_specific_time: bool
    interval_value: int
    interval_unit: str  # "minutes" | "hours" — validated upstream
    time_of_day: str
    timezone: str
    max_attempts: int


def _build_template_dict(config: CronTriggerNodeConfig) -> dict[str, Any]:
    """Return the canvas template dict with the user's values applied.

    Steps:

    1. Build a fresh CronTrigger template via the canonical helper.
    2. Override the value of each user-controllable field.
    3. Invoke ``update_build_config`` so the derived cron + visibility
       are computed exactly as they would be after a canvas edit.
    """
    # Local import — ``create_component_template`` pulls a sizeable
    # graph of Langflow internals; deferring it keeps module load
    # cheap when the API layer is not actually creating nodes.
    from lfx.custom.utils import create_component_template

    instance = CronTriggerComponent()
    template, _ = create_component_template(
        component_extractor=instance,
        module_name="lfx.components.triggers.cron_trigger.CronTriggerComponent",
    )

    fields: dict[str, Any] = template.get("template", {})
    # Override user-controllable values. ``cron_expression`` is
    # intentionally omitted here — ``update_build_config`` derives it
    # from the others below.
    _set_if_present(fields, "at_specific_time", config.at_specific_time)
    _set_if_present(fields, "interval_value", config.interval_value)
    _set_if_present(fields, "interval_unit", config.interval_unit)
    _set_if_present(fields, "time_of_day", config.time_of_day)
    _set_if_present(fields, "timezone", config.timezone)
    _set_if_present(fields, "max_attempts", config.max_attempts)

    # Derive cron + apply visibility. The hook reads from ``fields``
    # in-place and writes back ``cron_expression["value"]``.
    instance.update_build_config(
        fields,
        field_value=config.at_specific_time,
        field_name="at_specific_time",
    )
    return template


def _set_if_present(template_fields: dict[str, Any], name: str, value: Any) -> None:
    """Write ``value`` to ``template_fields[name]['value']`` if the field exists."""
    field = template_fields.get(name)
    if isinstance(field, dict):
        field["value"] = value


def build_cron_trigger_node(
    config: CronTriggerNodeConfig,
    *,
    position_x: float = _DEFAULT_NODE_X,
    position_y: float = _DEFAULT_NODE_Y,
) -> dict[str, Any]:
    """Return a full canvas node dict ready to append to ``flow.data['nodes']``.

    The returned shape matches what a CronTrigger node looks like when
    the canvas saves a flow: an outer wrapper with ``id``, ``type``,
    ``position`` and a ``data`` payload containing the typed template.
    """
    template = _build_template_dict(config)
    component_id = f"CronTrigger-{uuid4().hex[:_NODE_ID_SUFFIX_LEN]}"

    return {
        "id": component_id,
        "type": "genericNode",
        "position": {"x": position_x, "y": position_y},
        "data": {
            "id": component_id,
            "type": CronTriggerComponent.name,
            "node": template,
        },
    }


def append_node_to_flow_data(
    flow_data: dict[str, Any] | None,
    node: dict[str, Any],
) -> dict[str, Any]:
    """Return ``flow_data`` with ``node`` appended to its ``nodes`` list.

    Tolerates ``None`` / missing keys: the result is always a dict with
    ``nodes`` and ``edges`` lists, never raising on a fresh flow that
    had ``flow.data = None``.
    """
    base: dict[str, Any] = dict(flow_data) if flow_data else {}
    nodes = list(base.get("nodes") or [])
    edges = list(base.get("edges") or [])
    nodes.append(node)
    base["nodes"] = nodes
    base["edges"] = edges
    return base
