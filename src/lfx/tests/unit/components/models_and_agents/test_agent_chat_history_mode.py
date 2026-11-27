"""Agent "Chat History Mode": Last N stays as it was; Auto reads session memory and folds beside the run."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from lfx.base.memory.session_memory import AutoHistory, Budget
from lfx.components.models_and_agents import agent as agent_module
from lfx.components.models_and_agents.agent import CHAT_HISTORY_AUTO, CHAT_HISTORY_LAST_N, AgentComponent
from lfx.components.models_and_agents.agent_helpers.in_run_compaction_middleware import InRunCompactionMiddleware
from lfx.components.models_and_agents.agent_helpers.tool_result_cap_middleware import ToolResultCapMiddleware
from lfx.memory.session_state import SessionMemoryState
from lfx.schema.message import Message
from lfx.schema.properties import Usage
from lfx.utils.constants import MESSAGE_SENDER_USER


def _component(mode: str) -> AgentComponent:
    component = AgentComponent()
    component._user_id = None
    component.set_attributes(
        {
            "model": "fake-model",
            "tools": [],
            "chat_history": [],
            "input_value": Message(text="now", sender=MESSAGE_SENDER_USER, id=uuid.uuid4()),
            "chat_history_mode": mode,
            "n_messages": 100,
            "context_id": "",
        }
    )
    component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id="s", flow_id=None, user_id=None))
    return component


def _llm(window: int | None):
    return SimpleNamespace(profile={"max_input_tokens": window} if window else None)


async def _history(component, *, loaded=None, window=128_000):
    prior = Message(text="earlier", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())
    with (
        patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=[prior])) as last_n,
        patch.object(agent_module, "load_auto_history", new=AsyncMock(return_value=loaded)) as load,
        patch.object(agent_module, "should_persist_messages", return_value=True),
    ):
        result = await component._history_for_turn(_llm(window))
    return result, last_n, load


async def test_last_n_mode_reads_only_the_last_n_messages():
    result, last_n, load = await _history(_component(CHAT_HISTORY_LAST_N))
    assert [m.text for m in result] == ["earlier"]
    last_n.assert_awaited_once()
    load.assert_not_called()


async def test_auto_mode_reads_session_memory_with_the_budget_of_the_model_window():
    notes = Message(text="Background notes from earlier in this conversation: x", sender=MESSAGE_SENDER_USER)
    loaded = AutoHistory(history=[notes], state=SessionMemoryState())
    result, last_n, load = await _history(_component(CHAT_HISTORY_AUTO), loaded=loaded, window=32_000)
    assert result == [notes]
    last_n.assert_not_called()
    assert load.call_args.kwargs["budget"] == Budget(high=6_400, low=3_200)


async def test_auto_mode_falls_back_to_last_n_without_session_memory():
    result, last_n, _ = await _history(_component(CHAT_HISTORY_AUTO), loaded=None)
    assert [m.text for m in result] == ["earlier"]
    last_n.assert_awaited_once()


async def test_auto_mode_loads_once_per_input_and_folds_beside_the_run():
    component = _component(CHAT_HISTORY_AUTO)
    batch = [Message(text="old", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())]
    loaded = AutoHistory(history=[], state=SessionMemoryState(), fold_batch=batch)
    release = asyncio.Event()
    started = []

    async def slow_fold(**kwargs):
        started.append(kwargs["batch"])
        await release.wait()

    with patch.object(agent_module, "fold", new=slow_fold):
        _, _, load = await _history(component, loaded=loaded)
        with (
            patch.object(agent_module, "load_auto_history", new=load),
            patch.object(agent_module, "should_persist_messages", return_value=True),
        ):
            await component._history_for_turn(_llm(128_000))  # memo hit
        assert load.await_count == 1
        component._start_fold()
        component._start_fold()  # no-op while one is pending
        await asyncio.sleep(0)
        assert started == [batch]
        assert not component._fold_task.done()
        release.set()
        await component._settle_fold()
    assert component._fold_task is None


async def test_settle_adds_fold_usage_to_the_run_usage():
    component = _component(CHAT_HISTORY_AUTO)
    component._token_usage = Usage(input_tokens=10, output_tokens=5, total_tokens=15)
    component._fold_usage_handler = MagicMock(
        get_usage=MagicMock(return_value=Usage(input_tokens=3, output_tokens=1, total_tokens=4))
    )
    component._fold_task = asyncio.create_task(asyncio.sleep(0))
    await component._settle_fold()
    assert component._token_usage == Usage(input_tokens=13, output_tokens=6, total_tokens=19)


def test_tool_result_cap_is_added_only_in_auto_mode():
    for mode, expected in ((CHAT_HISTORY_LAST_N, False), (CHAT_HISTORY_AUTO, True)):
        component = _component(mode)
        component.tools = [MagicMock(name="tool")]
        middleware = component._build_middleware(MagicMock())
        assert any(isinstance(m, ToolResultCapMiddleware) for m in middleware) is expected


class FakeChatWatsonx(FakeMessagesListChatModel):
    """Named like ChatWatsonx, so `is_watsonx_model` adds the two WatsonX middleware."""

    def bind_tools(self, _tools, **_kwargs):  # type: ignore[override]
        return self


@tool
def lookup(query: str) -> str:
    """Look something up."""
    return f"result for {query}"


def test_compaction_is_added_only_in_auto_mode_with_a_known_window():
    for mode, window, expected in (
        (CHAT_HISTORY_LAST_N, 128_000, False),
        (CHAT_HISTORY_AUTO, None, False),
        (CHAT_HISTORY_AUTO, 128_000, True),
    ):
        component = _component(mode)
        component._get_llm = lambda **_kwargs: FakeMessagesListChatModel(responses=[])
        middleware = component._build_middleware(_llm(window))
        assert any(isinstance(m, InRunCompactionMiddleware) for m in middleware) is expected


def test_window_falls_back_to_the_catalog_metadata_of_the_selected_model():
    component = _component(CHAT_HISTORY_AUTO)
    component.model = [{"name": "granite", "provider": "IBM watsonx.ai", "metadata": {"context_window": 131_072}}]
    assert component._model_window(_llm(None)) == 131_072


async def test_watsonx_middleware_run_together_with_compaction():
    component = _component(CHAT_HISTORY_AUTO)
    component.tools = [lookup]
    component._get_llm = lambda **_kwargs: FakeMessagesListChatModel(responses=[AIMessage(content="summary")])
    model = FakeChatWatsonx(
        responses=[
            AIMessage(
                content="", tool_calls=[{"id": "c1", "name": "lookup", "args": {"query": "q"}, "type": "tool_call"}]
            ),
            AIMessage(content="answer"),
        ]
    )
    model.profile = {"max_input_tokens": 128_000}
    middleware = component._build_middleware(model)
    names = [type(m).__name__ for m in middleware]
    assert names.index("WatsonXPlaceholderMiddleware") < names.index("InRunCompactionMiddleware")

    state = await create_agent(model=model, tools=[lookup], middleware=middleware).ainvoke(
        {"messages": [("user", "go")]}
    )
    assert state["messages"][-1].content == "answer"


async def test_fold_event_shows_while_the_answer_streams_and_ends_done_or_failed():
    for saved, expected in ((SessionMemoryState(version=1), "done"), (None, "failed")):
        component = _component(CHAT_HISTORY_AUTO)
        batch = [Message(text="old", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())]
        component._staged_fold = {"scope": {}, "state": SessionMemoryState(), "batch": batch}

        async def finished_fold(result=saved, **_kwargs):
            return result

        with patch.object(agent_module, "fold", new=finished_fold):
            component._start_fold()
        first = component._build_initial_agent_message().properties.context_events
        assert [(e.kind, e.state, e.messages) for e in first] == [("fold", "running", 1)]

        await component._await_fold()
        assert component._fold_event.state == expected
        assert component._fold_event.id == first[0].id
        assert component._fold_event.duration is not None
