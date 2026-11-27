"""Parity: HarnessLoopRuntime applies the same harness controls as the packaged Agent.

The main test runs one scripted harness through the packaged path
(`AgentComponent.create_agent_runnable`) and through the runtime, with the real
`AgentComponent._build_middleware` list, and compares everything a middleware can see or emit.
The rest run small recording middleware through `create_agent` and the runtime and compare what
they logged, or check where the runtime refuses instead of drifting. Only the reviewed-flow
executor is faked, except in the permission test, which runs the real flow.
"""

import asyncio
import json
from copy import deepcopy
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Annotated
from uuid import UUID, uuid4

import lfx.custom  # noqa: F401  (breaks an import cycle, like the test runner does)
import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    ModelCallLimitMiddleware,
    hook_config,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command
from lfx.base.agents.compaction import CompactionResult
from lfx.base.agents.hooks import HookBinding, HookDecision
from lfx.base.agents.loop_runtime import HarnessLoopRuntime
from lfx.base.agents.permissions import Permission
from lfx.components.models_and_agents.agent import AgentComponent
from lfx.components.models_and_agents.agent_helpers.source_evidence import EVIDENCE_STATE_KEY
from lfx.projects import invocation
from lfx.projects.artifacts import SOURCE_EVIDENCE_KIND
from lfx.projects.compaction import COMPACTION_INPUT, CompactionBinding
from lfx.projects.context import AGENT_CONTEXT, ContextBinding
from lfx.projects.hooks import HOOK_EVENT_CONTEXT
from lfx.projects.permissions import PERMISSION_INPUT, PermissionBinding
from lfx.projects.skills import HarnessSkills, skill_pack_manifest
from lfx.run.hitl import NestedHITLUnsupportedError
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message
from pydantic import BaseModel, Field

from tests.unit.components.models_and_agents.agent_helpers.test_permission_flows import source

PROJECT_ID = UUID(int=1)
FLOW_ID = str(UUID(int=2))
ACTIVE_SKILL_KEY = "harness_active_skill"


class ScriptedModel(BaseChatModel):
    """Emits scripted tool calls by call index. Records what each call saw and what was bound."""

    script: list = Field(default_factory=list)
    seen: list = Field(default_factory=list)
    bound: list = Field(default_factory=list)
    delay: float = 0

    @property
    def _llm_type(self):
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        self.bound.append(([t.name for t in tools], kwargs))
        return self

    def bind(self, **kwargs):
        self.bound.append(([], kwargs))
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        index = len(self.seen)
        self.seen.append(deepcopy(messages))
        calls = self.script[index] if index < len(self.script) else []
        message = AIMessage(content="" if calls else "done", tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=message)])

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(self.delay)
        return self._generate(messages, stop, run_manager, **kwargs)


class EventSink(AsyncCallbackHandler):
    def __init__(self):
        self.events = []

    async def on_custom_event(self, name, data, **kwargs):  # noqa: ARG002
        if name == "harness_runtime":
            self.events.append(data)


def _call(name, args, cid):
    return {"name": name, "args": args, "id": cid, "type": "tool_call"}


def _binding(cls, **extra):
    return cls(flow_id=FLOW_ID, node_id="n", output_name="o", revision="r" * 8, **extra)


def _human():
    return [HumanMessage(content="Find animal facts and clean up.", id="h1")]


@dataclass
class Flows:
    """What the scripted reviewed flows decide, and what they were asked."""

    permission_action: str = "approve"
    calls: list = field(default_factory=list)


@pytest.fixture
def flows(monkeypatch):
    """Replace every reviewed flow with a scripted decision and record what it was asked."""
    state = Flows()

    async def fake(self, binding, context):  # noqa: ARG001
        if self.label == "Hook":
            ctx = context[HOOK_EVENT_CONTEXT]
            payload = ctx["payload"]
            state.calls.append(("hook", ctx["event"], payload.get("tool_name")))
            if ctx["event"] == "before_tool_call" and payload["tool_name"] == "search" and "query" in payload["args"]:
                return HookDecision(
                    action="modify", modified_payload={"args": {"query": payload["args"]["query"].upper()}}
                )
            return HookDecision()
        if self.label == "permission":
            request = context[PERMISSION_INPUT]
            state.calls.append(("permission", request["tool_name"]))
            if request["tool_name"] == "delete_file":
                return Permission(action="reject", reason="Permission flow: deletes are not allowed.")
            return Permission(action=state.permission_action)
        if self.label == "context":
            rows = context[AGENT_CONTEXT]["messages"]
            last_human = max(i for i, r in enumerate(rows) if r["type"] == "human")
            state.calls.append(("context", len(rows), len(rows) - last_human))
            return DataFrame(deepcopy(rows[last_human:]))
        if self.label == "compaction":
            request = context[COMPACTION_INPUT]
            rows = request["messages"]
            cut = max(i for i, r in enumerate(rows) if r["type"] == "ai")
            state.calls.append(("compaction", len(rows), cut, request["estimated_tokens"]))
            return CompactionResult(
                kept_messages=DataFrame(deepcopy(rows[cut:]), columns=["type", "data"]),
                summary_message=Message(text=f"Summary of {cut} earlier messages."),
                dropped_count=cut,
            )
        raise AssertionError(self.label)

    monkeypatch.setattr(invocation.ReviewedFlowRunner, "__call__", fake)
    return state


