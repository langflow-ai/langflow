"""Permission decisions execute as real graphs and survive identified approval replay."""

import json
from copy import deepcopy
from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from lfx.base.agents.permissions import PermissionFlowError
from lfx.graph.graph.base import Graph
from lfx.projects.baselines import build_slot_baseline
from lfx.projects.bindings import flow_revision
from lfx.projects.permissions import PermissionBinding, permission_outputs

from tests.unit.components.models_and_agents.agent_helpers.test_harness_permissions import (
    answer,
    begin,
    pending,
    requires_interrupts,
    setup_agent,  # noqa: F401 - reuse the real model/tool/checkpoint fixture
)


def source(tmp_path, *, action="ask", code=None):
    flow = build_slot_baseline("builtin:permission")
    flow["id"] = str(uuid4())
    template = flow["data"]["nodes"][-1]["data"]["node"]["template"]
    template["action"]["value"] = action
    if code:
        template["code"]["value"] = code(template["code"]["value"])
    path = tmp_path / f"{flow['id']}.json"
    path.write_text(json.dumps(flow))
    choice = permission_outputs(flow["data"])[0]
    binding = PermissionBinding(
        flow_id=flow["id"],
        node_id=choice["node_id"],
        output_name=choice["output_name"],
        revision=flow_revision(flow["data"]),
        version_id="reviewed-version",
    )
    return binding, flow, path


@pytest.fixture
def permission_agent(setup_agent, tmp_path):  # noqa: F811 - imported pytest fixture
    def build(binding, **kwargs):
        component, _, config, model, effects = setup_agent(**kwargs)
        component._user_id = "test-user"
        component.set(permission_binding=binding.model_dump_json())
        component.graph.context = {"project_dir": str(tmp_path)}
        return component, component.create_agent_runnable(), config, model, effects

    return build


async def collect(runnable, config):
    return [
        event["data"]
        async for event in runnable.astream_events(
            {"messages": [HumanMessage(content="Record.")]}, config, version="v2"
        )
        if event.get("name") == "harness_runtime"
    ]


@pytest.mark.parametrize(("action", "effects"), [("approve", ["1-0", "1-1"]), ("reject", [])])
async def test_real_flow_controls_parallel_tools_and_records_binding_evidence(
    tmp_path, permission_agent, action, effects
):
    binding, _, _ = source(tmp_path, action=action)
    _, runnable, config, _, observed = permission_agent(binding, parallel=True)
    evidence = await collect(runnable, config)
    assert sorted(observed) == effects
    assert len(evidence) == 2
    assert {item["tool_call_id"] for item in evidence} == {"call-1-0", "call-1-1"}
    assert all(item["decision"] == action and item["revision"] == binding.revision for item in evidence)
    assert all(item["version_id"] == "reviewed-version" and item["flow_id"] == binding.flow_id for item in evidence)


@requires_interrupts
async def test_parallel_ask_resumes_only_one_call_across_recompile(tmp_path, permission_agent):
    binding, _, _ = source(tmp_path)
    component, runnable, config, model, effects = permission_agent(binding, parallel=True)
    await begin(runnable, config)
    first = await pending(component, runnable, config)
    assert effects == []
    runnable = component.create_agent_runnable()
    await answer(component, runnable, config, first, "approve")
    assert effects == [first["action_requests"][0]["args"]["value"]]
    second = await pending(component, runnable, config)
    await answer(component, runnable, config, first, "approve")
    assert await pending(component, runnable, config) == second
    assert len(effects) == len(model.seen) == 1
    await answer(component, runnable, config, second, "reject")
    assert len(effects) == 1
    assert len(model.seen) == 2


@requires_interrupts
@pytest.mark.parametrize("action", ["approve", "ask"])
async def test_flow_cannot_skip_tool_specific_review(tmp_path, permission_agent, action):
    binding, _, _ = source(tmp_path, action=action)
    component, runnable, config, _, effects = permission_agent(binding, actions=["respond", "reject"])
    await begin(runnable, config)
    request = await pending(component, runnable, config)
    assert request["allowed_decisions"] == ["respond", "reject"]
    await answer(component, runnable, config, request, "respond", {"message": "Human result"})
    assert effects == []


