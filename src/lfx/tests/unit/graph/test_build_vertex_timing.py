"""Tests for per-call vertex build timing in Graph.build_vertex.

Graph.build_vertex records the wall time of every vertex.build call via
vertex.add_build_time (seconds, float), so library callers running async_start
get per-vertex build_times. Server endpoints no longer record separately.
Wall time includes lazy-load and, for concurrent builds on one vertex, the other
call's lock wait: entries are call durations, not pure build-only durations.
"""

import asyncio
import copy
import json
import pickle
from pathlib import Path

import pytest
from lfx.custom.custom_component.component import Component
from lfx.exceptions.component import ComponentBuildError
from lfx.graph import Graph
from lfx.graph.vertex.base import Vertex, VertexStates
from lfx.io import Output
from lfx.schema.data import Data
from lfx.services.cache.utils import CacheMiss


@pytest.fixture
def simple_chat_flow():
    test_data_dir = Path(__file__).parent.parent.parent / "data"
    with (test_data_dir / "simple_chat_no_llm.json").open() as f:
        return json.load(f)


def _dict_cache(store):
    async def get_cache(key):
        return store.get(key, CacheMiss())

    async def set_cache(key, data):
        store[key] = {"result": data}
        return True

    return get_cache, set_cache


async def _run(graph):
    return [r async for r in graph.async_start()]


@pytest.mark.asyncio
async def test_every_built_vertex_records_exactly_one_entry(simple_chat_flow):
    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    await _run(graph)
    built = [v for v in graph.vertices if v.built]
    assert built, "flow should build at least one vertex"
    for vertex in built:
        assert len(vertex.build_times) == 1, f"{vertex.id}: {vertex.build_times}"
        assert isinstance(vertex.build_times[0], float)
        assert vertex.build_times[0] >= 0


@pytest.mark.asyncio
async def test_second_run_accumulates_one_entry_per_call(simple_chat_flow):
    """Repeated async_start on the same (nonfrozen) graph appends per call; vertices are the same objects."""
    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    await _run(graph)
    first_ids = {v.id: id(v) for v in graph.vertices}
    first_counts = {v.id: len(v.build_times) for v in graph.vertices if v.built}
    await _run(graph)
    for vertex in graph.vertices:
        assert id(vertex) == first_ids[vertex.id]
        if vertex.id in first_counts:
            assert len(vertex.build_times) == first_counts[vertex.id] + 1


@pytest.mark.asyncio
async def test_frozen_cache_hit_records_no_entry(simple_chat_flow):
    """Frozen vertex with a real cache hit: no vertex.build call, no new entry."""
    flow = copy.deepcopy(simple_chat_flow)
    for node in flow["data"]["nodes"]:
        node["data"]["node"]["frozen"] = True
    graph = Graph.from_payload(flow)
    await _run(graph)  # first run: real builds, entries recorded (library path has no cache)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    store = {}
    get_cache, set_cache = _dict_cache(store)  # fresh store, single vertex: fully deterministic
    before = len(vertex.build_times)
    # miss: the frozen, already-built vertex still gets a vertex.build call that early-returns,
    # records one (near-zero) entry, and stores the result in the injected cache
    await graph.build_vertex(vertex.id, get_cache=get_cache, set_cache=set_cache)
    assert len(vertex.build_times) == before + 1
    # hit: the cached result is restored; no vertex.build call happens, so no new entry
    await graph.build_vertex(vertex.id, get_cache=get_cache, set_cache=set_cache)
    assert len(vertex.build_times) == before + 1


@pytest.mark.asyncio
async def test_frozen_already_built_cache_miss_records_entry(simple_chat_flow, monkeypatch):
    """Frozen, already-built vertex whose cache misses (CacheMiss keeps built=True).

    vertex.build is still called (spy proves it) and early-returns; the call
    records one nonnegative entry (documented semantics; magnitude is
    timing-dependent and deliberately unasserted).
    """
    flow = copy.deepcopy(simple_chat_flow)
    for node in flow["data"]["nodes"]:
        node["data"]["node"]["frozen"] = True
    graph = Graph.from_payload(flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)
    real_build = vertex.build
    build_calls = 0

    async def counting_build(**kwargs):
        nonlocal build_calls
        build_calls += 1
        return await real_build(**kwargs)

    monkeypatch.setattr(vertex, "build", counting_build)

    async def missing_get_cache(key):  # noqa: ARG001 - cache protocol passes the key
        return CacheMiss()

    await graph.build_vertex(vertex.id, get_cache=missing_get_cache)
    assert build_calls == 1  # the build call happened and early-returned
    assert len(vertex.build_times) == before + 1
    assert vertex.build_times[-1] >= 0


