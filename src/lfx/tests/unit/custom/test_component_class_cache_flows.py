"""Whole-flow isolation for reused component classes.

Prompt Template is the one reviewed component whose fields depend on the flow. On the ``from_payload`` path its
template variables are not inputs: ``set_attributes`` stores them in each instance's ``_attributes``, which is what
``build_prompt`` renders. These tests build real graphs from payloads, with the cache on, and check that sharing
the class never lets one vertex, graph or user see another's variables, and that nothing is written onto the class.
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from lfx.components.input_output import ChatOutput
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.custom import class_cache
from lfx.graph.graph.base import Graph
from lfx.interface.components import component_cache
from lfx.utils.flow_validation import _compute_code_hash


def _payload(chains: dict[str, tuple[str, dict[str, str]]]) -> dict:
    """One ``Prompt Template -> Chat Output`` chain per entry: ``{prompt_id: (template, values)}``."""
    nodes, edges = [], []
    for prompt_id, (template, values) in chains.items():
        prompt = PromptComponent(_id=prompt_id, template=template).set(**values)
        out = ChatOutput(_id=f"out_{prompt_id}").set(input_value=prompt.build_prompt)
        data = Graph(prompt, out).dump()["data"]
        nodes += data["nodes"]
        edges += data["edges"]
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
def trusted_cache(monkeypatch):
    """Cache on, with the real review and registry gates; the registry holds every source a payload carries."""
    monkeypatch.setattr(class_cache, "_cache_enabled", lambda: True)

    def seed(payload: dict) -> None:
        sources = {n["data"]["node"]["template"]["code"]["value"] for n in payload["nodes"]}
        registry = dict(component_cache.code_by_hash or {})
        registry.update({_compute_code_hash(source): source for source in sources})
        monkeypatch.setattr(component_cache, "code_by_hash", registry)

    return seed


def _prompt(graph: Graph, vertex_id: str = "p"):
    return graph.get_vertex(vertex_id).custom_component


async def test_prompt_vertices_in_one_graph_render_only_their_own_variables(trusted_cache, class_state):
    payload = _payload(
        {
            "p_a": ("Hello {name}", {"name": "Ada"}),
            "p_b": ("Total {amount} {currency}", {"amount": "5", "currency": "EUR"}),
        }
    )
    trusted_cache(payload)
    graph = Graph.from_payload(payload, flow_id="flow-one")

    shared = type(_prompt(graph, "p_a"))
    assert type(_prompt(graph, "p_b")) is shared  # the class really is reused
    assert class_cache.component_class_cache_stats()["hits"] >= 1
    before = class_state(shared)

    texts = await _run(graph)

    assert texts["p_a"] == "Hello Ada"
    assert texts["p_b"] == "Total 5 EUR"
    assert class_state(shared) == before
    first, second = _prompt(graph, "p_a"), _prompt(graph, "p_b")
    assert first is not second
    assert first.inputs is not second.inputs
    assert first._attributes is not second._attributes
    assert "name" not in second._attributes


async def test_concurrent_graphs_for_different_users_do_not_share_variables(trusted_cache, class_state):
    alice = _payload({"p": ("Dear {who}, balance {balance}", {"who": "alice", "balance": "100"})})
    bob = _payload({"p": ("Hi {who}", {"who": "bob"})})
    trusted_cache(alice)
    trusted_cache(bob)

    graph_a = Graph.from_payload(alice, flow_id="flow-a", user_id="user-a")
    graph_b = Graph.from_payload(bob, flow_id="flow-b", user_id="user-b")
    shared = type(_prompt(graph_a))
    assert type(_prompt(graph_b)) is shared
    before = class_state(shared)

    text_a, text_b = await asyncio.gather(_run(graph_a), _run(graph_b))

    assert text_a["p"] == "Dear alice, balance 100"
    assert text_b["p"] == "Hi bob"
    assert class_state(shared) == before
    comp_a, comp_b = _prompt(graph_a), _prompt(graph_b)
    assert comp_a._attributes is not comp_b._attributes
    assert "balance" not in comp_b._attributes


async def test_graph_built_after_another_graph_ran_starts_clean(trusted_cache, class_state):
    alice = _payload({"p": ("Dear {who}, balance {balance}", {"who": "alice", "balance": "100"})})
    bob = _payload({"p": ("Hi {who}", {"who": "bob"})})
    trusted_cache(alice)
    trusted_cache(bob)

    graph_a = Graph.from_payload(alice, flow_id="flow-a", user_id="user-a")
    shared = type(_prompt(graph_a))
    before = class_state(shared)
    assert (await _run(graph_a))["p"] == "Dear alice, balance 100"

    graph_b = Graph.from_payload(bob, flow_id="flow-b", user_id="user-b")
    comp_b = _prompt(graph_b)
    assert type(comp_b) is shared  # built from the class alice's run just used
    assert "balance" not in comp_b._attributes
    assert (await _run(graph_b))["p"] == "Hi bob"
    assert "balance" not in comp_b._attributes
    assert class_state(shared) == before


def test_builds_and_runs_on_separate_threads_stay_isolated(trusted_cache, class_state):
    users = {f"user-{i}": (f"Hi {{who}} #{i}", {"who": f"name{i}"}) for i in range(6)}
    payloads = {user: _payload({"p": chain}) for user, chain in users.items()}
    for payload in payloads.values():
        trusted_cache(payload)
    # Every thread snapshots the class after its build and before any thread runs.
    all_built = threading.Barrier(len(payloads), timeout=60)

    def build_and_run(user: str) -> tuple[str, type, dict, str]:
        graph = Graph.from_payload(payloads[user], flow_id=f"flow-{user}", user_id=user)
        cls = type(_prompt(graph))
        state = class_state(cls)
        all_built.wait()
        return user, cls, state, asyncio.run(_run(graph))["p"]

    with ThreadPoolExecutor(max_workers=len(payloads)) as pool:
        results = list(pool.map(build_and_run, payloads))

    classes = {cls for _, cls, _, _ in results}
    assert len(classes) == 1
    (shared,) = classes
    before = results[0][2]
    assert all(state == before for _, _, state, _ in results)
    assert class_state(shared) == before
    assert {user: text for user, _, _, text in results} == {f"user-{i}": f"Hi name{i} #{i}" for i in range(6)}
