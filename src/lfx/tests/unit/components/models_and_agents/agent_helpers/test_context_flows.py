"""Context flows transform actual model requests without rewriting stored conversations."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage, messages_to_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.base.agents.context_messages import messages_from_rows, messages_from_table, messages_to_table
from lfx.base.agents.events import process_agent_events
from lfx.base.agents.hooks import HookBinding
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape
from lfx.components.models_and_agents.agent_helpers.harness_middleware import SUMMARY_MARKER
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.context import ContextBinding, ContextFlowError, ContextFlowRunner, context_outputs
from lfx.projects.hooks import HookFlowRunner
from lfx.schema.message import Message
from pydantic import Field


class ContextModel(BaseChatModel):
    seen: list = Field(default_factory=list)
    use_tool: bool = False

    @property
    def _llm_type(self):
        return "context-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        if "Messages to summarize:" in str(messages[0].content):
            result = AIMessage(content="Earlier source [source-1] was reviewed.")
        elif self.use_tool and not any(isinstance(m, ToolMessage) for m in messages):
            result = AIMessage(content="", tool_calls=[{"name": "read_source", "args": {}, "id": "read-1"}])
        else:
            result = AIMessage(content='{"answer":"Sourced result [source-1]"}')
        return ChatResult(generations=[ChatGeneration(message=result)])


def context_flow(tmp_path, *, strategy="all", code=None):
    flow = build_slot_baseline("builtin:context")
    flow["id"] = str(uuid4())
    terminal = flow["data"]["nodes"][-1]
    template = terminal["data"]["node"]["template"]
    template["strategy"]["value"] = strategy
    template["turns"]["value"] = 1
    if code:
        template["code"]["value"] = code(template["code"]["value"])
    path = tmp_path / f"{flow['id']}.json"
    path.write_text(json.dumps(flow))
    output = context_outputs(flow["data"])[0]
    binding = ContextBinding(
        flow_id=flow["id"],
        revision=flow_revision(flow["data"]),
        node_id=output["node_id"],
        output_name=output["output_name"],
        version_id="reviewed-snapshot",
    )
    return binding, flow, path


def agent(tmp_path, binding, *, use_tool=False, **settings):
    @tool
    def read_source() -> str:
        """Read a primary source."""
        return "Source [source-1]"

    model = ContextModel(use_tool=use_tool)
    component = AgentComponent(_user_id="test-user")
    component.set(
        model=model,
        tools=[read_source] if use_tool else [],
        system_prompt="Keep the harness instructions.",
        max_iterations=4,
        context_binding=json.dumps(binding.model_dump()),
        **settings,
    )
    component._vertex = SimpleNamespace(
        graph=SimpleNamespace(
            context={"project_dir": str(tmp_path)},
            run_id=str(uuid4()),
            session_id=str(uuid4()),
            human_input_decisions={},
        )
    )
    return component, model


def history():
    return [
        HumanMessage(content="Earlier question " * 80, id="old-question"),
        AIMessage(content="Earlier answer " * 80, id="old-answer"),
        HumanMessage(content="Read the latest source.", id="latest"),
    ]


async def events(component, messages=None):
    return [
        event
        async for event in component.create_agent_runnable().astream_events(
            {"messages": messages if messages is not None else history()},
            version="v2",
        )
    ]


async def test_context_baseline_is_a_real_passthrough_graph_with_preview_messages():
    flow = build_slot_baseline("builtin:context")
    output = context_outputs(flow["data"])[0]
    graph = Graph.from_payload(flow["data"])
    results = [result async for result in graph.async_start()]
    assert sum(getattr(result, "valid", False) for result in results) == 2
    value = graph.get_vertex(output["node_id"]).custom_component.get_output(output["output_name"]).value
    assert messages_from_table(value)[0].content == "Research this question using primary sources."


def test_message_table_preserves_rich_content_tool_metadata_and_ids_without_aliasing():
    messages = [
        SystemMessage(content="Instructions", id="system"),
        HumanMessage(
            content=[{"type": "text", "text": "Review"}, {"type": "image_url", "image_url": {"url": "fixture-image"}}],
            id="user",
        ),
        AIMessage(content="", tool_calls=[{"name": "read", "args": {"source": "a"}, "id": "call"}], id="ai"),
        ToolMessage(content="Evidence", tool_call_id="call", status="error", artifact={"source_id": "a"}, id="result"),
    ]
    table = messages_to_table(messages)
    restored = messages_from_table(table)
    assert messages_to_dict(restored) == messages_to_dict(messages)
    restored[1].content[0]["text"] = "Changed"
    assert messages[1].content[0]["text"] == "Review"
    assert messages_from_table(table)[1].content[0]["text"] == "Review"
    assert messages_from_table(messages_to_table([])) == []


@pytest.mark.parametrize(
    "rows",
    [
        [{"type": "remove", "data": {"id": "latest"}}],
        [{"type": "human", "data": "not a message"}],
        [{"type": "tool", "data": {"content": "orphan", "tool_call_id": "unknown"}}],
        messages_to_dict([AIMessage(content="", tool_calls=[{"name": "read", "args": {}, "id": "pending"}])]),
        messages_to_dict(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "read", "args": {}, "id": "same"}, {"name": "read", "args": {}, "id": "same"}],
                )
            ]
        ),
        messages_to_dict(
            [
                AIMessage(content="", tool_calls=[{"name": "read", "args": {}, "id": "call"}]),
                HumanMessage(content="Interrupted"),
            ]
        ),
    ],
)
def test_context_output_rejects_state_commands_malformed_messages_and_broken_tool_pairs(rows):
    with pytest.raises(ValueError, match=r"[Cc]ontext"):
        messages_from_rows(rows)


async def test_bound_flow_replaces_scalar_selection_and_keeps_history_unchanged(tmp_path):
    binding, _, _ = context_flow(tmp_path)
    component, model = agent(tmp_path, binding, context_strategy="recent_turns", context_turns=1)
    original = history()
    raw = await events(component, original)
    assert [m.id for m in model.seen[0][1:]] == ["old-question", "old-answer", "latest"]
    assert model.seen[0][0].content == "Keep the harness instructions."
    evidence = next(e["data"] for e in raw if e.get("name") == "harness_runtime")
    assert evidence["strategy"] == "flow"
    assert evidence["revision"] == binding.revision
    assert evidence["version_id"] == binding.version_id
    assert len(original) == 3
    final = next(e for e in reversed(raw) if not e.get("parent_ids") and e["event"] == "on_chain_end")
    assert len(final["data"]["output"]["messages"]) == 4


async def test_context_flow_runs_before_each_model_call_and_preserves_tool_pairs(tmp_path):
    binding, _, _ = context_flow(tmp_path, strategy="recent_turns")
    component, model = agent(tmp_path, binding, use_tool=True)
    raw = await events(component)
    assert len(model.seen) == 2
    assert all(not any(m.id == "old-question" for m in request) for request in model.seen)
    assert isinstance(model.seen[1][-1], ToolMessage)
    assert model.seen[1][-1].tool_call_id == model.seen[1][-2].tool_calls[0]["id"]
    evidence = [e["data"] for e in raw if e.get("name") == "harness_runtime"]
    assert len(evidence) == 2
    assert [item["messages_after"] for item in evidence] == [1, 3]


async def test_context_flow_can_transform_the_model_request_without_changing_saved_messages(tmp_path):
    def change(code):
        return code.replace(
            "return messages_to_table(prepared)",
            'prepared[-1] = prepared[-1].model_copy(update={"content": "Use primary evidence."})\n'
            "        return messages_to_table(prepared)",
        )

    binding, _, _ = context_flow(tmp_path, code=change)
    component, model = agent(tmp_path, binding)
    original = history()
    await events(component, original)
    assert model.seen[0][-1].content == "Use primary evidence."
    assert original[-1].content == "Read the latest source."


async def test_custom_context_sees_compacted_history_and_retains_summary(tmp_path):
    binding, _, _ = context_flow(tmp_path, strategy="recent_turns")
    component, model = agent(
        tmp_path, binding, compaction="summarize", compaction_trigger_tokens=80, compaction_keep_messages=1
    )
    await events(component)
    assert len(model.seen) == 2
    assert any(m.additional_kwargs.get(SUMMARY_MARKER) for m in model.seen[-1])
    assert model.seen[-1][-1].content == "Read the latest source."


async def test_stale_definition_stops_before_model_call_and_explains_rebinding(tmp_path):
    binding, flow, path = context_flow(tmp_path)
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["turns"]["value"] = 2
    path.write_text(json.dumps(flow))
    component, model = agent(tmp_path, binding)
    with pytest.raises(ContextFlowError, match=r"changed.*Review"):
        await events(component)
    assert model.seen == []


@pytest.mark.parametrize(
    "replacement",
    [
        'return "display artifact"',
        'return DataFrame([{"wrong": "schema"}])',
        'raise RuntimeError("private provider detail")',
    ],
)
async def test_bad_flow_outputs_stop_before_model_call_without_leaking_payloads(tmp_path, replacement):
    binding, _, _ = context_flow(
        tmp_path, code=lambda code: code.replace("return messages_to_table(prepared)", replacement)
    )
    component, model = agent(tmp_path, binding)
    raw = []

    async def collect():
        async for event in component.create_agent_runnable().astream_events({"messages": history()}, version="v2"):
            raw.append(event)  # noqa: PERF401 - retain partial evidence when execution raises

    with pytest.raises(ContextFlowError, match="output was not applied"):
        await collect()
    evidence = next(e["data"] for e in raw if e.get("name") == "harness_runtime")
    assert evidence["kind"] == "context_failed"
    assert "private provider detail" not in str(evidence)
    assert model.seen == []


async def test_timeout_stops_before_model_call_and_cancels_the_flow(tmp_path):
    def slow(code):
        return code.replace("    def prepare_messages", "    async def prepare_messages").replace(
            "        policy =", "        import asyncio\n        await asyncio.sleep(10)\n        policy ="
        )

    binding, _, _ = context_flow(tmp_path, code=slow)
    component, model = agent(tmp_path, binding.model_copy(update={"timeout_seconds": 0.05}))
    with pytest.raises(ContextFlowError, match="timed out"):
        await events(component)
    assert model.seen == []


async def test_compiled_runner_keeps_its_definition_until_a_new_agent_is_created(tmp_path):
    binding, flow, path = context_flow(tmp_path)
    component, model = agent(tmp_path, binding)
    runnable = component.create_agent_runnable()
    await runnable.ainvoke({"messages": history()})
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["strategy"]["value"] = "recent_turns"
    path.write_text(json.dumps(flow))
    await runnable.ainvoke({"messages": history()})
    assert len(model.seen[0]) == len(model.seen[1]) == 4
    with pytest.raises(ContextFlowError, match="changed"):
        await events(component)


async def test_parallel_context_invocations_have_isolated_messages(tmp_path):
    binding, _, _ = context_flow(tmp_path)
    component, _ = agent(tmp_path, binding)
    runner = ContextFlowRunner(component, binding)
    results = await asyncio.gather(*(runner([HumanMessage(content=str(i))]) for i in range(3)))
    assert [messages[0].content for messages in results] == ["0", "1", "2"]


async def test_shared_invocation_guard_rejects_cross_contract_recursion_and_resets(tmp_path, monkeypatch):
    binding, _, _ = context_flow(tmp_path)
    component, _ = agent(tmp_path, binding)
    runner = ContextFlowRunner(component, binding)
    hook_runner = HookFlowRunner(component)
    hook = HookBinding(**binding.model_dump(), on_event="before_llm_call")

    async def recurse(**_kwargs):
        return await hook_runner(hook, {})

    with monkeypatch.context() as patcher:
        patcher.setattr("lfx.helpers.flow.run_flow", recurse)
        with pytest.raises(ValueError, match="recursively invoke"):
            await runner(history())
    assert len(await runner(history())) == 3


async def test_structured_output_uses_custom_context_instead_of_native_shortcut(tmp_path, monkeypatch):
    binding, _, _ = context_flow(tmp_path, strategy="recent_turns")
    component, model = agent(tmp_path, binding)
    component.set(
        input_value="Latest question",
        output_schema=[{"name": "answer", "type": "str", "description": "Answer", "multiple": False}],
    )

    async def requirements():
        return model, [Message(text="Old question", sender="User"), Message(text="Old answer", sender="Machine")], []

    def native(*_args, **_kwargs):
        msg = "Native shortcut bypassed custom context"
        raise AssertionError(msg)

    monkeypatch.setattr(component, "get_agent_requirements", requirements)
    monkeypatch.setattr(ContextModel, "with_structured_output", native)
    result = await component.json_response()
    assert result.data == {"answer": "Sourced result [source-1]"}
    assert len(model.seen[0]) == 2
    assert model.seen[0][-1].content == "Latest question"


def test_sync_execution_rejects_flow_adapter_before_model_call(tmp_path):
    binding, _, _ = context_flow(tmp_path)
    component, model = agent(tmp_path, binding)
    with pytest.raises(ContextFlowError, match="asynchronous"):
        component.create_agent_runnable().invoke({"messages": history()})
    assert model.seen == []


async def test_context_model_output_is_traced_but_only_main_answer_is_published(tmp_path):
    def nested_model(code):
        return code.replace("    def prepare_messages", "    async def prepare_messages").replace(
            "        policy =",
            "        from langchain_core.language_models.fake_chat_models import FakeListChatModel\n"
            '        await FakeListChatModel(responses=["Internal context work"]).ainvoke("Prepare context")\n'
            "        policy =",
        )

    binding, _, _ = context_flow(tmp_path, code=nested_model)
    component, _ = agent(tmp_path, binding)
    raw = await events(component)
    assert any(e["event"].startswith("on_chat_model") and "harness:context" in e.get("tags", []) for e in raw)

    async def source():
        for event in raw:
            yield event

    async def publish(*, message, **_kwargs):
        return message

    result = await process_agent_events(
        adapt_graph_events_to_executor_shape(source()), Message(text="", sender="Machine"), publish
    )
    assert result.text == '{"answer":"Sourced result [source-1]"}'
    assert "Internal context work" not in str(result.content_blocks)
    assert "Context prepared" in str(result.content_blocks)
    assert binding.revision in str(result.content_blocks)


@pytest.mark.parametrize("timeout", [0, -1, 301, float("nan"), float("inf")])
def test_context_binding_rejects_invalid_timeouts(tmp_path, timeout):
    binding, _, _ = context_flow(tmp_path)
    with pytest.raises(ValueError, match="timeout_seconds"):
        ContextBinding.model_validate({**binding.model_dump(), "timeout_seconds": timeout})


def test_static_context_validation_does_not_execute_saved_code_and_requires_live_input():
    flow = build_slot_baseline("builtin:context")
    original = context_outputs(flow["data"])
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('must not execute')"
    assert context_outputs(flow["data"]) == original
    flow["data"]["edges"] = []
    with pytest.raises(ValueError, match="Configure"):
        context_outputs(flow["data"])
    flow["data"]["nodes"] = flow["data"]["nodes"][1:]
    with pytest.raises(ValueError, match="one Agent Context"):
        context_outputs(flow["data"])
