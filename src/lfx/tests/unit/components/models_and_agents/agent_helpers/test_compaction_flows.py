"""Run real reviewed compaction graphs through the Agent, including failures and replay."""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from lfx.base.agents.compaction import COMPACTION_MODEL, SUMMARY_MARKER, CompactionResult
from lfx.base.agents.context_messages import messages_from_table, messages_to_table
from lfx.base.agents.events import process_agent_events
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.compaction import CompactionBinding, CompactionFlowError, CompactionFlowRunner, compaction_outputs
from lfx.schema.message import Message
from pydantic import Field


class CompactionModel(BaseChatModel):
    seen: list = Field(default_factory=list)
    summary: str = "Earlier evidence supports [source-1] at https://example.org/source."
    fail_summary: bool = False

    @property
    def _llm_type(self):
        return "compaction-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        if "Messages to summarize:" in str(messages[0].content):
            if self.fail_summary:
                msg = "private provider payload"
                raise RuntimeError(msg)
            answer = self.summary
        else:
            answer = '{"answer":"Report [source-1]"}'
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=answer))])


def history():
    return [
        HumanMessage(content="Old question " * 90, id="q1"),
        AIMessage(content="Old answer " * 90, id="a1"),
        HumanMessage(content="Latest question", id="q2"),
    ]


def source(tmp_path, *, code=None, keep=1):
    flow = build_slot_baseline("builtin:compaction", initial_config={"compaction_keep_messages": keep})
    flow["id"] = str(uuid4())
    if code:
        template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
        template["code"]["value"] = code(template["code"]["value"])
    path = tmp_path / f"{flow['id']}.json"
    path.write_text(json.dumps(flow))
    choice = compaction_outputs(flow["data"])[0]
    binding = CompactionBinding(
        flow_id=flow["id"],
        node_id=choice["node_id"],
        output_name=choice["output_name"],
        revision=flow_revision(flow["data"]),
        version_id="reviewed-version",
        trigger_tokens=80,
    )
    return binding, flow, path