@requires_interrupts
async def test_pending_decision_is_not_reexecuted_on_resume(tmp_path, permission_agent):
    marker = tmp_path / "decision-count"

    def changing(code):
        return code.replace(
            "        result = (",
            f"        from pathlib import Path\n        marker = Path({str(marker)!r})\n"
            "        action = 'approve' if marker.exists() else 'ask'\n"
            "        marker.write_text('executed')\n        self.action = action\n        result = (",
        )

    binding, _, _ = source(tmp_path, code=changing)
    component, runnable, config, _, effects = permission_agent(binding)
    await begin(runnable, config)
    request = await pending(component, runnable, config)
    assert marker.read_text() == "executed"
    runnable = component.create_agent_runnable()
    await answer(component, runnable, config, request, "reject")
    assert effects == []


@requires_interrupts
async def test_changed_binding_cannot_reuse_a_pending_approval(tmp_path, permission_agent):
    binding, flow, path = source(tmp_path)
    component, runnable, config, _, effects = permission_agent(binding)
    await begin(runnable, config)
    request = await pending(component, runnable, config)
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["action"]["value"] = "approve"
    path.write_text(json.dumps(flow))
    component.set(
        permission_binding=binding.model_copy(update={"revision": flow_revision(flow["data"])}).model_dump_json()
    )
    with pytest.raises(PermissionFlowError, match="changed"):
        await answer(component, component.create_agent_runnable(), config, request, "approve")
    assert effects == []


@requires_interrupts
@pytest.mark.parametrize(("edit", "expected"), [("allowed", ["allowed"]), ("forbidden", [])])
async def test_human_edited_arguments_are_checked_before_execution(tmp_path, permission_agent, edit, expected):
    binding, _, _ = source(
        tmp_path,
        code=lambda code: code.replace(
            "        result = (",
            "        self.action = 'reject' if self.request.data['args']['value'] == 'forbidden' else 'ask'\n"
            "        result = (",
        ),
    )
    component, runnable, config, _, effects = permission_agent(binding, actions=["approve", "edit", "reject"])
    await begin(runnable, config)
    request = await pending(component, runnable, config)
    await answer(component, component.create_agent_runnable(), config, request, "edit", {"args": {"value": edit}})
    assert effects == expected


@pytest.mark.parametrize(
    "replacement",
    [
        'return "display artifact"',
        'return Permission(action="unknown")',
        'raise RuntimeError("private permission payload")',
    ],
)
async def test_failed_permission_cannot_be_retried_into_tool_execution(tmp_path, permission_agent, replacement):
    binding, _, _ = source(
        tmp_path, code=lambda code: code.replace("        result = (", f"        {replacement}\n        result = (")
    )
    _, runnable, config, model, effects = permission_agent(binding)
    evidence = []

    async def capture():
        async for event in runnable.astream_events(
            {"messages": [HumanMessage(content="Record")]}, config, version="v2"
        ):
            if event.get("name") == "harness_runtime":
                evidence.append(event["data"])  # noqa: PERF401 - retain partial failure evidence

    with pytest.raises(PermissionFlowError) as error:
        await capture()
    assert effects == []
    assert len(model.seen) == 1
    assert len(evidence) == 1
    assert evidence[0]["kind"] == "permission_failed"
    assert "private permission payload" not in str(evidence) + str(error.value)


async def test_timeout_stops_before_tool_execution(tmp_path, permission_agent):
    binding, _, _ = source(
        tmp_path,
        code=lambda code: code.replace("    def build_permission", "    async def build_permission").replace(
            "        result = (", "        import asyncio\n        await asyncio.sleep(10)\n        result = ("
        ),
    )
    _, runnable, config, _, effects = permission_agent(binding.model_copy(update={"timeout_seconds": 0.05}))
    with pytest.raises(PermissionFlowError, match="timed out"):
        await begin(runnable, config)
    assert effects == []