def build(script_prefix=(), *, retry=True, harness=True, **settings):
    """A fresh Agent with every harness control wired, plus its scripted model and tool side effects."""
    effects: list = []

    @tool(response_format="content_and_artifact")
    def search(query: str):
        """Search the web."""
        effects.append(("search", query))
        source = {"uri": f"https://example.org/{query}", "title": query, "content": f"captured {query}"}
        return f"results for {query}: " + "lorem ipsum " * 150, {"kind": SOURCE_EVIDENCE_KIND, "source": source}

    @tool
    def delete_file(path: str) -> str:
        """Delete a file."""
        effects.append(("delete_file", path))
        return f"deleted {path}"

    manifest = skill_pack_manifest(
        PROJECT_ID,
        "Research",
        {"skills": [{"name": "verify-sources", "description": "Verify sources", "instructions": "SKILL BODY: cite."}]},
    )
    skill_key = f"{PROJECT_ID}:verify-sources"
    model = ScriptedModel(
        script=[
            *script_prefix,
            [_call("search", {"query": "cats"}, "c1"), _call("delete_file", {"path": "/etc/hosts"}, "c2")],
            [_call("activate_skill", {"skill": skill_key}, "c3")],
            [_call("search", {"query": "dogs"}, "c4")],
            [_call("search", {"query": "birds"}, "c5")],
            [],  # would answer "done"; the call limit (4) ends the run first
        ]
    )
    component = AgentComponent(_user_id="u")
    component.set(
        model=model,
        tools=[search, delete_file],
        system_prompt="You are a test agent.",
        max_iterations=4,
        handle_parsing_errors=retry,
    )
    if harness:
        hook = lambda event, **extra: _binding(HookBinding, on_event=event, **extra).model_dump()  # noqa: E731
        component.set(
            hook_bindings=json.dumps(
                [
                    hook("before_tool_call", mode="control", on_failure="stop"),
                    hook("before_llm_call", mode="control", on_failure="stop"),
                    hook("after_llm_call"),
                ]
            ),
            permission_binding=_binding(PermissionBinding).model_dump_json(),
            context_binding=_binding(ContextBinding).model_dump_json(),
            compaction_binding=_binding(CompactionBinding, trigger_tokens=300).model_dump_json(),
            skill_bindings=HarnessSkills(packs=(manifest,)).model_dump_json(),
        )
    component.set(**settings)
    component._vertex = SimpleNamespace(
        graph=SimpleNamespace(context={}, run_id=str(uuid4()), session_id=str(uuid4()), human_input_decisions={})
    )
    return component, model, [search, delete_file], effects


async def run_packaged(component, model):
    """The packaged path: the runnable and the config the Agent component itself builds."""
    sink = EventSink()
    agent = component.create_agent_runnable()
    model.bound.clear()  # create_agent_runnable validates tool binding once, eagerly
    config = {
        "configurable": {"thread_id": component._agent_thread_id()},
        "callbacks": [sink],
        "recursion_limit": component._compute_recursion_limit(),
    }
    state = await agent.ainvoke({"messages": _human()}, config)
    return state["messages"], state, sink


def make_runtime(component, model, sink=None):
    return HarnessLoopRuntime(
        model=model,
        tools=component.tools,
        system_prompt=component.system_prompt,
        middleware=component._build_middleware(model),
        callbacks=[sink] if sink else None,
    )


async def drive(runtime, messages):
    """The reference Agent Block loop: model, tools in parallel, stop on the runtime's signal, finish."""
    for _ in range(20):
        messages = await runtime.model_call(messages)
        if runtime.stopped or not getattr(messages[-1], "tool_calls", None):
            break
        messages = [*messages, *await runtime.tool_calls(messages[-1].tool_calls, messages)]
        if runtime.stopped:
            break
    await runtime.finish()
    return messages


async def run_runtime(component, model):
    sink = EventSink()
    runtime = make_runtime(component, model, sink)
    messages = await drive(runtime, _human())
    return messages, runtime.state, sink


