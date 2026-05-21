"""Unit tests for the node factory used by ``POST /api/v1/triggers``.

The factory leans on ``create_component_template`` from Langflow to
build a canvas-shaped template dict, then patches the user-supplied
values in. These tests guard the contract the API endpoint and the
lifecycle hook rely on:

  * Node id prefix matches the discovery matcher.
  * ``data.type`` is the immutable ``CronTrigger`` identifier.
  * Template field values reflect what the caller asked for.
  * ``cron_expression`` is derived correctly for both branches of the
    schedule toggle.
  * ``append_node_to_flow_data`` works on empty / missing / full
    inputs without raising.
"""

from __future__ import annotations

from langflow.services.triggers.discovery import (
    find_cron_trigger_configs,
    find_cron_trigger_nodes,
)
from langflow.services.triggers.node_factory import (
    CronTriggerNodeConfig,
    append_node_to_flow_data,
    build_cron_trigger_node,
)


def _config(
    *,
    at_specific_time: bool = False,
    interval_value: int = 5,
    interval_unit: str = "minutes",
    time_of_day: str = "09:00",
    timezone: str = "UTC",
    max_attempts: int = 3,
) -> CronTriggerNodeConfig:
    return CronTriggerNodeConfig(
        at_specific_time=at_specific_time,
        interval_value=interval_value,
        interval_unit=interval_unit,
        time_of_day=time_of_day,
        timezone=timezone,
        max_attempts=max_attempts,
    )


# --------------------------------------------------------------------------- #
#  build_cron_trigger_node
# --------------------------------------------------------------------------- #


def test_node_id_uses_cron_trigger_prefix():
    """Node id prefix must match the canvas convention.

    The backend discovery keys on ``data.type``, but any hand-grep
    against ``flow.data`` looks for ``"CronTrigger-"`` literal; both
    contracts must hit the same string.
    """
    node = build_cron_trigger_node(_config())
    assert node["id"].startswith("CronTrigger-")


def test_node_data_type_is_immutable_identifier():
    node = build_cron_trigger_node(_config())
    assert node["data"]["type"] == "CronTrigger"
    # data.id mirrors the outer id — canvas relies on the duplication.
    assert node["data"]["id"] == node["id"]


def test_node_position_defaults_visible():
    """Default position must be on the visible canvas area, not 0,0."""
    node = build_cron_trigger_node(_config())
    assert node["position"]["x"] > 0
    assert node["position"]["y"] > 0


def test_interval_minutes_node_has_minutes_cron():
    node = build_cron_trigger_node(_config(interval_value=10, interval_unit="minutes"))
    template = node["data"]["node"]["template"]
    assert template["interval_value"]["value"] == 10
    assert template["interval_unit"]["value"] == "minutes"
    assert template["at_specific_time"]["value"] is False
    assert template["cron_expression"]["value"] == "*/10 * * * *"


def test_interval_hours_node_has_hour_cron():
    node = build_cron_trigger_node(_config(interval_value=3, interval_unit="hours"))
    template = node["data"]["node"]["template"]
    assert template["cron_expression"]["value"] == "0 */3 * * *"


def test_specific_time_node_has_time_of_day_cron():
    node = build_cron_trigger_node(
        _config(at_specific_time=True, time_of_day="14:30", timezone="America/Sao_Paulo"),
    )
    template = node["data"]["node"]["template"]
    assert template["at_specific_time"]["value"] is True
    assert template["time_of_day"]["value"] == "14:30"
    assert template["timezone"]["value"] == "America/Sao_Paulo"
    assert template["cron_expression"]["value"] == "30 14 * * *"


def test_node_is_picked_up_by_discovery_unchanged():
    """A fresh factory node must round-trip through discovery.

    This is the integration guarantee: if the discovery helper does
    not see a CronTrigger node minted by the factory, the worker
    never fires it.
    """
    node = build_cron_trigger_node(_config(interval_value=7))
    flow_data = {"nodes": [node], "edges": []}
    nodes = find_cron_trigger_nodes(flow_data)
    assert len(nodes) == 1
    configs = find_cron_trigger_configs(flow_data)
    assert len(configs) == 1
    assert configs[0].cron_expression == "*/7 * * * *"


def test_max_attempts_value_propagates_to_template():
    node = build_cron_trigger_node(_config(max_attempts=7))
    template = node["data"]["node"]["template"]
    assert template["max_attempts"]["value"] == 7


# --------------------------------------------------------------------------- #
#  append_node_to_flow_data
# --------------------------------------------------------------------------- #


def test_append_to_none_flow_data_initialises_lists():
    node = build_cron_trigger_node(_config())
    result = append_node_to_flow_data(None, node)
    assert result["nodes"] == [node]
    assert result["edges"] == []


def test_append_to_empty_flow_data_initialises_lists():
    node = build_cron_trigger_node(_config())
    result = append_node_to_flow_data({}, node)
    assert result["nodes"] == [node]
    assert result["edges"] == []


def test_append_preserves_existing_nodes_and_edges():
    existing_node = {"id": "ChatInput-x", "data": {"type": "ChatInput"}}
    existing_edge = {"source": "ChatInput-x", "target": "ChatOutput-y"}
    flow_data = {"nodes": [existing_node], "edges": [existing_edge]}

    new_node = build_cron_trigger_node(_config())
    result = append_node_to_flow_data(flow_data, new_node)
    assert result["nodes"] == [existing_node, new_node]
    assert result["edges"] == [existing_edge]


def test_append_does_not_mutate_input():
    flow_data = {"nodes": [], "edges": []}
    snapshot_nodes = flow_data["nodes"]
    snapshot_edges = flow_data["edges"]
    new_node = build_cron_trigger_node(_config())
    append_node_to_flow_data(flow_data, new_node)
    # The original lists must be untouched (factory returns a fresh dict).
    assert snapshot_nodes == []
    assert snapshot_edges == []