async def test_stale_source_is_rejected_before_a_tool_executes(tmp_path, permission_agent):
    binding, flow, path = source(tmp_path, action="approve")
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["reason"]["value"] = "Unreviewed"
    path.write_text(json.dumps(flow))
    _, runnable, config, _, effects = permission_agent(binding)
    with pytest.raises(PermissionFlowError, match="changed"):
        await begin(runnable, config)
    assert effects == []


@pytest.mark.parametrize(("policy", "action"), [("tool_defaults", "approve"), ("ask", "ask"), ("deny", "reject")])
async def test_baseline_executes_in_standalone_preview_and_exposes_typed_result(policy, action):
    from lfx.schema.schema import build_output_logs

    flow = build_slot_baseline("builtin:permission", initial_config={"tool_policy": policy})
    graph = Graph.from_payload(deepcopy(flow["data"]), flow_id=str(uuid4()))
    results = [result async for result in graph.async_start()]
    assert all(getattr(result, "valid", True) for result in results)
    terminal = graph.get_vertex(flow["data"]["nodes"][-1]["id"])
    assert terminal.custom_component.get_output("permission").value.action == action
    preview = build_output_logs(terminal, (terminal.custom_component,))["permission"]
    assert preview["type"] == "object"
    assert preview["message"]["action"] == action


@pytest.mark.parametrize("action", ["approve", "reject", "ask"])
def test_flow_requires_resumable_message_output_even_if_baseline_does_not_ask(tmp_path, permission_agent, action):
    binding, _, _ = source(tmp_path, action=action)
    component, _, _, _, effects = permission_agent(binding)
    with pytest.raises(ValueError, match="Agent message output"):
        component.create_agent_runnable(allow_interrupts=False)
    component._vertex = None
    with pytest.raises(ValueError, match="resumable run"):
        component.create_agent_runnable()
    assert effects == []


def test_sync_invocation_fails_before_tool_execution(tmp_path, permission_agent):
    binding, _, _ = source(tmp_path, action="approve")
    _, runnable, config, _, effects = permission_agent(binding)
    with pytest.raises(NotImplementedError, match="async-only"):
        runnable.invoke({"messages": [HumanMessage(content="Record")]}, config)
    assert effects == []


async def test_flow_receives_actual_call_and_harness_identity(tmp_path, permission_agent):
    binding, _, _ = source(
        tmp_path,
        action="approve",
        code=lambda code: code.replace(
            "        result = (",
            "        import json\n        self.reason = json.dumps(self.request.data)\n        result = (",
        ),
    )
    component, runnable, config, _, effects = permission_agent(binding)
    evidence = await collect(runnable, config)
    payload = json.loads(evidence[0]["reason"])
    assert payload == {
        "tool_name": "record",
        "args": {"value": "1-0"},
        "tool_call_id": "call-1-0",
        "approval_actions": [],
        "run_id": component._agent_thread_id(),
        "session_id": component.graph.session_id,
    }
    assert effects == ["1-0"]


@requires_interrupts
async def test_changed_hook_arguments_cannot_reuse_a_checkpointed_decision(tmp_path, permission_agent, monkeypatch):
    from lfx.base.agents.hooks import HookDecision
    from lfx.projects.hooks import HookFlowRunner

    from tests.unit.components.models_and_agents.agent_helpers.test_harness_hooks import hook_flow

    hook, _, _ = hook_flow(tmp_path, action="modify")
    values = iter(["shown to user", "changed on resume"])

    async def changing_hook(_self, _binding, _payload):
        return HookDecision(action="modify", modified_payload={"args": {"value": next(values)}})

    monkeypatch.setattr(HookFlowRunner, "__call__", changing_hook)
    binding, _, _ = source(tmp_path)
    component, _, config, _, effects = permission_agent(binding)
    component.set(hook_bindings=json.dumps([hook.model_dump()]))
    runnable = component.create_agent_runnable()
    await begin(runnable, config)
    request = await pending(component, runnable, config)
    assert request["action_requests"][0]["args"] == {"value": "shown to user"}
    with pytest.raises(PermissionFlowError, match="changed"):
        await answer(component, runnable, config, request, "approve")
    assert effects == []