def _ids(model, messages):
    """Label every message id by order of first appearance, so two runs with random ids compare."""
    labels: dict = {}
    for m in [*(m for seen in model.seen for m in seen), *messages]:
        labels.setdefault(m.id, f"m{len(labels)}")
    return labels


def _shape(messages, labels):
    return [
        (m.type, m.content, [(c["name"], c["args"], c["id"]) for c in getattr(m, "tool_calls", [])], labels[m.id])
        for m in messages
    ]


def _events(sink, labels):
    def relabel(event):
        event = deepcopy(event)
        if "retained_message_ids" in event:
            event["retained_message_ids"] = [labels.get(i, "unknown") for i in event["retained_message_ids"]]
        return event

    return [relabel(e) for e in sink.events]


def _stable(value):
    """Drop capture times, the one thing two runs of the same script do not share."""
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k != "captured_at"}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def _by_call(events):
    """Parallel tool calls emit their events in either order, so order them by call id."""
    return sorted(events, key=lambda e: json.dumps(e, sort_keys=True))


async def test_runtime_matches_packaged_agent(flows):
    component, model, _, effects = build()
    p_messages, p_state, p_sink = await run_packaged(component, model)
    p_flows, p_effects, p_seen, p_bound = list(flows.calls), list(effects), model.seen, model.bound
    p_labels = _ids(model, p_messages)

    flows.calls.clear()
    component, model, _, effects = build()
    r_messages, r_state, r_sink = await run_runtime(component, model)
    r_labels = _ids(model, r_messages)

    assert p_effects == [("search", "CATS"), ("search", "DOGS"), ("search", "BIRDS")]  # upper-cased, delete rejected
    assert effects == p_effects
    assert sorted(map(str, flows.calls)) == sorted(map(str, p_flows))
    assert {"before_llm_call", "after_llm_call", "before_tool_call"} <= {c[1] for c in flows.calls if c[0] == "hook"}
    assert len(model.seen) == len(p_seen) == 4
    assert [_shape(s, r_labels) for s in model.seen] == [_shape(s, p_labels) for s in p_seen]
    assert ["SKILL BODY" in str(s[0].content) for s in model.seen] == [False, False, True, True]
    assert model.bound == p_bound
    assert _shape(r_messages, r_labels) == _shape(p_messages, p_labels)
    assert r_messages[-1].content == "Model call limits exceeded: run limit (4/4)"
    assert r_state[ACTIVE_SKILL_KEY] == p_state[ACTIVE_SKILL_KEY]
    assert r_state[ACTIVE_SKILL_KEY]["key"] == f"{PROJECT_ID}:verify-sources"
    assert _stable(r_state[EVIDENCE_STATE_KEY]) == _stable(p_state[EVIDENCE_STATE_KEY])
    assert [s["uri"] for s in r_state[EVIDENCE_STATE_KEY]["sources"]] == [
        f"https://example.org/{q}" for q in ("CATS", "DOGS", "BIRDS")
    ]
    r_events, p_events = _events(r_sink, r_labels), _events(p_sink, p_labels)
    assert _by_call(_stable(r_events)) == _by_call(_stable(p_events))
    assert {"compacted", "skill_activated", "context_prepared"} <= {e["kind"] for e in r_events}
    assert any(e.get("retained_message_ids") for e in r_events)


@pytest.mark.parametrize("retry", [True, False])
async def test_invalid_tool_args_match_packaged_agent(flows, retry):  # noqa: ARG001
    bad = _call("search", {"wrong": 1}, "bad")

    component, model, _, _ = build([[bad]], retry=retry)
    agent = component.create_agent_runnable()
    packaged = None
    async for update in agent.astream(
        {"messages": _human()},
        {"configurable": {"thread_id": component._agent_thread_id()}},
        stream_mode="updates",
    ):
        for value in update.values():
            for m in (value or {}).get("messages", []) if isinstance(value, dict) else []:
                if isinstance(m, ToolMessage) and m.tool_call_id == "bad":
                    packaged = m
        if packaged:
            break

    component, model, _, _ = build([[bad]], retry=retry)
    runtime = make_runtime(component, model)
    messages = await runtime.model_call(_human())
    (ours,) = await runtime.tool_calls([bad], messages)

    assert packaged is not None
    assert (ours.status, ours.content) == (packaged.status, packaged.content)
    assert ours.status == "error"


async def test_ask_decision_raises_and_tool_does_not_run(tmp_path):
    binding, _, _ = source(tmp_path, action="ask")
    component, model, _, effects = build(harness=False, permission_binding=binding.model_dump_json())
    component._user_id = "test-user"
    component._vertex.graph.context = {"project_dir": str(tmp_path)}
    runtime = make_runtime(component, model)
    messages = await runtime.model_call(_human())
    with pytest.raises(NestedHITLUnsupportedError):
        await runtime.tool_calls(messages[-1].tool_calls, messages)
    assert effects == []


