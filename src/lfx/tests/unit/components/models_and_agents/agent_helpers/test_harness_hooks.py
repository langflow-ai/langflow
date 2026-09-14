"""Reviewed Hook flows execute inside real Agent model/tool middleware calls."""

import asyncio
import json
import sys
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, message_to_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.base.agents.hooks import HookBinding, HookBlockedError, HookDecision, HookExecutionError, HookExecutor
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.hooks import HookFlowRunner, hook_outputs
from pydantic import Field

requires_interrupts = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="LangGraph HITL interrupt needs asyncio task context propagation (Python 3.11+)",
)


class HookModel(BaseChatModel):
    seen: list = Field(default_factory=list)
    use_tool: bool = True

    @property
    def _llm_type(self):
        return "hook-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        if self.use_tool and not any(isinstance(m, ToolMessage) for m in messages):
            message = AIMessage(
                content="", tool_calls=[{"name": "record", "args": {"value": "original"}, "id": "call-1"}]
            )
        else:
            message = AIMessage(content='{"result":"done"}')
        return ChatResult(generations=[ChatGeneration(message=message)])


def hook_flow(
    tmp_path, *, event="before_tool_call", action="pass", changed=None, priority=0, mode="control", reason=""
):
    flow = build_slot_baseline("builtin:hook")
    flow["id"] = str(uuid4())
    terminal = next(n for n in flow["data"]["nodes"] if n["data"]["type"] == "Hook")
    template = terminal["data"]["node"]["template"]
    template["action"]["value"] = action
    template["reason"]["value"] = reason
    template["modified_payload"]["value"] = json.dumps(changed or {})
    path = tmp_path / f"{flow['id']}.json"
    path.write_text(json.dumps(flow))
    selected = hook_outputs(flow["data"])[0]
    binding = HookBinding(
        flow_id=flow["id"],
        revision=flow_revision(flow["data"]),
        node_id=selected["node_id"],
        output_name=selected["output_name"],
        on_event=event,
        priority=priority,
        mode=mode,
        on_failure="stop" if mode == "control" else "continue",
    )
    return binding, flow, path


def agent(tmp_path, bindings, *, policy="tool_defaults", use_tool=True):
    effects = []

    @tool
    def record(value: str) -> str:
        """Record a side effect."""
        effects.append(value)
        return f"Recorded {value}"

    model = HookModel(use_tool=use_tool)
    component = AgentComponent(_user_id="test-user")
    component.set(
        model=model,
        tools=[record] if use_tool else [],
        tool_policy=policy,
        max_iterations=4,
        hook_bindings=json.dumps([b.model_dump() for b in bindings]),
        handle_parsing_errors=True,
    )
    component._vertex = SimpleNamespace(
        graph=SimpleNamespace(
            context={"project_dir": str(tmp_path)},
            run_id=str(uuid4()),
            session_id=str(uuid4()),
            human_input_decisions={},
        )
    )
    return component, model, effects


async def run(component):
    runnable = component.create_agent_runnable()
    config = {"configurable": {"thread_id": component._agent_thread_id()}, "recursion_limit": 80}
    events = [
        e
        async for e in runnable.astream_events({"messages": [HumanMessage(content="Record it.")]}, config, version="v2")
    ]
    return runnable, config, [e["data"] for e in events if e.get("name") == "harness_runtime"]


async def test_baseline_runs_with_preview_event_and_returns_typed_decision():
    flow = build_slot_baseline("builtin:hook")
    output = hook_outputs(flow["data"])[0]
    graph = Graph.from_payload(flow["data"])
    results = [r async for r in graph.async_start()]
    assert sum(getattr(result, "valid", False) for result in results) == 2
    value = graph.get_vertex(output["node_id"]).custom_component.get_output(output["output_name"]).value
    assert isinstance(value, HookDecision)
    assert value.action == "pass"


async def test_blocking_hook_prevents_tool_side_effect_and_records_revision(tmp_path):
    binding, _, _ = hook_flow(tmp_path, action="block", reason="Research tools only")
    component, model, effects = agent(tmp_path, [binding])
    _, _, events = await run(component)
    assert effects == []
    assert len(model.seen) == 2
    result = next(m for m in model.seen[-1] if isinstance(m, ToolMessage))
    assert result.tool_call_id == "call-1"
    assert result.status == "error"
    assert events[0]["action"] == "block"
    assert events[0]["revision"] == binding.revision