class _FailingComponent(Component):
    display_name = "Failing"
    inputs: list = []
    outputs = [Output(display_name="Out", name="out", method="build_out")]

    def build_out(self):
        msg = "intentional failure"
        raise ValueError(msg)


class _SleepyComponent(Component):
    display_name = "Sleepy"
    inputs: list = []
    outputs = [Output(display_name="Out", name="out", method="build_out")]

    async def build_out(self):
        _SLEEPY_STARTED.set()
        await asyncio.sleep(3600)
        return Data(text="done")


_SLEEPY_STARTED: asyncio.Event


@pytest.mark.asyncio
async def test_cancellation_records_no_entry():
    """CancelledError bypasses the timed entry: a build cancelled mid-call records nothing.

    The start barrier proves the build actually began before cancellation, so the
    empty build_times assertion is not vacuous.
    """
    global _SLEEPY_STARTED  # noqa: PLW0603 - component methods cannot take fixtures
    _SLEEPY_STARTED = asyncio.Event()
    component = _SleepyComponent(_id="sleepy")
    graph = Graph(component, component)
    vertex = graph.get_vertex("sleepy")
    task = asyncio.create_task(_run(graph))
    await asyncio.wait_for(_SLEEPY_STARTED.wait(), timeout=5)
    task.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5)
    except TimeoutError:
        pytest.fail("cancellation did not unwind the build within 5s")
    assert vertex.build_times == []


@pytest.mark.asyncio
async def test_failing_component_records_call_until_failure():
    """A component failure records the call-until-failure elapsed time, then raises."""
    component = _FailingComponent(_id="failing")
    graph = Graph(component, component)
    vertex = graph.get_vertex("failing")
    with pytest.raises(ComponentBuildError, match=r"intentional failure"):
        await _run(graph)
    assert len(vertex.build_times) == 1
    assert vertex.build_times[0] >= 0


@pytest.mark.asyncio
async def test_pickle_round_trip_retains_build_times(simple_chat_flow):
    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    await _run(graph)
    restored = pickle.loads(pickle.dumps(graph))  # noqa: S301 - trusted local round-trip in test
    original = {v.id: v.build_times for v in graph.vertices if v.build_times}
    assert original, "expected recorded entries"
    for vertex in restored.vertices:
        if vertex.id in original:
            assert vertex.build_times == original[vertex.id]


@pytest.mark.asyncio
async def test_inactive_vertex_real_behavior(simple_chat_flow):
    """Pin the real behavior for an INACTIVE vertex through build_vertex.

    build_inactive sets built=True with no result -> the near-zero call entry is recorded,
    then build_vertex raises ValueError for the missing result.
    """
    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    graph.prepare()
    vertex = graph.vertices[0]
    vertex.state = VertexStates.INACTIVE
    with pytest.raises(ValueError, match="no result found"):
        await graph.build_vertex(vertex.id)
    assert len(vertex.build_times) == 1
    assert vertex.build_times[0] >= 0  # near-zero in practice; magnitude is timing-dependent


@pytest.mark.asyncio
async def test_concurrent_same_vertex_builds_record_one_entry_each(simple_chat_flow, monkeypatch):
    """Two concurrent build_vertex calls on the same nonfrozen vertex.

    They serialize on the vertex lock; the counting wrapper proves both calls
    reach vertex.build (real work), and each records exactly one entry. A wall
    time can include the other call's lock wait, as documented in the module docstring.
    """
    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    graph.prepare()
    vertex = graph.vertices[0]
    real_build = vertex.build
    build_calls = 0

    async def counting_build(**kwargs):
        nonlocal build_calls
        build_calls += 1
        return await real_build(**kwargs)

    monkeypatch.setattr(vertex, "build", counting_build)
    await asyncio.gather(graph.build_vertex(vertex.id), graph.build_vertex(vertex.id))
    assert build_calls == 2
    assert len(vertex.build_times) == 2
    assert all(t >= 0 for t in vertex.build_times)
    assert vertex.built


def _frozen_built_vertex(simple_chat_flow):
    """Run a fully frozen flow and return (graph, a built frozen vertex)."""
    flow = copy.deepcopy(simple_chat_flow)
    for node in flow["data"]["nodes"]:
        node["data"]["node"]["frozen"] = True
    return Graph.from_payload(flow)