# Differential tests: small recording middleware through create_agent and through the runtime.


class Recorder(AgentMiddleware):
    """Logs every hook it runs. `tag` tells two instances apart."""

    log: list
    tag: str

    async def abefore_model(self, state, runtime):  # noqa: ARG002
        self.log.append((self.tag, "before_model", [bool(m.id) for m in state["messages"]]))

    async def aafter_model(self, state, runtime):  # noqa: ARG002
        self.log.append((self.tag, "after_model"))

    async def aafter_agent(self, state, runtime):  # noqa: ARG002
        self.log.append((self.tag, "after_agent", [bool(m.id) for m in state["messages"]]))

    async def awrap_model_call(self, request, handler):
        self.log.append((self.tag, "wrap_model:in"))
        response = await handler(request)
        self.log.append((self.tag, "wrap_model:out"))
        return response

    async def awrap_tool_call(self, request, handler):
        self.log.append(
            (self.tag, "wrap_tool:in", request.tool_call["name"], [bool(m.id) for m in request.state["messages"]])
        )
        result = await handler(request)
        self.log.append((self.tag, "wrap_tool:out"))
        return result


def named(base, tag, log, **members):
    """An instance of a fresh subclass, because create_agent rejects two middleware of one class name."""
    cls = type(f"{base.__name__}{tag}", (base,), members)
    middleware = cls()
    middleware.log, middleware.tag = log, tag
    return middleware


@tool
def echo(text: str) -> str:
    """Echo."""
    return text


@tool(return_direct=True)
def answer(text: str) -> str:
    """Answer and end the run."""
    return text


def one_echo():
    return [[_call("echo", {"text": "x"}, "e1")]]


async def both_paths(make_middleware, *, tools=(echo,), script=None, model_kwargs=None):
    """Run the same middleware through create_agent, then the runtime. Returns (model, log, messages) for each."""
    outcomes = []
    for packaged in (True, False):
        log: list = []
        model = ScriptedModel(script=script if script is not None else one_echo(), **(model_kwargs or {}))
        middleware = make_middleware(log)
        if packaged:
            agent = create_agent(model=model, tools=list(tools), system_prompt="s", middleware=middleware)
            messages = (await agent.ainvoke({"messages": [HumanMessage("hi")]}))["messages"]
        else:
            runtime = HarnessLoopRuntime(model=model, tools=list(tools), system_prompt="s", middleware=middleware)
            messages = await drive(runtime, [HumanMessage("hi")])
        outcomes.append((model, log, messages))
    return outcomes


async def test_hook_and_wrapper_order_match_create_agent():
    (_, p_log, p_messages), (_, r_log, r_messages) = await both_paths(
        lambda log: [named(Recorder, "A", log), named(Recorder, "B", log)]
    )
    assert r_log == p_log
    assert [m.content for m in r_messages] == [m.content for m in p_messages]
    # after_model and after_agent run in reverse registration order, wrappers nest first-outermost
    after_model = [e[0] for e in r_log if e[1] == "after_model"]
    assert after_model[:2] == ["B", "A"]
    assert [e[0] for e in r_log if e[1] == "after_agent"] == ["B", "A"]
    assert [e[0] for e in r_log if e[1] == "wrap_model:in"][:2] == ["A", "B"]
    assert [e[0] for e in r_log if e[1] == "wrap_tool:in"] == ["A", "B"]


async def test_message_ids_are_assigned_like_create_agent():
    (_, p_log, _), (_, r_log, _) = await both_paths(lambda log: [named(Recorder, "A", log)])
    with_ids = [e for e in r_log if e[1] in ("before_model", "after_agent")]
    assert with_ids == [e for e in p_log if e[1] in ("before_model", "after_agent")]
    assert all(all(e[2]) for e in with_ids)


async def test_tool_and_finish_see_message_ids_when_the_caller_passes_none():
    log: list = []
    runtime = HarnessLoopRuntime(
        model=ScriptedModel(), tools=[echo], system_prompt="s", middleware=[named(Recorder, "A", log)]
    )
    call = _call("echo", {"text": "x"}, "e1")
    await runtime.tool_calls([call], [HumanMessage("hi"), AIMessage("", tool_calls=[call])])
    await runtime.finish()
    assert log[0] == ("A", "wrap_tool:in", "echo", [True, True])
    assert log[-1] == ("A", "after_agent", [True, True, True])


