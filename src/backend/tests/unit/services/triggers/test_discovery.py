"""Unit tests for the discovery parser.

Pure functions, no DB. Covers the contract the lifecycle hook and the
worker rely on: ``find_cron_trigger_nodes`` returns the right shape
for the input it gets, and ``parse_cron_trigger_config`` applies the
right defaults when a field is missing or malformed.
"""

from __future__ import annotations

from langflow.services.triggers.discovery import (
    CRON_TRIGGER_TYPE,
    find_cron_trigger_configs,
    find_cron_trigger_nodes,
    parse_cron_trigger_config,
)
from lfx.components.triggers.constants import (
    DEFAULT_CRON_EXPRESSION,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_TIMEZONE,
    MAX_ATTEMPTS_LIMIT,
)


def _make_node(
    component_id: str = "CronTrigger-abc12",
    template: dict | None = None,
    *,
    data_type: str = CRON_TRIGGER_TYPE,
) -> dict:
    return {
        "id": component_id,
        "type": "genericNode",
        "data": {"type": data_type, "node": {"template": template or {}}},
    }


def _wrap(*nodes: dict) -> dict:
    return {"nodes": list(nodes), "edges": []}


# --------------------------------------------------------------------------- #
#  find_cron_trigger_nodes
# --------------------------------------------------------------------------- #


def test_find_returns_empty_for_none_flow_data():
    assert find_cron_trigger_nodes(None) == []


def test_find_returns_empty_for_empty_dict():
    assert find_cron_trigger_nodes({}) == []


def test_find_returns_empty_when_no_cron_nodes_present():
    assert find_cron_trigger_nodes(_wrap(_make_node(data_type="ChatInput"))) == []


def test_find_returns_only_cron_nodes():
    cron = _make_node("CronTrigger-x")
    chat = _make_node("ChatInput-y", data_type="ChatInput")
    other_cron = _make_node("CronTrigger-z")
    found = find_cron_trigger_nodes(_wrap(cron, chat, other_cron))
    ids = [n["id"] for n in found]
    assert ids == ["CronTrigger-x", "CronTrigger-z"]


def test_find_tolerates_malformed_node_entries():
    """Loose validation: ignore non-dict entries inside ``nodes``."""
    flow_data = {"nodes": [None, "bogus", 42, _make_node("CronTrigger-only-survivor")]}
    found = find_cron_trigger_nodes(flow_data)
    assert [n["id"] for n in found] == ["CronTrigger-only-survivor"]


# --------------------------------------------------------------------------- #
#  parse_cron_trigger_config
# --------------------------------------------------------------------------- #


def test_parse_uses_defaults_when_template_is_empty():
    config = parse_cron_trigger_config(_make_node("CronTrigger-zero"))
    assert config.component_id == "CronTrigger-zero"
    assert config.cron_expression == DEFAULT_CRON_EXPRESSION
    assert config.timezone == DEFAULT_TIMEZONE
    assert config.max_attempts == DEFAULT_MAX_ATTEMPTS


def test_parse_reads_provided_values():
    node = _make_node(
        "CronTrigger-set",
        template={
            "cron_expression": {"value": "0 9 * * 1"},
            "timezone": {"value": "America/Sao_Paulo"},
            "max_attempts": {"value": 5},
        },
    )
    config = parse_cron_trigger_config(node)
    assert config.cron_expression == "0 9 * * 1"
    assert config.timezone == "America/Sao_Paulo"
    assert config.max_attempts == 5


def test_parse_clamps_max_attempts_into_range():
    node = _make_node(
        "CronTrigger-out-of-range",
        template={"max_attempts": {"value": 999}},
    )
    assert parse_cron_trigger_config(node).max_attempts == MAX_ATTEMPTS_LIMIT


def test_parse_falls_back_when_max_attempts_is_non_numeric():
    node = _make_node(
        "CronTrigger-bad",
        template={"max_attempts": {"value": "garbage"}},
    )
    assert parse_cron_trigger_config(node).max_attempts == DEFAULT_MAX_ATTEMPTS


def test_parse_treats_empty_string_as_default():
    node = _make_node(
        "CronTrigger-empty",
        template={
            "cron_expression": {"value": ""},
            "timezone": {"value": ""},
        },
    )
    config = parse_cron_trigger_config(node)
    assert config.cron_expression == DEFAULT_CRON_EXPRESSION
    assert config.timezone == DEFAULT_TIMEZONE


# --------------------------------------------------------------------------- #
#  find_cron_trigger_configs (compose)
# --------------------------------------------------------------------------- #


def test_find_configs_returns_one_per_cron_node():
    flow = _wrap(
        _make_node("CronTrigger-a", template={"cron_expression": {"value": "* * * * *"}}),
        _make_node("CronTrigger-b", template={"cron_expression": {"value": "0 0 * * *"}}),
        _make_node("ChatInput-c", data_type="ChatInput"),
    )
    configs = find_cron_trigger_configs(flow)
    by_id = {c.component_id: c.cron_expression for c in configs}
    assert by_id == {"CronTrigger-a": "* * * * *", "CronTrigger-b": "0 0 * * *"}
