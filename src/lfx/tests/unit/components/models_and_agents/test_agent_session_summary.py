"""Agent integration of the "Summarize Older Messages" toggle."""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from lfx.base.memory.session_compressor import SummaryHistory, build_summary_message
from lfx.components.models_and_agents import agent as agent_module
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.messages_input_builder import build_initial_messages
from lfx.schema.message import Message
from lfx.schema.properties import Usage
from lfx.utils.constants import MESSAGE_SENDER_USER


def _component(*, summarize: bool, n_messages: int = 10) -> AgentComponent:
    component = AgentComponent()
    component._user_id = None
    component.set_attributes(
        {
            "model": "fake-model",
            "tools": [],
            "chat_history": [],
            "input_value": Message(text="now", sender=MESSAGE_SENDER_USER, id=uuid.uuid4()),
            "summarize_older_messages": summarize,
            "n_messages": n_messages,
            "context_id": "",
        }
    )
    component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id="s", flow_id=None, user_id=None))
    return component


def _history(component: AgentComponent) -> list[Message]:
    prior = Message(text="earlier", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())
    return [prior, component.input_value]


async def _memory_data(component, history, loaded=None):
    with (
        patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=history)),
        patch.object(agent_module, "load_history_with_summary", new=AsyncMock(return_value=loaded)) as load,
    ):
        return await component._history_for_turn(), load


async def test_toggle_off_returns_window_without_loading_a_summary():
    component = _component(summarize=False)
    history = _history(component)
    result, load = await _memory_data(component, history)
    assert result == history[:1]
    load.assert_not_called()


async def test_summary_is_skipped_under_evals_isolation_or_without_stored_messages():
    for patched in ("is_evals_memory_isolated", "should_persist_messages"):
        component = _component(summarize=True)
        history = _history(component)
        value = patched == "is_evals_memory_isolated"
        with patch.object(agent_module, patched, return_value=value):
            result, load = await _memory_data(component, history)
        assert result == history[:1]
        load.assert_not_called()


async def test_toggle_on_prepends_user_role_summary_message():
    component = _component(summarize=True)
    history = _history(component)
    summary = build_summary_message("KEY FACT", "s")
    result, load = await _memory_data(component, history, SummaryHistory([summary, history[0]]))
    assert load.call_args.kwargs["window"] == history[:1]
    assert result[0] is summary
    lc_messages = build_initial_messages(input_value=component.input_value, chat_history=result)
    assert isinstance(lc_messages[0], HumanMessage)
    assert "KEY FACT" in lc_messages[0].content


async def test_history_is_loaded_once_per_input():
    component = _component(summarize=True)
    history = _history(component)
    loaded = SummaryHistory(history[:1])
    with (
        patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=history)),
        patch.object(agent_module, "load_history_with_summary", new=AsyncMock(return_value=loaded)) as load,
    ):
        await component._history_for_turn()
        await component._history_for_turn()
    assert load.call_count == 1


async def test_fold_starts_in_the_background_once_and_does_not_block_the_history():
    component = _component(summarize=True)
    history = _history(component)
    release = asyncio.Event()
    started = []

    async def slow_fold(**kwargs):
        started.append(kwargs["batch"])
        await release.wait()

    batch = [Message(text="old", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())]
    loaded = SummaryHistory(history[:1], fold_batch=batch)
    with patch.object(agent_module, "fold_batch", new=slow_fold):
        result, _ = await _memory_data(component, history, loaded)
        await component._history_for_turn()  # memo hit: no second fold
        assert (
            getattr(component, "_fold_task", None) is None
        )  # staged, not started: `_start_fold` starts it where the history is used
        component._start_fold()
        component._start_fold()  # no-op while pending
        await asyncio.sleep(0)
        assert result == history[:1]
        assert started == [batch]
        assert not component._fold_task.done()
        release.set()
        await component._settle_fold()
    assert component._fold_task is None


async def test_settle_cancels_a_pending_fold_and_adds_its_usage_by_plain_addition():
    component = _component(summarize=True)
    component._token_usage = Usage(input_tokens=10, output_tokens=5, total_tokens=15)
    component._fold_usage_handler = MagicMock(
        get_usage=MagicMock(return_value=Usage(input_tokens=3, output_tokens=1, total_tokens=4))
    )
    component._fold_task = asyncio.create_task(asyncio.sleep(60))
    task = component._fold_task

    await component._settle_fold(cancel=True)

    assert task.cancelled()
    assert component._token_usage == Usage(input_tokens=13, output_tokens=6, total_tokens=19)


