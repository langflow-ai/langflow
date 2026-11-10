"""The direct OpenDsStar streaming path retains callbacks and its recursion limit."""

from types import SimpleNamespace

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langgraph.graph import END, START, StateGraph
from lfx_bundles.codeagents.open_ds_star_agent import OpenDsStarAgentComponent, OpenDsStarAgentRunnable


@pytest.mark.asyncio
async def test_direct_agent_stream_keeps_workflow_callback(monkeypatch):
    class _RecordingCallback(BaseCallbackHandler):
        def __init__(self):
            self.model_runs = []

        def on_chat_model_start(self, _serialized, _messages, *, run_id, **_kwargs):
            self.model_runs.append(run_id)

    callback = _RecordingCallback()
    model = FakeListChatModel(responses=["fixture answer"])

    def _answer(state, config):
        assert config["recursion_limit"] == 120
        return {"final_answer": model.invoke(state["user_query"]).content}

    graph = StateGraph(dict)
    graph.add_node("answer", _answer)
    graph.add_edge(START, "answer")
    graph.add_edge("answer", END)
    agent = SimpleNamespace(
        _graph=SimpleNamespace(graph=graph.compile(), tools=[]),
        max_steps=12,
        code_mode="stepwise",
        output_max_length=100,
        logs_max_length=100,
        max_debug_tries=1,
    )

    async def _send_message(_self, message, **_kwargs):
        return message

    monkeypatch.setattr(OpenDsStarAgentComponent, "get_langchain_callbacks", lambda _self: [callback])
    monkeypatch.setattr(OpenDsStarAgentComponent, "send_message", _send_message)
    component = OpenDsStarAgentComponent()
    component.input_value = "fixture query"

    result = await component.run_agent(OpenDsStarAgentRunnable(agent))

    assert result.text == "fixture answer"
    assert len(callback.model_runs) == 1