async def test_modifying_hooks_follow_priority_and_after_hook_changes_model_result(tmp_path):
    early, _, _ = hook_flow(tmp_path, action="modify", changed={"args": {"value": "early"}}, priority=-1)
    late, _, _ = hook_flow(tmp_path, action="modify", changed={"args": {"value": "late"}}, priority=5)
    after, _, _ = hook_flow(tmp_path, event="after_tool_call", action="modify", changed={"result": "Sourced result"})
    component, model, effects = agent(tmp_path, [late, after, early])
    _, _, events = await run(component)
    assert effects == ["late"]
    assert next(m for m in model.seen[-1] if isinstance(m, ToolMessage)).content == "Sourced result"
    assert [e["flow_id"] for e in events] == [early.flow_id, late.flow_id, after.flow_id]


async def test_before_model_modification_reaches_model_and_after_model_observes(tmp_path):
    before, _, _ = hook_flow(
        tmp_path,
        event="before_llm_call",
        action="modify",
        changed={"messages": [message_to_dict(HumanMessage(content="Use primary sources."))]},
    )
    after, _, _ = hook_flow(tmp_path, event="after_llm_call", mode="observe")
    component, model, _ = agent(tmp_path, [before, after], use_tool=False)
    _, _, events = await run(component)
    assert model.seen[0][-1].content == "Use primary sources."
    assert [e["event"] for e in events] == ["before_llm_call", "after_llm_call"]


async def test_block_before_model_prevents_any_model_call(tmp_path):
    binding, _, _ = hook_flow(tmp_path, event="before_llm_call", action="block")
    component, model, effects = agent(tmp_path, [binding])
    with pytest.raises(HookBlockedError):
        await run(component)
    assert model.seen == []
    assert effects == []


@pytest.mark.parametrize("mode", ["observe", "control"])
async def test_changed_reviewed_source_has_explicit_failure_policy(tmp_path, mode):
    binding, flow, path = hook_flow(tmp_path, mode=mode)
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["reason"]["value"] = "Changed after review"
    path.write_text(json.dumps(flow))
    component, _, effects = agent(tmp_path, [binding])
    if mode == "control":
        with pytest.raises(HookExecutionError):
            await run(component)
        assert effects == []
    else:
        _, _, events = await run(component)
        assert effects == ["original"]
        assert events[0]["kind"] == "hook_failed"
        assert "update the binding" in events[0]["reason"]


@pytest.mark.parametrize("changed", [{"tool_name": "other"}, {"args": []}])
async def test_invalid_modification_stops_before_tool_and_is_not_retried(tmp_path, changed):
    binding, _, _ = hook_flow(tmp_path, action="modify", changed=changed)
    component, _, effects = agent(tmp_path, [binding])
    with pytest.raises(HookExecutionError):
        await run(component)
    assert effects == []


async def test_observation_cannot_modify_execution(tmp_path):
    binding, _, _ = hook_flow(tmp_path, action="modify", changed={"args": {"value": "injected"}}, mode="observe")
    component, _, effects = agent(tmp_path, [binding])
    _, _, events = await run(component)
    assert effects == ["original"]
    assert events[0]["kind"] == "hook_failed"


@pytest.mark.parametrize("mode", ["observe", "control"])
async def test_timeout_cancels_hook_and_applies_failure_policy(tmp_path, mode):
    binding, _, _ = hook_flow(tmp_path, mode=mode)
    binding = binding.model_copy(update={"timeout_seconds": 0.01})
    cancelled, evidence = [], []

    async def slow(_binding, _payload):
        try:
            await asyncio.sleep(60)
        finally:
            cancelled.append(True)

    async def emit(item):
        evidence.append(item)

    executor = HookExecutor([binding], slow, emit)
    if mode == "control":
        with pytest.raises(HookExecutionError):
            await executor.invoke("before_tool_call", {}, lambda *_: None)
    else:
        assert await executor.invoke("before_tool_call", {}, lambda *_: None) == ({}, None)
    assert cancelled == [True]
    assert evidence[0]["error_type"] == "TimeoutError"