class Jumper(Recorder):
    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):
        await super().abefore_model(state, runtime)
        return {"jump_to": "end", "messages": [AIMessage("blocked")]}

    @hook_config(can_jump_to=["end"])
    async def aafter_model(self, state, runtime):
        await super().aafter_model(state, runtime)
        return {"jump_to": "end"}


@pytest.mark.parametrize("phase", ["before_model", "after_model"])
async def test_jump_to_end_stops_the_phase_like_create_agent(phase):
    def middleware(log):
        # before hooks run in registration order, after hooks in reverse
        pair = [named(Jumper, "J", log), named(Recorder, "R", log)]
        return pair if phase == "before_model" else pair[::-1]

    (p_model, p_log, p_messages), (r_model, r_log, r_messages) = await both_paths(middleware)
    assert r_log == p_log
    assert len(r_model.seen) == len(p_model.seen)
    assert not any(e[0] == "R" and e[1] == phase for e in r_log)
    assert [m.content for m in r_messages] == [m.content for m in p_messages]


class EndBeforeModel(AgentMiddleware):
    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):  # noqa: ARG002
        return {"jump_to": "end"}


class EndAfterModel(AgentMiddleware):
    @hook_config(can_jump_to=["end"])
    async def aafter_model(self, state, runtime):  # noqa: ARG002
        return {"jump_to": "end"}


@pytest.mark.parametrize("middleware", [EndBeforeModel, EndAfterModel])
async def test_stopped_run_refuses_tools(middleware):
    ran = []

    @tool
    def wipe(path: str) -> str:
        """Delete things."""
        ran.append(path)
        return "wiped"

    call = _call("wipe", {"path": "/"}, "w1")
    model = ScriptedModel(script=[[call]])
    runtime = HarnessLoopRuntime(model=model, tools=[wipe], system_prompt="s", middleware=[middleware()])
    messages = await runtime.model_call([HumanMessage("hi")])
    assert runtime.stopped
    with pytest.raises(RuntimeError, match="stopped"):
        await runtime.tool_calls([call], [*messages, AIMessage("", tool_calls=[call])])
    assert ran == []


class Redirect(AgentMiddleware):
    @hook_config(can_jump_to=["model"])
    async def aafter_model(self, state, runtime):  # noqa: ARG002
        return {"jump_to": "model"}


async def test_jump_to_other_than_end_raises():
    runtime = HarnessLoopRuntime(model=ScriptedModel(), tools=[], system_prompt="s", middleware=[Redirect()])
    with pytest.raises(NotImplementedError, match="model"):
        await runtime.model_call([HumanMessage("hi")])


class SyncGuard(AgentMiddleware):
    """A guard written sync-only. create_agent runs it from its async path."""

    log: list

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):  # noqa: ARG002
        self.log.append("before_model")
        return {"jump_to": "end", "messages": [AIMessage("blocked by guard")]}

    def after_model(self, state, runtime):  # noqa: ARG002
        self.log.append("after_model")

    def after_agent(self, state, runtime):  # noqa: ARG002
        self.log.append("after_agent")


async def test_sync_only_hooks_run_like_create_agent():
    def middleware(log):
        guard = SyncGuard()
        guard.log = log
        return [guard]

    (p_model, p_log, p_messages), (r_model, r_log, r_messages) = await both_paths(middleware)
    assert r_log == p_log == ["before_model", "after_agent"]
    assert len(r_model.seen) == len(p_model.seen) == 0
    assert r_messages[-1].content == p_messages[-1].content == "blocked by guard"


class SyncOnlyAfter(AgentMiddleware):
    log: list

    def after_model(self, state, runtime):  # noqa: ARG002
        self.log.append("after_model")


async def test_sync_after_model_runs_like_create_agent():
    def middleware(log):
        hook = SyncOnlyAfter()
        hook.log = log
        return [hook]

    (_, p_log, _), (_, r_log, _) = await both_paths(middleware)
    assert r_log == p_log
    assert r_log


class BeforeAgentOnly(AgentMiddleware):
    def before_agent(self, state, runtime):  # noqa: ARG002
        return None


class ABeforeAgentOnly(AgentMiddleware):
    async def abefore_agent(self, state, runtime):  # noqa: ARG002
        return None


@pytest.mark.parametrize("middleware", [BeforeAgentOnly, ABeforeAgentOnly])
def test_unsupported_overrides_raise_at_construction(middleware):
    with pytest.raises(NotImplementedError, match="before_agent"):
        HarnessLoopRuntime(model=ScriptedModel(), tools=[], system_prompt="s", middleware=[middleware()])


class Overrides(AgentMiddleware):
    """Narrows the tools and sets model settings, as a wrap_model_call middleware may."""

    async def awrap_model_call(self, request, handler):
        return await handler(
            request.override(tools=[t for t in request.tools if t.name == "echo"], model_settings={"temperature": 0.2})
        )