@pytest.mark.asyncio
async def test_frozen_cache_keyerror_triggers_genuine_rebuild_with_one_entry(simple_chat_flow, monkeypatch):
    """Cached dict missing the "result" key raises KeyError in build_vertex.

    The vertex is reset (built=False) and genuinely rebuilt: the build-call spy
    proves the call arrived with built=False (a frozen early return is impossible),
    and exactly one entry is recorded for that rebuild call.
    """
    graph = _frozen_built_vertex(simple_chat_flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)
    real_build = vertex.build
    build_states = []

    async def observing_build(**kwargs):
        build_states.append(vertex.built)
        return await real_build(**kwargs)

    monkeypatch.setattr(vertex, "build", observing_build)

    async def corrupt_get_cache(key):  # noqa: ARG001 - cache protocol passes the key
        return {"not_the_result_key": {}}

    await graph.build_vertex(vertex.id, get_cache=corrupt_get_cache)
    assert build_states == [False]  # KeyError reset happened before the rebuild call
    assert vertex.built
    assert len(vertex.build_times) == before + 1
    assert vertex.build_times[-1] >= 0


@pytest.mark.asyncio
async def test_frozen_cache_finalize_failure_triggers_genuine_rebuild(simple_chat_flow, monkeypatch):
    """finalize_build raising on a cached restore resets and genuinely rebuilds the vertex.

    The cache is seeded by a real first call (valid hit), then finalize_build fails
    once on the restore path and must succeed inside the genuine rebuild: both
    invocations, the pre-rebuild built=False reset, and the entry count are asserted.
    """
    graph = _frozen_built_vertex(simple_chat_flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)
    store = {}
    get_cache, set_cache = _dict_cache(store)
    await graph.build_vertex(vertex.id, get_cache=get_cache, set_cache=set_cache)  # seeds a valid cache entry
    assert len(vertex.build_times) == before + 1
    original_finalize = vertex.finalize_build
    finalize_calls = 0

    def flaky_finalize():
        nonlocal finalize_calls
        finalize_calls += 1
        if finalize_calls == 1:
            msg = "finalize boom"
            raise RuntimeError(msg)
        return original_finalize()

    real_build = vertex.build
    build_states = []

    async def observing_build(**kwargs):
        build_states.append(vertex.built)
        return await real_build(**kwargs)

    monkeypatch.setattr(vertex, "finalize_build", flaky_finalize)
    monkeypatch.setattr(vertex, "build", observing_build)
    await graph.build_vertex(vertex.id, get_cache=get_cache, set_cache=set_cache)
    assert finalize_calls == 2  # restore attempt raised once; genuine rebuild finalized once
    assert build_states == [False]  # the reset really happened before the rebuild call
    assert vertex.built
    assert len(vertex.build_times) == before + 2  # seed call + rebuild call


@pytest.mark.asyncio
async def test_successful_build_entry_retained_when_set_cache_fails(simple_chat_flow):
    """A successful call records its entry before set_cache runs.

    If set_cache then fails, the error propagates but the recorded entry persists.
    """
    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    graph.prepare()
    vertex = graph.vertices[0]
    assert not vertex.frozen

    async def boom_set_cache(key, data):  # noqa: ARG001 - cache protocol signature
        msg = "cache write down"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="cache write down"):
        await graph.build_vertex(vertex.id, set_cache=boom_set_cache)
    assert vertex.built
    assert len(vertex.build_times) == 1
    assert vertex.build_times[0] >= 0


@pytest.mark.asyncio
async def test_pre_wrap_failure_records_no_entry(simple_chat_flow):
    """Failures before the vertex.build call (here, get_cache raising) record nothing."""
    graph = _frozen_built_vertex(simple_chat_flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)

    async def bad_get_cache(key):  # noqa: ARG001 - cache protocol passes the key
        msg = "cache read failed"
        raise RuntimeError(msg)

    with pytest.raises(RuntimeError, match="cache read failed"):
        await graph.build_vertex(vertex.id, get_cache=bad_get_cache)
    assert len(vertex.build_times) == before


@pytest.mark.asyncio
async def test_pause_safeguard_records_no_entry(simple_chat_flow, monkeypatch):
    """GraphPausedException escaping vertex.build is re-raised untimed.

    vertex.build cannot raise it today (raised only at graph-level boundaries);
    this pins the safeguard so a pause never records a build time.
    """
    from lfx.graph.exceptions import GraphPausedException

    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    graph.prepare()
    vertex = graph.vertices[0]
    before = len(vertex.build_times)

    async def paused_build(**kwargs):  # noqa: ARG001 - mirrors vertex.build signature
        raise GraphPausedException(checkpoint_id="ckpt-test", reason="pause_requested")

    monkeypatch.setattr(vertex, "build", paused_build)
    with pytest.raises(GraphPausedException):
        await graph.build_vertex(vertex.id)
    assert len(vertex.build_times) == before


