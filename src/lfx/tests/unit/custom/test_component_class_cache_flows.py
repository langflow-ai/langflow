"""Whole-flow isolation for reused component classes.

Prompt Template is the one reviewed component whose fields depend on the flow: each template variable
becomes a per-flow input. These tests build real graphs from payloads, with the cache on, and check that
sharing the class never lets one vertex, graph or user see another's variables.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest
from lfx.base.prompts.api_utils import process_prompt_template
from lfx.components.input_output import ChatOutput
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.custom import class_cache
from lfx.graph.graph.base import Graph
from lfx.interface.components import component_cache
from lfx.utils.flow_validation import _compute_code_hash


def _node(component) -> dict:
    frontend = component.to_frontend_node()
    return {"id": frontend["id"], "data": frontend["data"]}


def _prompt_node(node_id: str, template: str, **values: str) -> dict:
    frontend = PromptComponent(_id=node_id, template=template).to_frontend_node()
    node = frontend["data"]["node"]
    process_prompt_template(
        template=template,
        name="template",
        custom_fields=node.setdefault("custom_fields", {}),
        frontend_node_template=node["template"],
        is_mustache=False,
    )
    node["template"]["template"]["value"] = template
    for name, value in values.items():
        node["template"][name]["value"] = value
    return {"id": frontend["id"], "data": frontend["data"]}


def _edge(source: str, target: str) -> dict:
    return {
        "source": source,
        "target": target,
        "id": f"{source}-{target}",
        "data": {
            "sourceHandle": {"dataType": "x", "id": source, "name": "prompt", "output_types": ["Message"]},
            "targetHandle": {"fieldName": "input_value", "id": target, "inputTypes": ["Message"], "type": "str"},
        },
    }


def _payload(chains: dict[str, tuple[str, dict[str, str]]]) -> dict:
    """One ``Prompt Template -> Chat Output`` chain per entry: ``{prompt_id: (template, values)}``."""
    nodes, edges = [], []
    for prompt_id, (template, values) in chains.items():
        out_id = f"out_{prompt_id}"
        nodes += [_prompt_node(prompt_id, template, **values), _node(ChatOutput(_id=out_id))]
        edges.append(_edge(prompt_id, out_id))
    return {"nodes": nodes, "edges": edges}


async def _run(graph: Graph) -> dict[str, str]:
    """Run the graph and return each Prompt Template vertex's rendered text."""
    graph.prepare()
    async for _ in graph.async_start(inputs={}):
        pass
    return {
        vertex_id: vertex.results["prompt"].text
        for vertex_id, vertex in graph.vertex_map.items()
        if "prompt" in (vertex.results or {})
    }


@pytest.fixture
def cache_on(monkeypatch):
    """Cache on, with the real review and registry gates; the registry holds every source a payload carries."""
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()

    def seed(payload: dict) -> None:
        sources = {n["data"]["node"]["template"]["code"]["value"] for n in payload["nodes"]}
        registry = dict(component_cache.code_by_hash or {})
        registry.update({_compute_code_hash(source): source for source in sources})
        monkeypatch.setattr(component_cache, "code_by_hash", registry)

    yield seed
    class_cache.clear_component_class_cache()
    class_cache.reset_component_class_cache_stats()


def _class_input_names(graph: Graph, vertex_id: str) -> list[str]:
    return [i.name for i in type(graph.get_vertex(vertex_id).custom_component).inputs]


async def test_prompt_vertices_in_one_graph_render_only_their_own_variables(cache_on):
    payload = _payload(
        {
            "p_a": ("Hello {name}", {"name": "Ada"}),
            "p_b": ("Total {amount} {currency}", {"amount": "5", "currency": "EUR"}),
        }
    )
    cache_on(payload)
    graph = Graph.from_payload(payload, flow_id="flow-one")

    shared = type(graph.get_vertex("p_a").custom_component)
    assert type(graph.get_vertex("p_b").custom_component) is shared  # the class really is reused
    assert class_cache.component_class_cache_stats()["hits"] >= 1
    names_before = _class_input_names(graph, "p_a")

    texts = await _run(graph)

    assert texts["p_a"] == "Hello Ada"
    assert texts["p_b"] == "Total 5 EUR"
    assert _class_input_names(graph, "p_a") == _class_input_names(graph, "p_b") == names_before
    assert not {"name", "amount", "currency"} & set(names_before)  # variables never reach the shared class
    first, second = graph.get_vertex("p_a").custom_component, graph.get_vertex("p_b").custom_component
    assert first is not second
    assert first.inputs is not second.inputs


async def test_concurrent_graphs_for_different_users_do_not_share_variables(cache_on):
    alice = _payload({"p": ("Dear {who}, balance {balance}", {"who": "alice", "balance": "100"})})
    bob = _payload({"p": ("Hi {who}", {"who": "bob"})})
    cache_on(alice)
    cache_on(bob)

    graph_a = Graph.from_payload(alice, flow_id="flow-a", user_id="user-a")
    graph_b = Graph.from_payload(bob, flow_id="flow-b", user_id="user-b")
    assert type(graph_a.get_vertex("p").custom_component) is type(graph_b.get_vertex("p").custom_component)
    names_before = _class_input_names(graph_a, "p")

    text_a, text_b = await asyncio.gather(_run(graph_a), _run(graph_b))

    assert text_a["p"] == "Dear alice, balance 100"
    assert text_b["p"] == "Hi bob"
    assert _class_input_names(graph_a, "p") == _class_input_names(graph_b, "p") == names_before
    assert "balance" not in names_before
    assert "balance" not in {i.name for i in graph_b.get_vertex("p").custom_component.inputs}


def test_builds_and_runs_on_separate_threads_stay_isolated(cache_on):
    users = {f"user-{i}": (f"Hi {{who}} #{i}", {"who": f"name{i}"}) for i in range(6)}
    payloads = {user: _payload({"p": chain}) for user, chain in users.items()}
    for payload in payloads.values():
        cache_on(payload)

    def build_and_run(user: str) -> tuple[str, str]:
        graph = Graph.from_payload(payloads[user], flow_id=f"flow-{user}", user_id=user)
        return user, asyncio.run(_run(graph))["p"]

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = dict(pool.map(build_and_run, payloads))

    assert results == {f"user-{i}": f"Hi name{i} #{i}" for i in range(6)}
