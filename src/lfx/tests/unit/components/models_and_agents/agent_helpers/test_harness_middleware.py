"""Real agent runs exercise context preparation, compaction, limits, and execution evidence."""

from copy import deepcopy

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.base.agents.events import process_agent_events
from lfx.base.agents.harness import HarnessRuntimeConfig
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape
from lfx.components.models_and_agents.agent_helpers.harness_middleware import SUMMARY_MARKER, prepare_context
from lfx.schema.message import Message
from pydantic import Field


class HarnessModel(BaseChatModel):
    seen: list = Field(default_factory=list)
    loop: bool = False
    fail_summary: bool = False
    empty_summary: bool = False
    answer: str = "Research result [source-1]."

    @property
    def _llm_type(self):
        return "harness-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        is_summary = "Messages to summarize:" in str(messages[0].content)
        if is_summary:
            if self.fail_summary:
                msg = "provider summary failure"
                raise RuntimeError(msg)
            result = AIMessage(content="" if self.empty_summary else "Earlier evidence supports claim [source-1].")
        elif self.loop:
            result = AIMessage(
                content="",
                tool_calls=[{"name": "read_source", "args": {}, "id": f"call-{len(self.seen)}", "type": "tool_call"}],
            )
        else:
            result = AIMessage(content=self.answer)
        return ChatResult(generations=[ChatGeneration(message=result)])


def agent(model, **settings):
    component = AgentComponent()
    component.set(model=model, tools=[], system_prompt="Keep the system instructions.", **settings)
    return component.create_agent_runnable(), component


def history():
    return [
        HumanMessage(content="Old question " * 100, id="old-q"),
        AIMessage(content="Old answer " * 100, id="old-a"),
        HumanMessage(content="Research this question.", id="new-q"),
    ]


async def test_context_selection_reaches_each_model_call_without_rewriting_history():
    model = HarnessModel()
    runnable, _ = agent(model, context_strategy="recent_turns", context_turns=1)
    original = history()
    events = [event async for event in runnable.astream_events({"messages": original}, version="v2")]
    assert [message.content for message in model.seen[0]] == [
        "Keep the system instructions.",
        "Research this question.",
    ]
    evidence = next(event["data"] for event in events if event.get("name") == "harness_runtime")
    assert evidence["retained_message_ids"] == ["new-q"]
    assert evidence["messages_before"] == 3
    assert evidence["messages_after"] == 1
    final = next(
        event for event in reversed(events) if not event.get("parent_ids") and event["event"] == "on_chain_end"
    )
    assert len(final["data"]["output"]["messages"]) == 4
    assert original[0].content.startswith("Old question")


def test_context_keeps_tool_pairs_system_messages_and_compaction_summary():
    summary = HumanMessage(content="Earlier summary", additional_kwargs={SUMMARY_MARKER: True})
    system = SystemMessage(content="System")
    call = AIMessage(content="", tool_calls=[{"name": "read_source", "args": {}, "id": "a", "type": "tool_call"}])
    result = ToolMessage(content="Evidence", tool_call_id="a")
    newest = HumanMessage(content="Question")
    messages = [
        system,
        summary,
        HumanMessage(content="Earlier"),
        AIMessage(content="Earlier answer"),
        newest,
        call,
        result,
    ]
    assert prepare_context(messages, 1) == [system, summary, newest, call, result]


async def test_compaction_uses_real_model_and_records_evidence_without_leaking_summary_stream():
    model = HarnessModel()
    runnable, _ = agent(
        model,
        compaction="summarize",
        compaction_trigger_tokens=80,
        compaction_keep_messages=1,
        context_strategy="recent_turns",
        context_turns=1,
    )
    events = [
        event
        async for event in adapt_graph_events_to_executor_shape(
            runnable.astream_events({"messages": history()}, version="v2")
        )
    ]
    assert len(model.seen) == 2
    assert any(message.additional_kwargs.get(SUMMARY_MARKER) for message in model.seen[1])
    assert model.seen[1][-1].content == "Research this question."
    evidence = [event["data"] for event in events if event.get("name") == "harness_runtime"]
    compacted = next(item for item in evidence if item["kind"] == "compacted")
    assert compacted["messages_before"] == 3
    assert compacted["retained_messages"] == 1
    assert "[source-1]" in compacted["summary"]
    assert not any("harness:compaction" in event.get("tags", []) for event in events)
    assert events[-1]["data"]["output"].return_values["output"] == "Research result [source-1]."