def agent(tmp_path, binding, model=None):
    model = model or CompactionModel()
    component = AgentComponent(_user_id="test-user")
    component.set(
        model=model,
        tools=[],
        system_prompt="Keep the harness instructions.",
        compaction_binding=binding.model_dump_json(),
        compaction="off",
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


async def events(component, messages=None):
    return [
        event
        async for event in component.create_agent_runnable().astream_events(
            {"messages": history() if messages is None else messages},
            version="v2",
        )
    ]


async def test_baseline_uses_the_harness_model_and_records_the_reviewed_result(tmp_path):
    binding, _, _ = source(tmp_path)
    component, model = agent(tmp_path, binding)
    original = history()
    raw = await events(component, original)
    assert len(model.seen) == 2
    assert "source identifiers" in model.seen[0][0].content
    assert model.seen[1][0].content == "Keep the harness instructions."
    assert any(m.additional_kwargs.get(SUMMARY_MARKER) for m in model.seen[1])
    assert model.seen[1][-1].id == "q2"
    evidence = next(e["data"] for e in raw if e.get("name") == "harness_runtime" and e["data"]["kind"] == "compacted")
    assert evidence["flow_id"] == binding.flow_id
    assert evidence["revision"] == binding.revision
    assert evidence["version_id"] == "reviewed-version"
    assert evidence["dropped_count"] == 2
    assert evidence["retained_message_ids"] == ["q2"]
    assert evidence["trigger_reason"] == "proactive"
    assert evidence["estimated_tokens_after"] < evidence["estimated_tokens_before"]
    assert original[0].content.startswith("Old question")
    assert len(original) == 3
    assert COMPACTION_MODEL.get() is None


async def test_below_threshold_does_not_resolve_or_execute_the_flow(tmp_path):
    binding, _, path = source(tmp_path)
    path.unlink()
    component, model = agent(tmp_path, binding)
    raw = await events(component, [HumanMessage(content="Short")])
    assert len(model.seen) == 1
    assert not any(e.get("name") == "harness_runtime" and e["data"]["kind"] == "compacted" for e in raw)


async def test_baseline_keeps_tool_pairs_and_system_messages(tmp_path):
    binding, _, _ = source(tmp_path)
    component, model = agent(tmp_path, binding)
    messages = [
        SystemMessage(content="System rule", id="system"),
        *history(),
        AIMessage(content="", id="call", tool_calls=[{"name": "search", "args": {}, "id": "t1"}]),
        ToolMessage(content="Primary source", tool_call_id="t1", id="result"),
    ]
    result = await CompactionFlowRunner(component, binding, model)(messages, estimated_tokens=500)
    replacement = result.apply(messages)
    retained = messages_from_table(result.kept_messages)
    assert retained[0].id == "system"
    assert [m.id for m in retained[-2:]] == ["call", "result"]
    assert replacement[0].content == "System rule"
    assert result.dropped_count == len(messages) - len(retained)


async def test_no_removable_prefix_reports_no_state_replacement(tmp_path):
    binding, _, _ = source(tmp_path, keep=12)
    component, model = agent(tmp_path, binding)
    raw = await events(component)
    assert len(model.seen) == 1
    assert len(model.seen[0]) == 4
    evidence = next(e["data"] for e in raw if e.get("name") == "harness_runtime")
    assert evidence["kind"] == "compaction_skipped"
    assert evidence["dropped_count"] == 0


@pytest.mark.parametrize("model", [CompactionModel(fail_summary=True), CompactionModel(summary="")])
async def test_summary_failure_preserves_history_and_hides_provider_payload(tmp_path, model):
    binding, _, _ = source(tmp_path)
    component, _ = agent(tmp_path, binding, model)
    original = history()
    raw = []

    async def collect():
        async for event in component.create_agent_runnable().astream_events({"messages": original}, version="v2"):
            raw.append(event)  # noqa: PERF401 - preserve partial failure evidence

    with pytest.raises(CompactionFlowError, match="No context was removed"):
        await collect()
    evidence = next(e["data"] for e in raw if e.get("name") == "harness_runtime")
    assert evidence["kind"] == "compaction_failed"
    assert "private provider payload" not in str(evidence)
    assert len(model.seen) == 1
    assert len(original) == 3
    assert COMPACTION_MODEL.get() is None


async def test_stale_source_is_rejected_before_any_model_work(tmp_path):
    binding, flow, path = source(tmp_path)
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["instructions"]["value"] = "New policy"
    path.write_text(json.dumps(flow))
    component, model = agent(tmp_path, binding)
    with pytest.raises(CompactionFlowError, match=r"changed.*Review"):
        await events(component)
    assert model.seen == []


async def test_timeout_cancels_and_clears_borrowed_model(tmp_path):
    binding, _, _ = source(
        tmp_path,
        code=lambda code: code.replace(
            "        policy =",
            "        import asyncio\n        await asyncio.sleep(10)\n        policy =",
        ),
    )
    component, model = agent(tmp_path, binding.model_copy(update={"timeout_seconds": 0.05}))
    with pytest.raises(CompactionFlowError, match="timed out"):
        await events(component)
    assert model.seen == []
    assert COMPACTION_MODEL.get() is None


async def test_parallel_invocations_do_not_mix_models_or_messages(tmp_path):
    binding, _, _ = source(tmp_path)
    first, model1 = agent(tmp_path, binding, CompactionModel(summary="First summary"))
    second, model2 = agent(tmp_path, binding, CompactionModel(summary="Second summary"))
    a, b = await asyncio.gather(
        CompactionFlowRunner(first, binding, model1)(history(), estimated_tokens=500),
        CompactionFlowRunner(second, binding, model2)(history(), estimated_tokens=500),
    )
    assert [a.summary_message.text, b.summary_message.text] == ["First summary", "Second summary"]
    assert len(model1.seen) == len(model2.seen) == 1
    assert COMPACTION_MODEL.get() is None


@pytest.mark.parametrize(
    "change",
    [
        lambda rows: rows[:-1],
        lambda rows: [rows[0], {**rows[-1], "data": {**rows[-1]["data"], "content": "Changed"}}],
        lambda rows: list(reversed(rows)),
    ],
)
def test_compaction_rejects_missing_latest_mutated_or_reordered_retained_messages(change):
    from lfx.schema.dataframe import DataFrame

    original = history()
    rows = change(messages_to_table(original).to_dict(orient="records"))
    result = CompactionResult(kept_messages=DataFrame(rows), dropped_count=len(original) - len(rows))
    with pytest.raises(ValueError, match="Compaction"):
        result.apply(original)


@pytest.mark.parametrize(("count", "summary"), [(1, None), (0, Message(text="unexpected")), (2, Message(text=" "))])
def test_compaction_validates_count_and_summary_together(count, summary):
    kept = history() if count == 0 else history()[-1:]
    with pytest.raises(ValueError, match=r"[Cc]ompaction"):
        CompactionResult(kept_messages=messages_to_table(kept), dropped_count=count, summary_message=summary).apply(
            history()
        )


async def test_compaction_evidence_is_published_without_summary_tokens(tmp_path):
    binding, _, _ = source(tmp_path)
    component, _ = agent(tmp_path, binding)

    async def publish(*, message, **_kwargs):
        return message

    result = await process_agent_events(
        adapt_graph_events_to_executor_shape(
            component.create_agent_runnable().astream_events({"messages": history()}, version="v2")
        ),
        Message(text="", sender="Machine"),
        publish,
    )
    assert result.text == '{"answer":"Report [source-1]"}'
    assert "Conversation compacted" in str(result.content_blocks)
    assert binding.revision in str(result.content_blocks)


def test_sync_execution_rejects_custom_flow(tmp_path):
    binding, _, _ = source(tmp_path)
    component, model = agent(tmp_path, binding)
    with pytest.raises(CompactionFlowError, match="asynchronous"):
        component.create_agent_runnable().invoke({"messages": history()})
    assert model.seen == []


def test_static_contract_does_not_execute_code_and_requires_connected_input(tmp_path):
    _, flow, _ = source(tmp_path)
    choices = compaction_outputs(flow["data"])
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["code"]["value"] = "raise RuntimeError('do not run')"
    assert compaction_outputs(flow["data"]) == choices
    flow["data"]["edges"] = []
    with pytest.raises(ValueError, match="Configure"):
        compaction_outputs(flow["data"])


@pytest.mark.parametrize(
    "settings",
    [
        {"trigger_tokens": 0},
        {"trigger_tokens": True},
        {"timeout_seconds": 0},
        {"timeout_seconds": 301},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
    ],
)
def test_invalid_binding_settings_fail(settings):
    with pytest.raises(ValueError, match="validation error"):
        CompactionBinding(flow_id="f", node_id="n", output_name="result", revision="r", **settings)


async def test_standalone_preview_uses_the_connected_preview_model():
    flow = build_slot_baseline("builtin:compaction", initial_config={"compaction_keep_messages": 1})
    graph = Graph.from_payload(flow["data"])
    model = CompactionModel()
    graph.get_vertex(flow["data"]["nodes"][0]["id"]).update_raw_params({"preview_model": model}, overwrite=True)
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    terminal = graph.get_vertex(flow["data"]["nodes"][-1]["id"])
    output = terminal.custom_component.get_output("result").value
    assert isinstance(output, CompactionResult)
    assert output.dropped_count == 2
    assert "source-1" in output.summary_message.text
    assert len(model.seen) == 1


async def test_structured_output_runs_custom_compaction_with_scalar_off(tmp_path, monkeypatch):
    binding, _, _ = source(tmp_path)
    component, model = agent(tmp_path, binding)
    component.set(
        input_value="Latest question",
        output_schema=[
            {"name": "answer", "type": "str", "description": "Report", "multiple": False},
        ],
    )

    async def requirements():
        return (
            model,
            [Message(text="Old question " * 90, sender="User"), Message(text="Old answer " * 90, sender="Machine")],
            [],
        )

    def native(*_args, **_kwargs):
        msg = "Native structured output bypassed compaction"
        raise AssertionError(msg)

    monkeypatch.setattr(component, "get_agent_requirements", requirements)
    monkeypatch.setattr(CompactionModel, "with_structured_output", native)
    result = await component.json_response()
    assert result.data == {"answer": "Report [source-1]"}
    assert len(model.seen) == 2
    assert any(m.additional_kwargs.get(SUMMARY_MARKER) for m in model.seen[-1])


async def test_compiled_agent_keeps_its_reviewed_definition_until_rebuilt(tmp_path):
    binding, flow, path = source(tmp_path)
    component, model = agent(tmp_path, binding)
    runnable = component.create_agent_runnable()
    await runnable.ainvoke({"messages": history()})
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["instructions"]["value"] = "Unreviewed change"
    path.write_text(json.dumps(flow))
    await runnable.ainvoke({"messages": history()})
    assert len(model.seen) == 4
    assert "Unreviewed change" not in str(model.seen)
    with pytest.raises(CompactionFlowError, match=r"changed.*Review"):
        await events(component)


@pytest.mark.parametrize(
    "replacement",
    [
        'return "Display artifact"',
        "return CompactionResult(kept_messages=self.messages, dropped_count=1)",
    ],
)
async def test_invalid_runtime_result_is_not_applied(tmp_path, replacement):
    binding, _, _ = source(
        tmp_path, code=lambda code: code.replace("        policy =", f"        {replacement}\n        policy =")
    )
    component, model = agent(tmp_path, binding)
    original = history()
    with pytest.raises(CompactionFlowError, match="No context was removed"):
        await events(component, original)
    assert model.seen == []
    assert len(original) == 3


def test_result_cannot_drop_system_messages_or_split_tool_pairs():
    messages = [
        SystemMessage(content="Keep", id="system"),
        *history(),
        AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": "c"}]),
        ToolMessage(content="Evidence", tool_call_id="c"),
    ]
    with pytest.raises(ValueError, match="system messages"):
        CompactionResult(kept_messages=messages_to_table(messages[1:]), dropped_count=1).apply(messages)
    with pytest.raises(ValueError, match="tool result"):
        CompactionResult(kept_messages=messages_to_table([messages[0], messages[-1]]), dropped_count=4).apply(messages)


def test_result_accepts_repeated_latest_content_without_ids_and_preserves_every_system_message():
    original = [
        SystemMessage(content="Rule"),
        HumanMessage(content="Continue"),
        SystemMessage(content="Rule"),
        HumanMessage(content="Continue"),
    ]
    kept = [original[0], *original[2:]]
    result = CompactionResult(kept_messages=messages_to_table(kept), dropped_count=1)
    assert result.apply(original) == kept
    with pytest.raises(ValueError, match="system messages"):
        CompactionResult(kept_messages=messages_to_table(kept[1:]), dropped_count=2).apply(original)


async def test_custom_context_receives_the_compaction_result(tmp_path):
    from lfx.projects.context import ContextBinding, context_outputs

    binding, _, _ = source(tmp_path)
    context = build_slot_baseline(
        "builtin:context", initial_config={"context_strategy": "recent_turns", "context_turns": 1}
    )
    context["id"] = str(uuid4())
    (tmp_path / f"{context['id']}.json").write_text(json.dumps(context))
    selected = context_outputs(context["data"])[0]
    context_binding = ContextBinding(
        flow_id=context["id"],
        revision=flow_revision(context["data"]),
        node_id=selected["node_id"],
        output_name=selected["output_name"],
    )
    component, model = agent(tmp_path, binding)
    component.set(context_binding=context_binding.model_dump_json())
    raw = await events(component)
    evidence = [e["data"] for e in raw if e.get("name") == "harness_runtime"]
    assert [e["kind"] for e in evidence] == ["compacted", "context_prepared"]
    assert evidence[1]["messages_before"] == 2
    assert any(m.additional_kwargs.get(SUMMARY_MARKER) for m in model.seen[-1])