@requires_interrupts
async def test_agent_event_stream_pauses_resumes_and_retains_reviewed_evidence(tmp_path, permission_agent, monkeypatch):
    binding, flow, path = source(tmp_path)
    flow["data"]["nodes"][-1]["data"]["node"]["template"]["reason"]["value"] = "Review this record before writing."
    path.write_text(json.dumps(flow))
    binding = binding.model_copy(update={"revision": flow_revision(flow["data"])})
    component, runnable, _, _, effects = permission_agent(binding)
    pauses = []
    component.graph.request_pause = lambda **kwargs: pauses.append(kwargs)

    async def send(message, **_kwargs):
        return message

    async def remove(*_args, **_kwargs):
        pass

    monkeypatch.setattr(component, "send_message", send)
    monkeypatch.setattr(component, "_send_message_event", remove)
    monkeypatch.setattr(component, "_get_shared_callbacks", list)
    await component.run_agent(runnable)
    request = pauses[-1]["data"]
    assert request["prompt"] == "Review this record before writing."
    assert effects == []
    component.graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
    result = await component.run_agent(component.create_agent_runnable())
    assert result.properties.state == "complete"
    assert effects == ["1-0"]
    evidence = [block for block in result.content_blocks if getattr(block, "title", None) == "Tool permission decided"]
    assert binding.revision in str(evidence)
    assert '"phase": "human"' in str(evidence)


@pytest.mark.parametrize("timeout", [0, -1, 301, float("inf"), float("nan")])
def test_permission_binding_rejects_invalid_timeout(tmp_path, timeout):
    binding, _, _ = source(tmp_path)
    with pytest.raises(ValueError, match="timeout_seconds"):
        PermissionBinding.model_validate({**binding.model_dump(), "timeout_seconds": timeout})


def test_permission_contract_rejects_disconnected_and_multiple_request_sources():
    data = build_slot_baseline("builtin:permission")["data"]
    assert permission_outputs(data)
    disconnected = {**data, "edges": []}
    with pytest.raises(ValueError, match="Request"):
        permission_outputs(disconnected)
    data["nodes"].append(deepcopy(data["nodes"][0]))
    with pytest.raises(ValueError, match="one Permission Request"):
        permission_outputs(data)


async def test_permission_model_tokens_stay_out_of_the_agent_answer(tmp_path, permission_agent):
    from lfx.components.models_and_agents.agent_helpers.graph_event_adapter import adapt_graph_events_to_executor_shape

    binding, _, _ = source(
        tmp_path,
        action="approve",
        code=lambda code: code.replace("    def build_permission", "    async def build_permission").replace(
            "        result = (",
            "        from langchain_core.language_models.fake_chat_models import FakeListChatModel\n"
            "        await FakeListChatModel(responses=['INTERNAL PERMISSION MODEL']).ainvoke('Inspect')\n"
            "        result = (",
        ),
    )
    _, runnable, config, _, effects = permission_agent(binding)
    raw = []

    async def events():
        async for event in runnable.astream_events(
            {"messages": [HumanMessage(content="Record")]}, config, version="v2"
        ):
            raw.append(event)
            yield event

    presented = [event async for event in adapt_graph_events_to_executor_shape(events())]
    assert any(
        event["event"].startswith("on_chat_model") and "harness:permission" in event.get("tags", []) for event in raw
    )
    assert not any("harness:permission" in event.get("tags", []) for event in presented)
    assert presented[-1]["data"]["output"].return_values["output"] == '{"result": "done"}'
    assert effects == ["1-0"]
