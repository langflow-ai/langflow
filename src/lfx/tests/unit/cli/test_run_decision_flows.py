"""``lfx run`` executes decision flows end to end: the shipped starter, every provider, every type.

Only the provider's HTTP endpoint is faked (see ``decision_wire``). The flow file, graph engine, Smart
Router, branch exclusion and Chat Output all run as they do for a user running a downloaded flow.
"""

import asyncio
import copy
import json

import pytest
from lfx.__main__ import app
from lfx.components.llm_operations.llm_conditional_router import SmartRouterComponent
from lfx.schema.dotdict import dotdict
from typer.testing import CliRunner

from tests.unit.base.models import decision_wire
from tests.unit.base.models.decision_wire import (
    PROVIDERS,
    distribution,
    probability_true,
    selected_model,
    status,
)
from tests.unit.cli.test_run_starter_projects import get_starter_projects_path

runner = CliRunner()
STARTER = "Support Ticket Routing.json"
ROUTER = "SmartRouter-4d826"
# The starter's Chat Output for each route, in route order, and the one its Else prompt feeds.
ROUTE_OUTPUTS = ["ChatOutput-27006", "ChatOutput-450f9", "ChatOutput-f0150"]
ELSE_OUTPUT = "ChatOutput-3cacd"
MESSAGE = "I was charged twice for my plan."


@pytest.fixture
def decision_endpoint(monkeypatch):
    return decision_wire.install(monkeypatch)


@pytest.fixture(autouse=True)
def allow_standard_cli_flow_execution(monkeypatch):
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "allow_custom_components", True)


@pytest.fixture
def starter():
    return json.loads((get_starter_projects_path() / STARTER).read_text(encoding="utf-8"))


def _router_node(flow):
    return next(node for node in flow["data"]["nodes"] if node["id"] == ROUTER)


def _configure(flow, **values):
    template = _router_node(flow)["data"]["node"]["template"]
    for name, value in values.items():
        template[name]["value"] = value
    return flow


def _switch_type(flow, kind):
    """Change Decision Type as the editor does: refresh the fields and outputs, then reconnect by position.

    The editor drops a type's old edges; a user reconnects the new outputs. Here each new output takes the
    old one's place, so the same Chat Outputs show which branch ran.
    """
    node = _router_node(flow)["data"]["node"]
    node["template"]["decision_kind"]["value"] = kind
    # The update endpoint builds the component from the saved values before asking it for fields.
    router = SmartRouterComponent()
    router.set(routing_mode=node["template"]["routing_mode"]["value"], decision_kind=kind)
    build_config = router.update_build_config(dotdict(node["template"]), kind, "decision_kind")
    node["template"] = dict(build_config)
    old = [output["name"] for output in node["outputs"] if output["name"] != "default_result"]
    # The editor's update endpoint refreshes outputs through this, which also types them.
    refreshed = asyncio.run(router.run_and_validate_update_outputs(copy.deepcopy(node), "decision_kind", kind))
    node["outputs"] = refreshed["outputs"]
    new = [output["name"] for output in node["outputs"] if output["name"] != "default_result"]
    renamed = dict(zip(old, new, strict=False))
    kept = []
    for edge in flow["data"]["edges"]:
        name = edge["data"]["sourceHandle"]["name"] if edge["source"] == ROUTER else None
        if name in renamed:
            reconnected = json.loads(json.dumps(edge).replace(f"œ{name}œ", f"œ{renamed[name]}œ"))
            reconnected["data"]["sourceHandle"]["name"] = renamed[name]
            kept.append(reconnected)
        elif name is None or name == "default_result":
            kept.append(edge)
        # Any other edge leaves an output the new type doesn't have, such as a third route for Boolean.
    flow["data"]["edges"] = kept
    return flow


