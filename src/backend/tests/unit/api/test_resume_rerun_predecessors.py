"""``_rerun_non_input_predecessors`` (HITL resume): regenerate dropped upstream outputs.

A graph checkpoint cannot serialize non-JSON outputs (Tools, models), so on resume the
paused producer's non-input predecessors must re-run to rebuild valid inputs. Input
vertices (Chat Input) keep their restored value and are not re-run.
"""

from __future__ import annotations

from types import SimpleNamespace

from langflow.api.build import _rerun_non_input_predecessors


def _graph(vertices, predecessor_map):
    by_id = {v.id: v for v in vertices}

    def get_vertex(vid):
        if vid not in by_id:
            raise ValueError(vid)
        return by_id[vid]

    return SimpleNamespace(predecessor_map=predecessor_map, get_vertex=get_vertex)


def _vertex(vid, *, is_input=False, built=True):
    return SimpleNamespace(id=vid, is_input=is_input, built=built)


def test_reruns_non_input_predecessors_and_keeps_inputs_built():
    chat = _vertex("chat", is_input=True)
    tool = _vertex("tool")
    agent = _vertex("agent")
    graph = _graph([chat, tool, agent], {"agent": ["chat", "tool"], "tool": [], "chat": []})

    _rerun_non_input_predecessors(graph, "agent")

    assert tool.built is False  # non-input predecessor (a tool) re-runs
    assert chat.built is True  # input vertex keeps its restored value
    assert agent.built is True  # the paused vertex is un-built by the caller, not here


def test_walks_predecessors_transitively():
    chat = _vertex("chat", is_input=True)
    mid = _vertex("mid")
    tool = _vertex("tool")
    agent = _vertex("agent")
    graph = _graph(
        [chat, mid, tool, agent],
        {"agent": ["tool"], "tool": ["mid"], "mid": ["chat"], "chat": []},
    )

    _rerun_non_input_predecessors(graph, "agent")

    assert tool.built is False
    assert mid.built is False
    assert chat.built is True


def test_no_predecessors_is_a_noop():
    agent = _vertex("agent")
    graph = _graph([agent], {"agent": []})

    _rerun_non_input_predecessors(graph, "agent")

    assert agent.built is True