@pytest.mark.asyncio
async def test_blank_user_id_disables_cache_but_still_records(simple_chat_flow):
    """A blank user_id disables the result cache; the vertex.build call is still timed."""
    graph = _frozen_built_vertex(simple_chat_flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)
    cache_calls = 0

    async def counting_get_cache(key):  # noqa: ARG001 - cache protocol passes the key
        nonlocal cache_calls
        cache_calls += 1
        return CacheMiss()

    await graph.build_vertex(vertex.id, get_cache=counting_get_cache, user_id="   ")
    assert cache_calls == 0  # blank user scope disables the cache
    assert len(vertex.build_times) == before + 1


@pytest.mark.asyncio
async def test_provider_policy_failure_before_timing_records_no_entry(simple_chat_flow, monkeypatch):
    """arequire_model_provider_policy raising on the frozen path is pre-wrap: no entry."""
    graph = _frozen_built_vertex(simple_chat_flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)

    async def denied_policy(user_id=None, event_manager=None):  # noqa: ARG001 - mirrors real signature
        msg = "provider denied"
        raise PermissionError(msg)

    monkeypatch.setattr(vertex, "arequire_model_provider_policy", denied_policy)
    with pytest.raises(PermissionError, match="provider denied"):
        await graph.build_vertex(vertex.id)
    assert len(vertex.build_times) == before


@pytest.mark.asyncio
async def test_frozen_loop_vertex_always_builds_and_records(simple_chat_flow, monkeypatch):
    """Loop components build even when frozen (is_loop branch); the call is timed."""
    graph = _frozen_built_vertex(simple_chat_flow)
    await _run(graph)
    vertex = next(v for v in graph.vertices if v.built and v.frozen)
    before = len(vertex.build_times)
    real_build = vertex.build
    build_calls = 0

    async def counting_build(**kwargs):
        nonlocal build_calls
        build_calls += 1
        return await real_build(**kwargs)

    monkeypatch.setattr(vertex, "build", counting_build)
    # is_loop is a class-level property; patch it on the class for this test only
    monkeypatch.setattr(type(vertex), "is_loop", property(lambda _: True))

    async def hit_get_cache(key):  # noqa: ARG001 - must never be consulted for loops
        msg = "cache consulted on the loop path"
        raise AssertionError(msg)

    await graph.build_vertex(vertex.id, get_cache=hit_get_cache)
    assert build_calls == 1
    assert len(vertex.build_times) == before + 1


@pytest.mark.asyncio
async def test_elapsed_arithmetic_with_deterministic_clock(simple_chat_flow, monkeypatch):
    """Recorded entries equal actual perf_counter deltas, not a constant.

    The fake clock returns 1000.0 once, then 1000.25 forever: build_start reads
    1000.0 and the success read gets 1000.25, so the entry must be exactly 0.25.
    A constant-zero implementation fails this test.
    """
    import itertools

    graph = Graph.from_payload(copy.deepcopy(simple_chat_flow))
    graph.prepare()
    vertex = graph.vertices[0]
    fake = itertools.chain([1000.0], itertools.repeat(1000.25))
    monkeypatch.setattr("time.perf_counter", lambda: next(fake))
    await graph.build_vertex(vertex.id)
    assert vertex.build_times == [0.25]


@pytest.mark.asyncio
@pytest.mark.parametrize("frozen", [False, True])
async def test_real_loop_run_timing_placement(frozen, monkeypatch):
    """Pin real loop timing placement.

    The parent Loop vertex records one entry per run (its call includes the body),
    each body iteration is timed on a DISCARDED per-iteration subgraph, and the
    parent graph's body vertex stays empty: a "3 entries on the parent body
    vertex" expectation would be wrong.
    """
    from tests.unit.components.flow_controls.test_loop_iteration_trigger import _build_item_only_topology

    graph, _loop, _sink = _build_item_only_topology(3)
    if frozen:
        for v in graph.vertices:
            v.frozen = True
    build_calls = {}
    subgraph_entries = {}
    orig_build = Vertex.build
    orig_add = Vertex.add_build_time

    async def counting_build(self, *a, **k):
        build_calls[self.id] = build_calls.get(self.id, 0) + 1
        return await orig_build(self, *a, **k)

    def counting_add(self, t):
        subgraph_entries[self.id] = subgraph_entries.get(self.id, 0) + 1
        return orig_add(self, t)

    monkeypatch.setattr(Vertex, "build", counting_build)
    monkeypatch.setattr(Vertex, "add_build_time", counting_add)
    async for _result in graph.async_start():
        pass
    bt = {v.id: list(v.build_times) for v in graph.vertices}
    assert subgraph_entries.get("ChatOutput-sink") == 3  # one timed build per iteration
    assert len(bt["loop"]) == 1  # parent loop vertex: one entry for its own call
    assert bt["ChatOutput-sink"] == []  # parent body vertex: entries live on discarded subgraphs
    assert all(t >= 0 for ts in bt.values() for t in ts)