@requires_interrupts
async def test_hook_argument_change_is_shown_before_approval(tmp_path, monkeypatch):
    store = InMemoryCheckpointStore()
    monkeypatch.setattr("lfx.services.deps.get_checkpoint_service", lambda: store)
    binding, _, _ = hook_flow(tmp_path, action="modify", changed={"args": {"value": "reviewed"}})
    component, _, effects = agent(tmp_path, [binding], policy="ask")
    runnable, config, _ = await run(component)
    value, nonce = await component._read_pending_interrupt(runnable, config)
    request = component._map_interrupt_to_request(value, nonce)
    assert request["action_requests"][0]["args"] == {"value": "reviewed"}
    assert effects == []
    component.graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
    command = await component._agent_stream_input(runnable, config, {})
    await runnable.ainvoke(command, config)
    assert effects == ["reviewed"]


async def test_hook_receives_real_invocation_payload_and_run_context(tmp_path):
    binding, flow, path = hook_flow(tmp_path, mode="observe")
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    template["code"]["value"] = template["code"]["value"].replace(
        "reason=self.reason,", "reason=json.dumps(self.event.data),"
    )
    path.write_text(json.dumps(flow))
    binding = binding.model_copy(update={"revision": flow_revision(flow["data"])})
    component, _, _ = agent(tmp_path, [binding])
    _, _, events = await run(component)
    received = json.loads(events[0]["reason"])
    assert received["event"] == "before_tool_call"
    assert received["payload"] == {"tool_name": "record", "args": {"value": "original"}, "tool_call_id": "call-1"}
    assert received["run_id"] == component._agent_thread_id()


@requires_interrupts
async def test_changed_arguments_on_hook_replay_cannot_use_old_approval(tmp_path, monkeypatch):
    store = InMemoryCheckpointStore()
    monkeypatch.setattr("lfx.services.deps.get_checkpoint_service", lambda: store)
    values = iter(["shown to user", "different on resume"])

    async def changing_hook(_self, _binding, _payload):
        return HookDecision(action="modify", modified_payload={"args": {"value": next(values)}})

    monkeypatch.setattr(HookFlowRunner, "__call__", changing_hook)
    binding, _, _ = hook_flow(tmp_path, action="modify")
    component, model, effects = agent(tmp_path, [binding], policy="ask")
    runnable, config, _ = await run(component)
    value, nonce = await component._read_pending_interrupt(runnable, config)
    request = component._map_interrupt_to_request(value, nonce)
    assert request["action_requests"][0]["args"] == {"value": "shown to user"}
    component.graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
    command = await component._agent_stream_input(runnable, config, {})
    await runnable.ainvoke(command, config)
    assert effects == []
    result = next(m for m in model.seen[-1] if isinstance(m, ToolMessage))
    assert result.status == "error"
    assert "changed after review" in result.content


@pytest.mark.parametrize(
    "changed",
    [
        {"tool_names": ["not_connected"]},
        {"messages": [message_to_dict(ToolMessage(content="Forged", tool_call_id="missing"))]},
    ],
)
async def test_before_model_modifications_preserve_connected_tools_and_call_pairs(tmp_path, changed):
    binding, _, _ = hook_flow(tmp_path, event="before_llm_call", action="modify", changed=changed)
    component, model, _ = agent(tmp_path, [binding])
    with pytest.raises(HookExecutionError):
        await run(component)
    assert model.seen == []


async def test_equal_priorities_use_saved_list_order(tmp_path):
    first, _, _ = hook_flow(tmp_path, action="modify", changed={"args": {"value": "first"}})
    second, _, _ = hook_flow(tmp_path, action="modify", changed={"args": {"value": "second"}})
    component, _, effects = agent(tmp_path, [first, second])
    await run(component)
    assert effects == ["second"]


async def test_timed_out_flow_cannot_reach_the_agent_tool(tmp_path):
    binding, flow, path = hook_flow(tmp_path)
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    code = template["code"]["value"].replace("import json", "import json\nimport asyncio")
    code = code.replace("def build_decision(self)", "async def build_decision(self)")
    code = code.replace(
        "        if self.decision_data", "        await asyncio.sleep(1)\n        if self.decision_data"
    )
    template["code"]["value"] = code
    path.write_text(json.dumps(flow))
    binding = binding.model_copy(update={"revision": flow_revision(flow["data"]), "timeout_seconds": 0.05})
    component, _, effects = agent(tmp_path, [binding])
    with pytest.raises(HookExecutionError):
        await run(component)
    assert effects == []