async def test_wrap_model_overrides_reach_the_model_like_create_agent():
    (p_model, _, _), (r_model, _, _) = await both_paths(lambda _log: [Overrides()], tools=(answer, echo))
    assert r_model.bound == p_model.bound
    assert r_model.bound[0] == (["echo"], {"tool_choice": None, "temperature": 0.2})


class SettingsOnly(AgentMiddleware):
    async def awrap_model_call(self, request, handler):
        return await handler(request.override(model_settings={"temperature": 0.2}))


async def test_model_settings_reach_a_model_without_tools_like_create_agent():
    (p_model, _, _), (r_model, _, _) = await both_paths(lambda _log: [SettingsOnly()], tools=(), script=[[]])
    assert r_model.bound == p_model.bound == [([], {"temperature": 0.2})]


class ToolsFromMiddleware(AgentMiddleware):
    tools = (answer,)


async def test_middleware_tools_come_first_like_create_agent():
    (p_model, _, _), (r_model, _, _) = await both_paths(lambda _log: [ToolsFromMiddleware()], tools=(echo,))
    assert r_model.bound == p_model.bound
    assert r_model.bound[0][0] == ["answer", "echo"]


class Structured(AgentMiddleware):
    class Answer(BaseModel):
        text: str

    async def awrap_model_call(self, request, handler):
        return await handler(request.override(response_format=ToolStrategy(schema=self.Answer)))


async def test_response_format_raises():
    runtime = HarnessLoopRuntime(model=ScriptedModel(), tools=[], system_prompt="s", middleware=[Structured()])
    with pytest.raises(NotImplementedError, match="response_format"):
        await runtime.model_call([HumanMessage("hi")])


class Tagger(AgentMiddleware):
    """Inner layer: every pass through it emits a command that appends a message."""

    async def awrap_model_call(self, request, handler):
        response = await handler(request)
        return ExtendedModelResponse(
            model_response=response, command=Command(update={"messages": [HumanMessage("tagged")]})
        )


class Retrier(AgentMiddleware):
    """Outer layer: calls the inner handler twice."""

    async def awrap_model_call(self, request, handler):
        await handler(request)
        return await handler(request)


async def test_retried_handler_replaces_its_commands_like_create_agent():
    (_, _, p_messages), (_, _, r_messages) = await both_paths(lambda _log: [Retrier(), Tagger()], script=[[]])
    assert [m.content for m in r_messages] == [m.content for m in p_messages]
    assert [m.content for m in r_messages].count("tagged") == 1


@pytest.mark.parametrize("command", [Command(goto="x"), Command(resume="x"), Command(graph=Command.PARENT)])
async def test_unsupported_model_commands_raise(command):
    class Bad(AgentMiddleware):
        async def awrap_model_call(self, request, handler):
            return ExtendedModelResponse(model_response=await handler(request), command=command)

    runtime = HarnessLoopRuntime(model=ScriptedModel(), tools=[], system_prompt="s", middleware=[Bad()])
    with pytest.raises(NotImplementedError):
        await runtime.model_call([HumanMessage("hi")])


@pytest.mark.parametrize("also_echo", [False, True])
async def test_return_direct_ends_the_run_like_create_agent(also_echo):
    calls = [_call("answer", {"text": "final"}, "a1")]
    if also_echo:
        calls.append(_call("echo", {"text": "x"}, "e1"))
    (p_model, _, p_messages), (r_model, _, r_messages) = await both_paths(
        lambda _log: [], tools=(answer, echo), script=[calls]
    )
    assert len(r_model.seen) == len(p_model.seen) == (2 if also_echo else 1)
    assert [m.content for m in r_messages] == [m.content for m in p_messages]


async def test_return_direct_sets_stopped_and_refuses_more_tools():
    model = ScriptedModel(script=[[_call("answer", {"text": "final"}, "a1")]])
    runtime = HarnessLoopRuntime(model=model, tools=[answer], system_prompt="s", middleware=[])
    messages = await runtime.model_call([HumanMessage("hi")])
    assert not runtime.stopped
    (result,) = await runtime.tool_calls(messages[-1].tool_calls, messages)
    assert result.content == "final"
    assert runtime.stopped
    with pytest.raises(RuntimeError, match="stopped"):
        await runtime.tool_calls(messages[-1].tool_calls, messages)


async def test_model_calls_are_serialized_by_the_lock():
    model = ScriptedModel(delay=0.05)
    runtime = HarnessLoopRuntime(
        model=model, tools=[], system_prompt="s", middleware=[ModelCallLimitMiddleware(run_limit=1)]
    )
    await asyncio.gather(*(runtime.model_call([HumanMessage("hi")]) for _ in range(3)))
    assert len(model.seen) == 1
    assert runtime.state["run_model_call_count"] == 1