@pytest.mark.parametrize("failure", ["fail_summary", "empty_summary"])
async def test_summary_failure_stops_before_reasoning_without_removing_history(failure):
    model = HarnessModel(**{failure: True})
    runnable, _ = agent(model, compaction="summarize", compaction_trigger_tokens=80, compaction_keep_messages=1)
    original = history()
    with pytest.raises(ValueError, match="No context was removed"):
        await runnable.ainvoke({"messages": original})
    assert len(model.seen) == 1
    assert len(original) == 3
    assert original[0].content.startswith("Old question")


async def test_model_call_limit_stops_real_tool_loop_with_context_preparation():
    calls = []

    @tool
    def read_source() -> str:
        """Read a source."""
        calls.append(True)
        return "Source evidence"

    model = HarnessModel(loop=True)
    component = AgentComponent()
    component.set(model=model, tools=[read_source], max_iterations=2, context_strategy="recent_turns", context_turns=1)
    runnable = component.create_agent_runnable()
    result = await runnable.ainvoke(
        {"messages": history()}, config={"recursion_limit": component._compute_recursion_limit()}
    )
    assert len(model.seen) == 2
    assert len(calls) == 2
    assert "limit" in result["messages"][-1].content.lower()
    # Both calls receive the fresh question; tool result remains paired on the second call.
    assert any(message.content == "Research this question." for message in model.seen[1])
    assert any(isinstance(message, ToolMessage) for message in model.seen[1])


async def test_context_and_compaction_evidence_survive_final_message_publication():
    model = HarnessModel()
    runnable, _ = agent(model, compaction="summarize", compaction_trigger_tokens=80, compaction_keep_messages=1)
    published = []
    tokens = []

    async def publish(*, message, **kwargs):
        published.append((deepcopy(message), kwargs.get("skip_db_update", False)))
        return message

    async def token(**kwargs):
        tokens.append(kwargs)

    result = await process_agent_events(
        adapt_graph_events_to_executor_shape(runnable.astream_events({"messages": history()}, version="v2")),
        Message(text="", sender="Machine", sender_name="AI"),
        publish,
        token,
    )
    titles = [getattr(block, "title", None) for block in result.content_blocks]
    assert "Conversation compacted" in titles
    assert "Context prepared" in titles
    assert "Earlier evidence supports claim [source-1]." in str(result.content_blocks)
    assert result.data["text"] == "Research result [source-1]."
    assert "Earlier evidence" not in str(tokens)
    final, skip_db = published[-1]
    assert not skip_db
    assert final.properties.state == "complete"
    assert final.content_blocks == result.content_blocks


@pytest.mark.parametrize(
    ("settings", "calls"),
    [
        ({"context_strategy": "recent_turns", "context_turns": 1}, 1),
        ({"compaction": "summarize", "compaction_trigger_tokens": 80, "compaction_keep_messages": 1}, 2),
    ],
)
async def test_structured_output_does_not_bypass_configured_context(monkeypatch, settings, calls):
    model = HarnessModel(answer='{"answer": "Sourced result"}')
    component = AgentComponent()
    component.set(
        model=model,
        tools=[],
        system_prompt="Research with sources.",
        input_value="Latest question",
        **settings,
        output_schema=[{"name": "answer", "type": "str", "description": "Result", "multiple": False}],
    )

    async def requirements():
        return (
            model,
            [
                Message(text="Old question " * 100, sender="User"),
                Message(text="Old answer " * 100, sender="Machine"),
            ],
            [],
        )

    def native_must_not_run(*_args, **_kwargs):
        msg = "Native structured output must not bypass the configured context middleware"
        raise AssertionError(msg)

    monkeypatch.setattr(component, "get_agent_requirements", requirements)
    monkeypatch.setattr(HarnessModel, "with_structured_output", native_must_not_run)
    result = await component.json_response()
    assert result.data == {"answer": "Sourced result"}
    assert len(model.seen) == calls
    assert model.seen[-1][-1].content == "Latest question"
    assert all(not message.content.startswith("Old question") for message in model.seen[-1])
    if calls == 2:
        assert any(message.additional_kwargs.get(SUMMARY_MARKER) for message in model.seen[-1])


@pytest.mark.parametrize(
    "settings",
    [{"context_turns": 0}, {"compaction_trigger_tokens": 0}, {"compaction": "fake"}, {"max_iterations": True}],
)
def test_runtime_settings_reject_invalid_values(settings):
    with pytest.raises(ValueError, match="validation error"):
        HarnessRuntimeConfig.model_validate(settings)
