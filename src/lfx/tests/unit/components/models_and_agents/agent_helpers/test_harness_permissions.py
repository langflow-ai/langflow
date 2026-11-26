"""Execute permission policies with real agent graphs, tools, and persisted checkpoints."""

import sys
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.graph.checkpoint.store import InMemoryCheckpointStore
from pydantic import Field

requires_interrupts = pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="LangGraph HITL interrupt needs asyncio task context propagation (Python 3.11+)",
)


class PermissionModel(BaseChatModel):
    seen: list = Field(default_factory=list)
    parallel: bool = False
    turns: int = 1

    @property
    def _llm_type(self):
        return "permission-test"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        self.seen.append(deepcopy(messages))
        results = [m for m in messages if isinstance(m, ToolMessage)]
        if len(results) >= self.turns * (2 if self.parallel else 1):
            response = AIMessage(content='{"result": "done"}')
        else:
            turn = len(results) + 1
            calls = [
                {"name": "record", "args": {"value": f"{turn}-{i}"}, "id": f"call-{turn}-{i}", "type": "tool_call"}
                for i in range(2 if self.parallel else 1)
            ]
            response = AIMessage(content="", tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=response)])


@pytest.fixture
def setup_agent(monkeypatch):
    store = InMemoryCheckpointStore()
    monkeypatch.setattr("lfx.services.deps.get_checkpoint_service", lambda: store)

    def build(policy="tool_defaults", *, parallel=False, turns=1, actions=None):
        effects = []

        @tool
        def record(value: str) -> str:
            """Record a value as an observable side effect."""
            effects.append(value)
            return value

        record.metadata = {"approval_actions": actions or []}
        model = PermissionModel(parallel=parallel, turns=turns)
        component = AgentComponent()
        component.set(model=model, tools=[record], tool_policy=policy, max_iterations=5, handle_parsing_errors=True)
        component._vertex = SimpleNamespace(
            graph=SimpleNamespace(run_id=str(uuid4()), session_id=str(uuid4()), human_input_decisions={})
        )
        runnable = component.create_agent_runnable()
        config = {"configurable": {"thread_id": component._agent_thread_id()}, "recursion_limit": 60}
        return component, runnable, config, model, effects

    return build


async def begin(runnable, config):
    return await runnable.ainvoke({"messages": [HumanMessage(content="Record the values.")]}, config)


async def pending(component, runnable, config):
    value, nonce = await component._read_pending_interrupt(runnable, config)
    assert value
    assert nonce
    return component._map_interrupt_to_request(value, nonce)


async def answer(component, runnable, config, request, action, values=None):
    component.graph.human_input_decisions = {request["request_id"]: {"action_id": action, "values": values or {}}}
    command = await component._agent_stream_input(runnable, config, {"messages": [HumanMessage(content="Wrong rerun")]})
    return await runnable.ainvoke(command, config)


async def test_deny_has_no_side_effect_and_emits_call_evidence_even_with_retries(setup_agent):
    _, runnable, config, model, effects = setup_agent("deny", parallel=True, actions=["approve", "reject"])
    events = [
        event
        async for event in runnable.astream_events(
            {"messages": [HumanMessage(content="Record.")]}, config, version="v2"
        )
    ]
    assert effects == []
    assert len(model.seen) == 2
    assert all(m.status == "error" for m in model.seen[-1] if isinstance(m, ToolMessage))
    evidence = [e["data"] for e in events if e.get("name") == "harness_runtime"]
    assert {e["tool_call_id"] for e in evidence} == {"call-1-0", "call-1-1"}
    assert all(e["decision"] == "reject" and e["policy"] == "deny" for e in evidence)


async def test_tool_defaults_preserve_ungated_execution(setup_agent):
    _, runnable, config, _, effects = setup_agent()
    await begin(runnable, config)
    assert effects == ["1-0"]


@pytest.mark.parametrize("policy", ["tool_defaults", "ask"])
@requires_interrupts
@pytest.mark.parametrize(
    ("decision", "values", "expected"),
    [
        ("approve", {}, ["1-0"]),
        ("edit", {"args": {"value": "reviewed"}}, ["reviewed"]),
        ("reject", {"message": "Denied"}, []),
        ("respond", {"message": "Human result"}, []),
    ],
)
async def test_tool_decisions_preserve_existing_vocabulary(setup_agent, policy, decision, values, expected):
    component, runnable, config, model, effects = setup_agent(policy, actions=["approve", "edit", "reject", "respond"])
    await begin(runnable, config)
    assert effects == []
    request = await pending(component, runnable, config)
    assert request["action_requests"][0]["tool_call_id"] == "call-1-0"
    # Recompile against the same store, as a fresh worker does after a persisted pause.
    runnable = component.create_agent_runnable()
    await answer(component, runnable, config, request, decision, values)
    assert effects == expected
    assert len(model.seen) == 2
    assert (await component._read_pending_interrupt(runnable, config))[0] is None