async def test_finish_waits_for_a_running_model_call():
    log: list = []
    runtime = HarnessLoopRuntime(
        model=ScriptedModel(delay=0.1), tools=[], system_prompt="s", middleware=[named(Recorder, "A", log)]
    )
    model_call = asyncio.create_task(runtime.model_call([HumanMessage("hi")]))
    await asyncio.sleep(0.02)
    await runtime.finish()
    await model_call
    assert [e[1] for e in log if e[1] in ("after_model", "after_agent")] == ["after_model", "after_agent"]


class SetsFlag(AgentMiddleware):
    """A tool wrapper that answers with a state update, as skill activation does. The model side writes too."""

    async def aafter_model(self, state, runtime):  # noqa: ARG002
        return {"flag": "model", "model_only": "seen"}

    async def awrap_tool_call(self, request, handler):  # noqa: ARG002
        call = request.tool_call
        return Command(
            update={
                "flag": call["args"]["value"],
                "messages": [ToolMessage("set", tool_call_id=call["id"], name=call["name"])],
            }
        )


@tool
def set_flag(value: str) -> str:
    """Set the flag."""
    return value


async def test_tool_state_update_commits_after_an_overlapping_model_call():
    runtime = HarnessLoopRuntime(
        model=ScriptedModel(delay=0.1), tools=[set_flag], system_prompt="s", middleware=[SetsFlag()]
    )

    async def set_to(value):
        call = _call("set_flag", {"value": value}, f"s-{value}")
        return await runtime.tool_calls([call], [HumanMessage("hi"), AIMessage("", tool_calls=[call])])

    await set_to("on")
    assert runtime.state["flag"] == "on"
    model_call = asyncio.create_task(runtime.model_call([HumanMessage("other branch")]))
    await asyncio.sleep(0.02)
    await set_to("off")  # its commit waits for the model call, then lands after it
    await model_call
    assert runtime.state["flag"] == "off"
    assert runtime.state["model_only"] == "seen"


@tool
def multi(tool_call_id: Annotated[str, InjectedToolCallId]) -> Command:
    """Answer with a Command that carries two messages."""
    return Command(
        update={
            "flag": "set",
            "messages": [ToolMessage("tool result", tool_call_id=tool_call_id), AIMessage("note by the tool")],
        }
    )


async def test_command_with_several_messages_returns_the_tools_own_message():
    runtime = HarnessLoopRuntime(model=ScriptedModel(), tools=[multi], system_prompt="s", middleware=[])
    call = _call("multi", {}, "m1")
    (result,) = await runtime.tool_calls([call], [HumanMessage("hi"), AIMessage("", tool_calls=[call])])
    assert isinstance(result, ToolMessage)
    assert result.content == "tool result"
    assert runtime.state["flag"] == "set"


class SeesAtFinish(AgentMiddleware):
    """Records the history the end-of-run hooks get."""

    def __init__(self):
        super().__init__()
        self.seen = []

    async def aafter_agent(self, state, runtime):  # noqa: ARG002
        self.seen.append([m.content for m in state["messages"]])


@tool
async def slow(text: str) -> str:
    """Answer after the other tool."""
    await asyncio.sleep(0.05)
    return f"slow {text}"


@tool
async def fast(text: str) -> str:
    """Answer at once."""
    return f"fast {text}"


async def test_parallel_results_come_back_and_reach_finish_in_call_order():
    watcher = SeesAtFinish()
    calls = [_call("slow", {"text": "a"}, "s1"), _call("fast", {"text": "b"}, "f1")]
    runtime = HarnessLoopRuntime(
        model=ScriptedModel(script=[calls]), tools=[slow, fast], system_prompt="s", middleware=[watcher]
    )
    messages = await runtime.model_call([HumanMessage("hi")])

    results = await runtime.tool_calls(messages[-1].tool_calls, messages)
    await runtime.finish()

    assert [m.content for m in results] == ["slow a", "fast b"]
    assert watcher.seen == [["hi", "", "slow a", "fast b"]]


async def test_finish_sees_the_last_model_calls_history_after_a_return_direct_turn():
    watcher = SeesAtFinish()
    model = ScriptedModel(script=[[_call("answer", {"text": "final"}, "a1")]])
    runtime = HarnessLoopRuntime(model=model, tools=[answer], system_prompt="s", middleware=[watcher])
    messages = await runtime.model_call([HumanMessage("hi")])
    await runtime.tool_calls(messages[-1].tool_calls, messages)

    await runtime.finish()

    assert runtime.stopped
    assert watcher.seen == [["hi", "", "final"]]