async def test_message_response_waits_for_the_fold_and_cancels_it_on_error():
    component = _component(summarize=True)
    done = []

    async def fold():
        await asyncio.sleep(0)
        done.append(True)

    component._fold_task = asyncio.create_task(fold())
    with patch.object(
        AgentComponent, "_run_agent_with_model_remediation", new=AsyncMock(return_value=Message(text="r"))
    ):
        await component.message_response()
    assert done == [True]
    assert component._fold_task is None

    component._fold_task = task = asyncio.create_task(asyncio.sleep(60))
    failing = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(AgentComponent, "_run_agent_with_model_remediation", new=failing), pytest.raises(RuntimeError):
        await component.message_response()
    assert task.cancelled()


async def test_component_without_the_input_keeps_last_n_history():
    component = _component(summarize=False)
    del component._attributes["summarize_older_messages"]
    history = _history(component)
    with patch.object(agent_module, "aget_agent_chat_history", new=AsyncMock(return_value=history)):
        assert await component._history_for_turn() == history[:1]


def test_summary_merges_into_current_input_when_window_is_empty():
    current = Message(text="now", sender=MESSAGE_SENDER_USER)
    result = build_initial_messages(input_value=current, chat_history=[build_summary_message("KEY FACT", "s")])
    assert len(result) == 1
    assert isinstance(result[0], HumanMessage)
    assert result[0].content.index("KEY FACT") < result[0].content.index("now")
    assert current.text == "now"


def test_summary_merges_into_a_copy_of_the_next_user_message_and_keeps_its_files():
    stored = Message(text="earlier", sender=MESSAGE_SENDER_USER)
    with_image = [{"type": "text", "text": "look"}, {"type": "image_url", "image_url": {"url": "u"}}]
    next_user = HumanMessage(content=with_image)
    summary = build_summary_message("KEY FACT", "s")

    def to_lc(message):
        return HumanMessage(content=message.text) if message is summary else next_user

    with patch.object(Message, "to_lc_message", autospec=True, side_effect=to_lc):
        result = build_initial_messages(input_value="now", chat_history=[summary, stored])

    assert [type(m) for m in result] == [HumanMessage, HumanMessage]
    assert "KEY FACT" in result[0].content[0]["text"]
    assert result[0].content[1:] == with_image
    assert result[0] is not next_user
    assert next_user.content == with_image
    assert stored.text == "earlier"


def test_summary_stays_separate_before_an_assistant_message():
    reply = Message(text="hello", sender="Machine", sender_name="AI")
    result = build_initial_messages(input_value="now", chat_history=[build_summary_message("KEY FACT", "s"), reply])
    assert [type(m) for m in result] == [HumanMessage, AIMessage, HumanMessage]


async def test_fold_call_reports_usage_and_tracing_callbacks():
    component = _component(summarize=True)
    component._fold_usage_handler = usage_handler = object()
    tracer = object()
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=MagicMock(content="SUMMARY"))
    with (
        patch.object(AgentComponent, "_get_llm", return_value=llm),
        patch.object(AgentComponent, "_get_shared_callbacks", return_value=[tracer]),
    ):
        assert await component._summarize_history("", [Message(text="a", sender=MESSAGE_SENDER_USER)]) == "SUMMARY"
    assert llm.ainvoke.call_args.kwargs["config"] == {"callbacks": [usage_handler, tracer]}


async def test_cancelling_message_response_propagates_while_a_fold_is_pending():
    component = _component(summarize=True)
    component._fold_task = fold = asyncio.create_task(asyncio.sleep(60))
    finished_run = AsyncMock(return_value=Message(text="r"))

    with patch.object(AgentComponent, "_run_agent_with_model_remediation", new=finished_run):
        runner = asyncio.create_task(component.message_response())
        await asyncio.sleep(0.01)  # the run is done; the component now waits for the fold
        assert not runner.done()
        runner.cancel()
        with pytest.raises(asyncio.CancelledError):
            await runner
    assert fold.cancelled()