def _run(tmp_path, flow, message=MESSAGE):
    path = tmp_path / "flow.json"
    path.write_text(json.dumps(flow), encoding="utf-8")
    result = runner.invoke(app, ["run", "--no-check-variables", str(path), message])
    return result, json.loads(result.stdout) if result.stdout.strip().startswith("{") else None


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("route", [0, 1, 2])
def test_the_starter_routes_each_message_to_one_branch(decision_endpoint, tmp_path, starter, provider, route):
    probabilities = [0.05, 0.05, 0.05]
    probabilities[route] = 0.9
    decision_endpoint.answer(distribution(*probabilities))

    result, output = _run(tmp_path, _configure(starter, decision_model=selected_model(provider)))

    assert result.exit_code == 0, result.output
    assert output["success"] is True
    assert output["component_id"] == ROUTE_OUTPUTS[route]
    assert len(decision_endpoint.calls) == 1


@pytest.mark.parametrize("provider", PROVIDERS)
def test_an_unsure_answer_reaches_the_starters_else_branch(decision_endpoint, tmp_path, starter, provider):
    decision_endpoint.answer(distribution(0.5, 0.3, 0.2))

    result, output = _run(tmp_path, _configure(starter, decision_model=selected_model(provider)))

    assert result.exit_code == 0, result.output
    assert output["component_id"] == ELSE_OUTPUT


@pytest.mark.parametrize("provider", PROVIDERS)
def test_the_starter_stops_on_a_provider_error(decision_endpoint, tmp_path, starter, provider):
    """The starter ships with Stop with error, so an outage never reaches a customer as a routed reply."""
    decision_endpoint.answer(status(503))

    result, output = _run(tmp_path, _configure(starter, decision_model=selected_model(provider)))

    assert result.exit_code != 0 or (output and output["success"] is False), result.output
    assert "server problem" in result.output


@pytest.mark.parametrize("provider", PROVIDERS)
def test_route_to_else_sends_a_provider_error_to_else(decision_endpoint, tmp_path, starter, provider):
    decision_endpoint.answer(status(503))
    flow = _configure(starter, decision_model=selected_model(provider), evaluation_error_action="Route to Else")

    result, output = _run(tmp_path, flow)

    assert result.exit_code == 0, result.output
    assert output["component_id"] == ELSE_OUTPUT


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(("p", "branch"), [(0.9, 0), (0.1, 1), (0.5, None)])
def test_a_boolean_router_runs_its_yes_no_and_else_branches(decision_endpoint, tmp_path, starter, provider, p, branch):
    flow = _switch_type(starter, "Boolean")
    _configure(flow, decision_model=selected_model(provider), decision_question="Is this about a payment?")
    decision_endpoint.answer(probability_true(p))

    result, output = _run(tmp_path, flow)

    assert result.exit_code == 0, result.output
    assert output["component_id"] == (ELSE_OUTPUT if branch is None else ROUTE_OUTPUTS[branch])


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize(("probabilities", "level"), [((0.8, 0.1, 0.1), 0), ((0.1, 0.1, 0.8), 2)])
def test_a_score_router_runs_the_level_its_score_rounds_to(
    decision_endpoint, tmp_path, starter, provider, probabilities, level
):
    flow = _switch_type(starter, "Score")
    _configure(flow, decision_model=selected_model(provider), decision_question="How urgent is this message?")
    decision_endpoint.answer(distribution(*probabilities))

    result, output = _run(tmp_path, flow)

    assert result.exit_code == 0, result.output
    assert output["component_id"] == ROUTE_OUTPUTS[level]


def test_a_downloaded_starter_runs_with_code_as_lines(decision_endpoint, tmp_path, starter):
    """Export writes code as a list of lines; the exported file must run unchanged."""
    for node in starter["data"]["nodes"]:
        for field in node["data"].get("node", {}).get("template", {}).values():
            if isinstance(field, dict) and field.get("type") == "code" and isinstance(field.get("value"), str):
                field["value"] = field["value"].split("\n")
    decision_endpoint.answer(distribution(0.9, 0.05, 0.05))

    result, output = _run(tmp_path, starter)

    assert result.exit_code == 0, result.output
    assert output["component_id"] == ROUTE_OUTPUTS[0]