@requires_interrupts
async def test_parallel_approval_resumes_only_identified_call_and_stale_answer_cannot_resolve_next(setup_agent):
    component, runnable, config, model, effects = setup_agent("ask", parallel=True)
    await begin(runnable, config)
    first = await pending(component, runnable, config)
    assert len(first["action_requests"]) == 1
    await answer(component, runnable, config, first, "approve")
    expected = first["action_requests"][0]["args"]["value"]
    assert effects == [expected]
    second = await pending(component, runnable, config)
    assert second["request_id"] != first["request_id"]
    await answer(component, runnable, config, first, "approve")
    assert effects == [expected]
    assert await pending(component, runnable, config) == second
    assert len(model.seen) == 1
    await answer(component, runnable, config, second, "reject")
    assert effects == [expected]
    assert len(model.seen) == 2


@requires_interrupts
async def test_later_model_turn_requires_fresh_approval_and_bare_request_cannot_authorize_it(setup_agent):
    component, runnable, config, model, effects = setup_agent("ask", turns=2)
    await begin(runnable, config)
    first = await pending(component, runnable, config)
    await answer(component, runnable, config, first, "approve")
    second = await pending(component, runnable, config)
    assert second["request_id"] != first["request_id"]
    bare = {"request_id": f"{component._id}:{component._agent_thread_id()}"}
    await answer(component, runnable, config, bare, "approve")
    assert effects == ["1-0"]
    assert len(model.seen) == 2
    await answer(component, runnable, config, second, "approve")
    assert effects == ["1-0", "2-0"]


@pytest.mark.parametrize("policy", ["ask", "tool_defaults"])
async def test_structured_output_cannot_bypass_tool_approval(setup_agent, monkeypatch, policy):
    component, _, _, model, effects = setup_agent(policy, actions=["approve", "reject"])
    component.set(output_schema=[{"name": "result", "type": "str", "description": "Result"}])

    async def requirements():
        return model, [], component.tools

    monkeypatch.setattr(component, "get_agent_requirements", requirements)
    result = await component.json_response()
    assert "error" in result.data, (result.data, model.seen, effects)
    assert "Agent message output" in result.data["error"]
    assert effects == []
    assert model.seen == []


@requires_interrupts
async def test_unknown_approval_action_does_not_default_to_approve(setup_agent):
    component, runnable, config, _, effects = setup_agent("ask")
    await begin(runnable, config)
    request = await pending(component, runnable, config)
    with pytest.raises(ValueError, match="Unknown tool approval decision"):
        await answer(component, runnable, config, request, "unexpected")
    assert effects == []


async def test_structured_output_honors_deny_without_requiring_approval(setup_agent, monkeypatch):
    component, _, _, model, effects = setup_agent("deny", actions=["approve", "reject"])
    component.set(output_schema=[{"name": "result", "type": "str", "description": "Result"}])

    async def requirements():
        return model, [], component.tools

    monkeypatch.setattr(component, "get_agent_requirements", requirements)
    result = await component.json_response()
    assert result.data == {"result": "done"}
    assert effects == []
    assert any(isinstance(message, ToolMessage) and message.status == "error" for message in model.seen[-1])


def test_deny_also_blocks_synchronous_tool_execution(setup_agent):
    _, runnable, config, _, effects = setup_agent("deny")
    result = runnable.invoke({"messages": [HumanMessage(content="Record.")]}, config)
    assert effects == []
    assert any(isinstance(message, ToolMessage) and message.status == "error" for message in result["messages"])


async def test_approval_without_a_resumable_run_fails_before_execution():
    @tool
    def record() -> str:
        """Must not execute."""
        raise AssertionError

    component = AgentComponent()
    component.set(model=PermissionModel(), tools=[record], tool_policy="ask")
    with pytest.raises(ValueError, match="resumable run"):
        component.create_agent_runnable()


@requires_interrupts
async def test_agent_event_path_pauses_resumes_and_publishes_permission_evidence(setup_agent, monkeypatch):
    component, runnable, _, _, effects = setup_agent("ask")
    pauses = []
    component.graph.session_id = str(uuid4())
    component.graph.request_pause = lambda **kwargs: pauses.append(kwargs)

    async def send(message, **_kwargs):
        return message

    async def remove(*_args, **_kwargs):
        pass

    monkeypatch.setattr(component, "send_message", send)
    monkeypatch.setattr(component, "_send_message_event", remove)
    monkeypatch.setattr(component, "_get_shared_callbacks", list)
    await component.run_agent(runnable)
    assert effects == []
    assert pauses[-1]["reason"] == "human_input_required"
    request = pauses[-1]["data"]
    component.graph.human_input_decisions = {request["request_id"]: {"action_id": "approve"}}
    result = await component.run_agent(component.create_agent_runnable())
    assert result.properties.state == "complete"
    assert effects == ["1-0"]
    evidence = next(block for block in result.content_blocks if block.title == "Tool permission decided")
    assert "call-1-0" in evidence.contents[0].text
    assert '"decision": "approve"' in evidence.contents[0].text