async def test_no_second_fold_starts_while_one_is_pending_even_without_an_input_id():
    component = _component(summarize=True)
    component.input_value = Message(text="now", sender=MESSAGE_SENDER_USER)  # no id: the memo is bypassed
    history = [Message(text="earlier", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())]
    batch = [Message(text="old", sender=MESSAGE_SENDER_USER, id=uuid.uuid4())]
    loaded = SummaryHistory(history, fold_batch=batch)
    started = []

    async def slow_fold(**kwargs):
        started.append(kwargs["batch"])
        await asyncio.sleep(60)

    with patch.object(agent_module, "fold_batch", new=slow_fold):
        await _memory_data(component, history, loaded)
        component._start_fold()
        first = component._fold_task
        await _memory_data(component, history, loaded)
        component._start_fold()
        await asyncio.sleep(0)
        assert component._fold_task is first
        assert len(started) == 1
        await component._settle_fold(cancel=True)
    assert first.cancelled()


async def test_cancelling_the_caller_while_a_cancelled_fold_winds_down_propagates():
    component = _component(summarize=True)

    async def slow_to_cancel():
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            await asyncio.sleep(60)  # slow cleanup

    component._fold_task = fold = asyncio.create_task(slow_to_cancel())
    await asyncio.sleep(0)
    settling = asyncio.create_task(component._settle_fold(cancel=True))
    await asyncio.sleep(0.01)
    assert not settling.done()
    settling.cancel()
    with pytest.raises(asyncio.CancelledError):
        await settling
    fold.cancel()  # the test's own cleanup: the stubborn fold ignores the first cancel


async def test_settle_ends_the_history_memo():
    component = _component(summarize=True)
    component._summary_history_memo = (uuid.uuid4(), [])
    await component._settle_fold()
    assert component._summary_history_memo is None


class _NoNativeLLM:
    """A model that inherits `with_structured_output` but raises NotImplementedError when it is used."""

    def with_structured_output(self, *_args, **_kwargs):
        raise NotImplementedError


class _NativeLLM:
    def with_structured_output(self, *_args, **_kwargs):
        return MagicMock(ainvoke=AsyncMock(return_value={"a": "1"}))


async def _json_response_with_staged_fold(llm, output_schema) -> list:
    """Run `json_response` with the real orchestrator and a staged fold; return the folds that started."""
    component = _component(summarize=True)
    component.set_attributes({"output_schema": output_schema})
    component._staged_fold = {"scope": {}, "state": None, "batch": []}
    started = []

    async def fold(**kwargs):
        await asyncio.sleep(0)
        started.append(kwargs)

    run_agent = AsyncMock(return_value=Message(text='{"a": "1"}'))

    async def remediation(_self, run_once):
        return await run_once()

    with (
        patch.object(AgentComponent, "get_agent_requirements", new=AsyncMock(return_value=(llm, [], []))),
        patch.object(AgentComponent, "_run_agent_with_model_remediation", new=remediation),
        patch.object(AgentComponent, "create_agent_runnable", new=MagicMock()),
        patch.object(AgentComponent, "run_agent", new=run_agent),
        patch.object(agent_module, "fold_batch", new=fold),
    ):
        result = await component.json_response()
    assert "error" not in result.data, result.data
    assert getattr(component, "_fold_task", None) is None
    assert component._staged_fold is None
    return started


SCHEMA = [{"name": "a", "type": "str"}]


async def test_json_response_starts_one_fold_when_native_output_falls_back_to_the_prompt_path():
    assert len(await _json_response_with_staged_fold(_NoNativeLLM(), SCHEMA)) == 1


async def test_json_response_starts_no_fold_when_the_native_path_succeeds():
    assert await _json_response_with_staged_fold(_NativeLLM(), SCHEMA) == []


async def test_json_response_starts_no_fold_for_an_empty_schema():
    assert await _json_response_with_staged_fold(_NoNativeLLM(), []) == []


async def test_message_response_starts_the_staged_fold_once_and_settles_it():
    component = _component(summarize=True)
    component._staged_fold = {"scope": {}, "state": None, "batch": []}
    started = []

    async def fold(**kwargs):
        await asyncio.sleep(0)
        started.append(kwargs)

    async def remediation(_self, run_once):
        return await run_once()

    with (
        patch.object(AgentComponent, "get_agent_requirements", new=AsyncMock(return_value=(MagicMock(), [], []))),
        patch.object(AgentComponent, "_run_agent_with_model_remediation", new=remediation),
        patch.object(AgentComponent, "create_agent_runnable", new=MagicMock()),
        patch.object(AgentComponent, "run_agent", new=AsyncMock(return_value=Message(text="reply"))),
        patch.object(agent_module, "fold_batch", new=fold),
    ):
        await component.message_response()

    assert len(started) == 1
    assert getattr(component, "_fold_task", None) is None
    assert component._staged_fold is None