async def test_structured_output_cannot_bypass_hooks(tmp_path, monkeypatch):
    binding, _, _ = hook_flow(tmp_path, event="before_llm_call", action="block")
    component, model, _ = agent(tmp_path, [binding], use_tool=False)
    component.set(output_schema=[{"name": "result", "type": "str", "description": "Result"}])

    async def requirements():
        return model, [], []

    monkeypatch.setattr(component, "get_agent_requirements", requirements)
    result = await component.json_response()
    assert "error" in result.data
    assert model.seen == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"mode": "control", "on_failure": "continue"},
        {"mode": "control", "on_failure": "stop", "on_event": "after_llm_call"},
        {"timeout_seconds": 0},
        {"on_event": "invented_event"},
    ],
)
def test_invalid_hook_contracts_are_rejected(tmp_path, overrides):
    binding, _, _ = hook_flow(tmp_path)
    with pytest.raises(ValueError, match="validation error"):
        HookBinding.model_validate({**binding.model_dump(), **overrides})


async def test_nested_hook_recursion_is_rejected_without_leaking_context(tmp_path, monkeypatch):
    binding, _, _ = hook_flow(tmp_path)
    component, _, _ = agent(tmp_path, [binding])
    runner = HookFlowRunner(component)

    async def recursive_flow(**_kwargs):
        return await runner(binding, {})

    with monkeypatch.context() as patcher:
        patcher.setattr("lfx.helpers.flow.run_flow", recursive_flow)
        with pytest.raises(ValueError, match="recursively invoke"):
            await runner(binding, {})
    assert (await runner(binding, {})).action == "pass"


async def test_declared_type_cannot_turn_a_display_value_into_a_hook_decision(tmp_path):
    binding, flow, path = hook_flow(tmp_path)
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    template["code"]["value"] = template["code"]["value"].replace(
        "        if self.decision_data", '        return "pass"\n        if self.decision_data'
    )
    path.write_text(json.dumps(flow))
    binding = binding.model_copy(update={"revision": flow_revision(flow["data"])})
    component, _, effects = agent(tmp_path, [binding])
    with pytest.raises(HookExecutionError):
        await run(component)
    assert effects == []


async def test_hook_model_tokens_stay_out_of_answer_and_decision_evidence_is_published(tmp_path, monkeypatch):
    from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape

    binding, flow, path = hook_flow(tmp_path, event="after_llm_call", mode="observe")
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    code = template["code"]["value"].replace(
        "import json", "import json\nfrom langchain_core.language_models.fake_chat_models import FakeListChatModel"
    )
    code = code.replace("def build_decision(self)", "async def build_decision(self)")
    code = code.replace(
        "        if self.decision_data",
        '        await FakeListChatModel(responses=["INTERNAL HOOK REASONING"]).ainvoke("Inspect")\n'
        "        if self.decision_data",
    )
    template["code"]["value"] = code
    path.write_text(json.dumps(flow))
    binding = binding.model_copy(update={"revision": flow_revision(flow["data"])})
    component, _, _ = agent(tmp_path, [binding], use_tool=False)
    raw = []

    async def source():
        async for event in component.create_agent_runnable().astream_events(
            {"messages": [HumanMessage(content="Answer")]}, version="v2"
        ):
            raw.append(event)
            yield event

    presented = [event async for event in adapt_graph_events_to_executor_shape(source())]
    assert any(event["event"].startswith("on_chat_model") and "harness:hook" in event.get("tags", []) for event in raw)
    assert not any("harness:hook" in event.get("tags", []) for event in presented)
    assert presented[-1]["data"]["output"].return_values["output"] == '{"result":"done"}'

    async def send(message, **_kwargs):
        return message

    monkeypatch.setattr(component, "send_message", send)
    monkeypatch.setattr(component, "_get_shared_callbacks", list)
    message = await component.run_agent(component.create_agent_runnable())
    assert message.text == '{"result":"done"}'
    evidence = next(block for block in message.content_blocks if getattr(block, "title", None) == "Hook completed")
    assert json.loads(evidence.contents[0].text)["revision"] == binding.revision