async def test_a_call_that_needs_approval_is_refused_before_any_call_of_its_batch_runs():
    from lfx.components.models_and_agents.agent_helpers.permission_middleware import ToolApprovalMiddleware

    ran = []

    @tool
    def wipe(path: str) -> str:
        """Delete things."""
        ran.append(path)
        return "wiped"

    @tool
    def note(text: str) -> str:
        """Write a note."""
        ran.append(text)
        return "noted"

    gate = ToolApprovalMiddleware({"wipe": {"allowed_decisions": ["approve", "reject"]}}, policy="ask")
    runtime = HarnessLoopRuntime(model=ScriptedModel(), tools=[note, wipe], system_prompt="s", middleware=[gate])
    calls = [_call("note", {"text": "first"}, "n1"), _call("wipe", {"path": "/"}, "w1")]

    with pytest.raises(ValueError, match="'wipe' requires approval"):
        await runtime.tool_calls(calls, [HumanMessage("hi"), AIMessage("", tool_calls=calls)])

    assert ran == []


async def test_a_tool_with_approval_actions_is_refused_without_a_gate():
    @tool
    def send(to: str) -> str:
        """Send mail."""
        return f"sent to {to}"

    send.metadata = {"approval_actions": ["approve", "reject"]}
    runtime = HarnessLoopRuntime(model=None, tools=[send], system_prompt=None, middleware=[])
    call = _call("send", {"to": "ceo"}, "m1")

    with pytest.raises(ValueError, match="'send' requires approval"):
        await runtime.tool_calls([call], [HumanMessage("hi"), AIMessage("", tool_calls=[call])])


async def test_a_failing_tool_returns_its_error_to_the_model_like_create_agent():
    from langchain.agents.middleware import ToolRetryMiddleware

    @tool
    def boom(text: str) -> str:
        """Fail."""
        msg = f"tool exploded on {text}"
        raise RuntimeError(msg)

    (_, _, p_messages), (_, _, r_messages) = await both_paths(
        lambda _log: [ToolRetryMiddleware(max_retries=0)], tools=(boom,), script=[[_call("boom", {"text": "x"}, "b1")]]
    )

    p_tool, r_tool = (next(m for m in messages if isinstance(m, ToolMessage)) for messages in (p_messages, r_messages))
    assert (r_tool.status, r_tool.content) == (p_tool.status, p_tool.content)
    assert "tool exploded" in r_tool.content
    assert r_messages[-1].content == "done"  # the model got the error back and answered


async def test_a_runtime_without_a_model_says_so_when_asked_for_a_model_call():
    runtime = HarnessLoopRuntime(model=None, tools=[echo], system_prompt=None, middleware=[])

    with pytest.raises(ValueError, match="without a model"):
        await runtime.model_call([HumanMessage("hi")])


@pytest.mark.parametrize(("prompt", "first"), [(None, "HumanMessage"), ("", "SystemMessage"), ("s", "SystemMessage")])
async def test_the_system_message_follows_create_agent(prompt, first):
    packaged, ours = ScriptedModel(), ScriptedModel()
    await create_agent(model=packaged, tools=[], system_prompt=prompt).ainvoke({"messages": [HumanMessage("hi")]})
    await HarnessLoopRuntime(model=ours, tools=[], system_prompt=prompt, middleware=[]).model_call([HumanMessage("hi")])

    assert [type(m).__name__ for m in ours.seen[0]] == [type(m).__name__ for m in packaged.seen[0]]
    assert type(ours.seen[0][0]).__name__ == first


SCOPE = __import__("contextvars").ContextVar("test_runtime_scope", default="unset")


async def test_tools_and_hooks_run_in_the_context_the_runtime_was_built_in():
    """The Agent builds the runtime and a loop flow calls it. Its tools see the Agent's scopes, not the caller's."""
    seen = []

    @tool
    def where(text: str) -> str:
        """Report the scope."""
        seen.append(("tool", SCOPE.get()))
        return text

    class Where(AgentMiddleware):
        async def abefore_model(self, state, runtime):  # noqa: ARG002
            seen.append(("before_model", SCOPE.get()))

    token = SCOPE.set("builder")
    runtime = HarnessLoopRuntime(
        model=ScriptedModel(script=[[_call("where", {"text": "x"}, "w1")]]),
        tools=[where],
        system_prompt="s",
        middleware=[Where()],
    )
    SCOPE.reset(token)

    async def caller():
        SCOPE.set("caller")
        messages = await runtime.model_call([HumanMessage("hi")])
        await runtime.tool_calls(messages[-1].tool_calls, messages)

    await asyncio.create_task(caller())

    assert seen == [("before_model", "builder"), ("tool", "builder")]
