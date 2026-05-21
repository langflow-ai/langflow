"""Discover ``CronTrigger`` components inside a flow's saved JSON.

Pure-function module: takes a ``flow.data`` dict, returns dataclasses.
No database, no I/O, no logging. The lifecycle hook and the worker
both call into here so the parsing rules for a node live in exactly
one place.

A trigger ``node`` is recognised by ``node["data"]["type"] ==
"CronTrigger"`` — the immutable class identifier pinned in the
component itself. We never match by node id prefix: that representation
is a frontend detail that could change without warning.

The ``component_id`` we record in ``trigger_job.component_id`` is
``node["id"]`` (e.g. ``"CronTrigger-abc12"``). It stays stable across
saves as long as the canvas does not regenerate the node id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lfx.components.triggers.constants import (
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
    MAX_ATTEMPTS_LIMIT,
)
from lfx.components.triggers.cron_trigger import CronTriggerComponent

# Canonical class identifier — see ``CronTriggerComponent.name``.
# Kept as a module-level constant so search-and-rename tools surface
# every coupling in one shot, and so we can unit-test the link
# between the helper and the component.
CRON_TRIGGER_TYPE: str = CronTriggerComponent.name


@dataclass(frozen=True)
class CronTriggerConfig:
    """Parsed configuration for a single CronTrigger node.

    All attributes have safe defaults: a partially filled node (e.g.
    the user just dropped the component but has not configured it
    yet) still produces a config with sensible fallbacks. The
    ``cron_expression`` default of ``"*/5 * * * *"`` is intentionally
    a valid cron so we never enqueue a job that the worker would
    immediately reject — invalid expressions are caught by the
    scheduler validation in the lifecycle hook, not here.
    """

    component_id: str
    cron_expression: str
    timezone: str
    max_attempts: int


def find_cron_trigger_nodes(flow_data: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return the raw node dicts whose ``data.type`` is ``CronTrigger``.

    Tolerates a ``None`` or missing ``flow_data`` (returns ``[]``) so
    callers do not need to guard around new/empty flows.
    """
    if not flow_data:
        return []
    nodes = flow_data.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [
        node
        for node in nodes
        if isinstance(node, dict)
        and isinstance(node.get("data"), dict)
        and node["data"].get("type") == CRON_TRIGGER_TYPE
    ]


def _read_template_value(template: dict[str, Any], field_name: str, fallback: Any) -> Any:
    """Pull ``template[field_name]['value']`` with a fallback.

    Saved flow templates are dicts of ``{field_name: {'value': ...,
    'type': ..., ...}}``. Missing fields, missing values, and falsy
    values (``None``, empty string) all fall through to ``fallback``.
    """
    field = template.get(field_name)
    if not isinstance(field, dict):
        return fallback
    value = field.get("value")
    if value is None or value == "":
        return fallback
    return value


def _coerce_int(value: Any, fallback: int, *, lo: int, hi: int) -> int:
    """Clamp ``value`` to ``[lo, hi]`` after best-effort int coercion."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return fallback
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


def parse_cron_trigger_config(node: dict[str, Any]) -> CronTriggerConfig:
    """Pull a typed config out of a CronTrigger node dict.

    Defaults applied per-field independently so a partially configured
    node still yields a usable config — the lifecycle hook layer
    decides whether to actually enqueue (it rejects configs whose
    cron expression fails validation).
    """
    component_id = node.get("id", "")
    template = node.get("data", {}).get("node", {}).get("template", {})
    if not isinstance(template, dict):
        template = {}

    return CronTriggerConfig(
        component_id=str(component_id),
        cron_expression=str(
            _read_template_value(template, "cron_expression", DEFAULT_CRON_EXPRESSION)
        ),
        timezone=str(_read_template_value(template, "timezone", DEFAULT_TIMEZONE)),
        max_attempts=_coerce_int(
            _read_template_value(template, "max_attempts", DEFAULT_MAX_ATTEMPTS),
            DEFAULT_MAX_ATTEMPTS,
            lo=1,
            hi=MAX_ATTEMPTS_LIMIT,
        ),
    )


def find_cron_trigger_configs(flow_data: dict[str, Any] | None) -> list[CronTriggerConfig]:
    """Convenience: ``find_cron_trigger_nodes`` + per-node parse.

    Used by the lifecycle hook (full reconciliation per flow save)
    and by the worker (resolve component config at dispatch time).
    """
    return [parse_cron_trigger_config(node) for node in find_cron_trigger_nodes(flow_data)]
