"""``_rerun_non_input_predecessors`` (HITL resume): regenerate only the dropped upstream outputs.

A graph checkpoint cannot serialize non-JSON outputs (Tools, model clients), so on resume the
producers of those — and only those — must re-run to rebuild valid inputs. Producers whose output
round-tripped (e.g. an Agent's Message) keep their restored result, so resume does not re-bill an
LLM call or re-fire side-effecting tools. Input vertices (Chat Input) are never re-run.
"""

from __future__ import annotations

from types import SimpleNamespace

from langflow.api.build import _rerun_non_input_predecessors


def _graph(vertices, predecessor_map, dropped=None):
    by_id = {v.id: v for v in vertices}

    def get_vertex(vid):
        if vid not in by_id:
            raise ValueError(vid)
        return by_id[vid]

    return SimpleNamespace(
        predecessor_map=predecessor_map,
        get_vertex=get_vertex,
        checkpoint_opaque_dropped_ids=set(dropped or set()),
    )


def _vertex(vid, *, is_input=False, built=True):
    return SimpleNamespace(id=vid, is_input=is_input, built=built)


def test_reruns_only_dropped_predecessor_and_keeps_inputs_built():
    chat = _vertex("chat", is_input=True)
    tool = _vertex("tool")
    agent = _vertex("agent")
    # The tool's live output (a Tool object) was opaque-dropped; the agent's Message round-tripped.
    graph = _graph(
        [chat, tool, agent],
        {"agent": ["chat", "tool"], "tool": [], "chat": []},
        dropped={"tool"},
    )

    _rerun_non_input_predecessors(graph, "agent")

    assert tool.built is False  # dropped live output → re-run to regenerate it
    assert chat.built is True  # input vertex keeps its restored value
    assert agent.built is True  # the paused vertex is un-built by the caller, not here


def test_does_not_rerun_producer_whose_output_round_tripped():
    # Agent -> HumanInput: the Agent's output is a serializable Message (not dropped), so resume must
    # NOT re-run it — that would re-bill the LLM call and re-fire any side-effecting tools.
    chat = _vertex("chat", is_input=True)
    agent = _vertex("agent")
    human = _vertex("human")
    graph = _graph(
        [chat, agent, human],
        {"human": ["agent"], "agent": ["chat"], "chat": []},
        dropped=set(),
    )

    _rerun_non_input_predecessors(graph, "human")

    assert agent.built is True  # round-tripped producer is reused, not re-executed
    assert chat.built is True


def test_walks_chain_and_reruns_only_dropped_links():
    # chat(input) -> tool(dropped) -> mid(round-tripped) -> agent(paused). The walk must reach the
    # dropped tool even though the intermediate mid stays built.
    chat = _vertex("chat", is_input=True)
    tool = _vertex("tool")
    mid = _vertex("mid")
    agent = _vertex("agent")
    graph = _graph(
        [chat, mid, tool, agent],
        {"agent": ["mid"], "mid": ["tool"], "tool": ["chat"], "chat": []},
        dropped={"tool"},
    )

    _rerun_non_input_predecessors(graph, "agent")

    assert tool.built is False  # dropped → re-run
    assert mid.built is True  # round-tripped → reused, but the walk passed through it
    assert chat.built is True


def test_no_predecessors_is_a_noop():
    agent = _vertex("agent")
    graph = _graph([agent], {"agent": []}, dropped={"agent"})

    _rerun_non_input_predecessors(graph, "agent")

    assert agent.built is True
