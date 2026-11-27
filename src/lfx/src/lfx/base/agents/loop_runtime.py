"""Run the harness middleware around a model/tool loop that is not `create_agent`.

Agent Blocks call the model and tools themselves, so they would skip every control the
packaged Agent applies as LangChain middleware. `HarnessLoopRuntime` takes the list that
`AgentComponent._build_middleware` returns and applies the same hooks, in the same order:

- `model_call`: before_model, wrap_model_call chain, the model, after_model
- `tool_calls`: one AI message's calls, in parallel, through LangGraph's public `ToolNode` with the
  wrap_tool_call chain
- `finish`: after_agent

It matches `create_agent` or raises. Overrides it cannot run (`before_agent`), a `jump_to`
other than "end", a wrap_model_call Command with goto/resume/graph, and a requested
`response_format` raise `NotImplementedError`.

The message history belongs to the caller. The runtime records the history it saw last, so
`finish()` runs the end-of-run hooks on it: what the last `model_call` returned, or the last tool
batch's history and its results in call order. The runtime also keeps the harness bookkeeping
(call counts, active skill, source evidence) in one private state dict, readable through `state`.
Every writer (model_call, tool Commands, finish) collects the keys it changed and commits only
those, under the lock, so a write never replaces a key it did not touch.

Each call runs inside a no-checkpointer LangGraph `entrypoint`: Permission flows use `@task`
and harness events use `adispatch_custom_event`, and both need a parent run. Each call of a tool
batch is a `task`. Every call also runs in the context the runtime was built in, so its tools and
middleware see the builder's flow, message and file scopes, wherever the caller runs.

Concurrency: `model_call` and `finish` are serialized by a lock, because they read and replace
the state. The calls of a batch run in parallel, as in the packaged loop, and a batch may overlap a
`model_call`: each call reads the state as it was when the batch started, and the batch's state
updates are committed under the lock. Two calls that update the same key keep the later one in the
batch. `stopped` is the single end-of-run signal, and `tool_calls` raises once it is set.
"""

import asyncio
import contextvars
import inspect
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from langchain.agents.middleware import (
    AgentMiddleware,
    ExtendedModelResponse,
    HumanInTheLoopMiddleware,
    ModelRequest,
    ModelResponse,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolCall, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.func import entrypoint, task
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langgraph.prebuilt.tool_node import ToolCallRequest, ToolCallWithContext
from langgraph.runtime import Runtime
from langgraph.types import Command

from lfx.run.hitl import NESTED_HITL_UNSUPPORTED, NestedHITLUnsupportedError

_INTERRUPT = "__interrupt__"

Hook = Callable[[dict, Runtime], Any]


def _overrides(middleware: AgentMiddleware, *names: str) -> bool:
    return any(getattr(type(middleware), name) is not getattr(AgentMiddleware, name) for name in names)


def _hooks(middleware: list[AgentMiddleware], sync_name: str, async_name: str) -> list[Hook]:
    """The hook create_agent runs for each middleware: the async override if any, else the sync one."""
    return [
        getattr(m, async_name) if _overrides(m, async_name) else getattr(m, sync_name)
        for m in middleware
        if _overrides(m, sync_name, async_name)
    ]


def _no_interrupt(result: Any) -> None:
    # Without a checkpointer an entrypoint returns the interrupt instead of raising it.
    if isinstance(result, dict) and _INTERRUPT in result:
        raise NestedHITLUnsupportedError(NESTED_HITL_UNSUPPORTED)


def _apply(state: dict, changes: dict, update: dict | None) -> str | None:
    """Merge a middleware update into `state`, record the keys it set in `changes`, return its `jump_to`."""
    for key, value in (update or {}).items():
        if key == "messages":
            state["messages"] = add_messages(state["messages"], value)
        elif key != "jump_to":
            state[key] = changes[key] = value
    return (update or {}).get("jump_to")


def _tool_packet(call: ToolCall, state: dict) -> ToolCallWithContext:
    # The legacy Send payload ToolNode still accepts. create_agent dispatches it through graph
    # channels; the runtime has none, so it hands the same packet to ToolNode directly.
    return ToolCallWithContext(__type="tool_call_with_context", tool_call=call, state=state)


class HarnessLoopRuntime:
    def __init__(
        self,
        *,
        model: BaseChatModel | None,
        tools: list[BaseTool],
        system_prompt: str | None,
        middleware: list[AgentMiddleware],
        callbacks: list | None = None,
    ) -> None:
        """`model` is None for a runtime that only runs tools. A `system_prompt` of None sends no system message."""
        for m in middleware:
            if _overrides(m, "before_agent", "abefore_agent"):
                msg = f"{m.name} overrides before_agent, which HarnessLoopRuntime does not run."
                raise NotImplementedError(msg)
        self._model = model
        self._system_prompt = system_prompt
        self._config = {"callbacks": callbacks or []}
        self._before = _hooks(middleware, "before_model", "abefore_model")
        # create_agent runs "after" hooks in reverse order.
        self._after = _hooks(middleware, "after_model", "aafter_model")[::-1]
        self._after_agent = _hooks(middleware, "after_agent", "aafter_agent")[::-1]
        self._wrap_model = [m for m in middleware if _overrides(m, "wrap_model_call", "awrap_model_call")]
        self._wrap_tool = [m for m in middleware if _overrides(m, "wrap_tool_call", "awrap_tool_call")]
        # The registry and its order belong to ToolNode: middleware tools first, as in create_agent.
        middleware_tools = [t for m in middleware for t in getattr(m, "tools", [])]
        self._tool_node = ToolNode([*middleware_tools, *tools], awrap_tool_call=self._tool_chain)
        self._state: dict[str, Any] = {}
        self._stopped = False
        self._history: list[BaseMessage] = []
        self._lock = asyncio.Lock()
        self._context = contextvars.copy_context()
        self._model_entry = entrypoint()(self._run_model_call)
        self._tool_batch = entrypoint()(self._run_tool_batch)
        self._tool_task = task(name="harness_tool_call")(self._run_tool_call)
        self._finish_entry = entrypoint()(self._run_finish)

    @property
    def stopped(self) -> bool:
        """True once the run is over: a middleware ended it (`jump_to` end) or the last turn was all `return_direct`."""
        return self._stopped

    @property
    def state(self) -> dict[str, Any]:
        """A copy of the harness bookkeeping (call counts, active skill, source evidence)."""
        return dict(self._state)

    async def model_call(self, messages: list[BaseMessage]) -> list[BaseMessage]:
        """Return the rewritten history. The new AIMessage is last, unless the run was stopped."""
        async with self._lock:
            result = await self._in_context(self._model_entry.ainvoke(list(messages), self._config))
            _no_interrupt(result)
            self._history = list(result)
        return result

    async def tool_calls(self, calls: list[ToolCall], messages: list[BaseMessage]) -> list[ToolMessage]:
        """Run one AI message's `calls` in parallel and return their results in call order.

        `messages` is the history ending in that AI message. A call that needs an approval decision is refused
        before any call runs, because nothing here can pause for the decision.
        """
        if self._stopped:
            msg = "The run has stopped. A stopped run does not run tools."
            raise RuntimeError(msg)
        for call in calls:
            if self._needs_decision(call["name"]):
                msg = (
                    f"Tool {call['name']!r} requires approval, and a loop flow cannot ask for it yet. "
                    "Run it through the Agent's packaged loop, or remove its approval setting."
                )
                raise ValueError(msg)
        # Message ids as create_agent has them, so middleware evidence (retained_message_ids) agrees.
        payload = {"calls": list(calls), "messages": add_messages([], list(messages)), "state": dict(self._state)}
        result = await self._in_context(self._tool_batch.ainvoke(payload, self._config))
        _no_interrupt(result)
        tool_messages = [message for message, _ in result["results"]]
        async with self._lock:
            for _, changes in result["results"]:
                self._state.update(changes)
            self._history = [*result["messages"], *tool_messages]
        self._note_return_direct(result["messages"])
        return tool_messages

    async def finish(self) -> None:
        """Run the end-of-run hooks on the history the runtime saw last, folding the final tool results into the state.

        That history is what the last `model_call` returned, or the last tool batch's history and its results.
        """
        async with self._lock:
            result = await self._in_context(self._finish_entry.ainvoke(list(self._history), self._config))
        _no_interrupt(result)

    def _in_context(self, call: Coroutine) -> asyncio.Task:
        # A task copies the context it is created in. Creating it inside the builder's context, rather than with
        # create_task's `context` argument, which Python 3.10 lacks, runs the call under the builder's scopes.
        return self._context.run(asyncio.create_task, call)

    def _needs_decision(self, name: str) -> bool:
        """Whether every call to tool `name` asks for an approval decision.

        The tool's own `approval_actions` always ask. So does a tool-approval middleware (HumanInTheLoopMiddleware)
        whose `interrupt_on` names the tool, such as the "ask" policy. A Permission flow (policy "flow") names every
        tool but asks only when the flow decides to, which is known only at the call.
        """
        tool = self._tool_node.tools_by_name.get(name)
        if tool is not None and (tool.metadata or {}).get("approval_actions"):
            return True
        return any(
            isinstance(m, HumanInTheLoopMiddleware) and name in m.interrupt_on and getattr(m, "policy", None) != "flow"
            for m in self._wrap_tool
        )

    async def _run_hooks(self, hooks: list[Hook], state: dict, changes: dict, runtime: Runtime) -> bool:
        """Run one phase like create_agent: `jump_to` end stops the phase, other targets are unsupported."""
        for hook in hooks:
            if inspect.iscoroutinefunction(hook):
                update = await hook(state, runtime)
            else:  # create_agent runs a sync-only hook in an executor
                update = await asyncio.to_thread(hook, state, runtime)
            jump = _apply(state, changes, update)
            if jump == "end":
                return True
            if jump:
                msg = f"jump_to {jump!r} is not supported by HarnessLoopRuntime. Only 'end' is."
                raise NotImplementedError(msg)
        return False

    async def _run_model_call(self, messages: list[BaseMessage], *, runtime: Runtime) -> list[BaseMessage]:
        # Message ids as create_agent has them, so middleware evidence (retained_message_ids) agrees.
        state, changes = {**self._state, "messages": add_messages([], messages)}, {}
        if await self._run_hooks(self._before, state, changes, runtime):
            self._stopped = True
        else:
            request = ModelRequest(
                model=self._model,
                tools=list(self._tool_node.tools_by_name.values()),
                # create_agent sends a system message for any prompt that is not None, an empty one included.
                system_message=SystemMessage(self._system_prompt) if self._system_prompt is not None else None,
                messages=state["messages"],
                tool_choice=None,
                state=state,
                runtime=runtime,
            )
            response, commands = await self._chain_model(request)
            for command in commands:
                self._check_command(command)
            _apply(state, changes, {"messages": response.result})
            for command in commands:
                _apply(state, changes, command.update)
            if await self._run_hooks(self._after, state, changes, runtime):
                self._stopped = True
        self._state.update(changes)
        return state["messages"]

    @staticmethod
    def _check_command(command: Command) -> None:
        for field, label in ((command.goto, "goto"), (command.resume, "resume"), (command.graph, "graph")):
            if field:
                msg = f"Command {label} is not supported in wrap_model_call middleware."
                raise NotImplementedError(msg)

    async def _chain_model(self, request: ModelRequest) -> tuple[ModelResponse, list[Command]]:
        """Run the wrap_model_call chain. Commands come inner-first, from the last handler call of each layer."""

        async def run(i: int, req: ModelRequest) -> tuple[ModelResponse, list[Command]]:
            if i == len(self._wrap_model):
                return await self._execute_model(req), []
            inner: list[Command] = []

            async def handler(r: ModelRequest) -> ModelResponse:
                nonlocal inner
                response, inner = await run(i + 1, r)  # a retried handler call replaces the earlier commands
                return response

            out = await self._wrap_model[i].awrap_model_call(req, handler)
            own = list(inner)
            if isinstance(out, ExtendedModelResponse):
                if out.command:
                    own.append(out.command)
                out = out.model_response
            return (ModelResponse(result=[out]) if isinstance(out, AIMessage) else out), own

        return await run(0, request)

    async def _execute_model(self, request: ModelRequest) -> ModelResponse:
        if request.response_format is not None:
            msg = "HarnessLoopRuntime does not support response_format."
            raise NotImplementedError(msg)
        if request.model is None:
            msg = "This HarnessLoopRuntime was built without a model, so it cannot make a model call."
            raise ValueError(msg)
        settings = request.model_settings
        model = (
            request.model.bind_tools(request.tools, tool_choice=request.tool_choice, **settings)
            if request.tools
            else request.model.bind(**settings)
        )
        prefix = [request.system_message] if request.system_message else []
        return ModelResponse(result=[await model.ainvoke([*prefix, *request.messages])])

    async def _tool_chain(
        self,
        request: ToolCallRequest,
        execute: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        async def run(i: int, req: ToolCallRequest) -> ToolMessage | Command:
            if i == len(self._wrap_tool):
                return await execute(req)
            return await self._wrap_tool[i].awrap_tool_call(req, lambda r: run(i + 1, r))

        return await run(0, request)

    async def _run_tool_batch(self, payload: dict) -> dict:
        futures = [self._tool_task(call, payload["messages"], payload["state"]) for call in payload["calls"]]
        return {**payload, "results": [await future for future in futures]}

    async def _run_tool_call(
        self, call: ToolCall, messages: list[BaseMessage], batch_state: dict
    ) -> tuple[ToolMessage, dict]:
        """One call of a batch: its ToolMessage and the state keys it changed, which the batch commits."""
        state = {**batch_state, "messages": messages}
        result = await self._tool_node.ainvoke(_tool_packet(call, state))
        out = result["messages"][-1] if isinstance(result, dict) else result[-1]  # dict, or [Command]
        changes: dict = {}
        if isinstance(out, Command):  # skills: a state update plus the ToolMessage
            _apply(state, changes, out.update)
            out = next(
                (
                    m
                    for m in reversed(((out.update or {}).get("messages")) or [])
                    if isinstance(m, ToolMessage) and m.tool_call_id == call["id"]
                ),
                None,
            )
            if out is None:
                msg = f"Tool {call['name']!r} returned a Command without a ToolMessage for call {call['id']!r}."
                raise ValueError(msg)
        return out, changes

    def _note_return_direct(self, messages: list[BaseMessage]) -> None:
        """create_agent ends the run once every tool the turn called is `return_direct`."""
        tools = self._tool_node.tools_by_name
        turn = [c for c in messages[-1].tool_calls if c["name"] in tools]
        if turn and all(tools[c["name"]].return_direct for c in turn):
            self._stopped = True

    async def _run_finish(self, messages: list[BaseMessage], *, runtime: Runtime) -> None:
        state, changes = {**self._state, "messages": add_messages([], messages)}, {}
        await self._run_hooks(self._after_agent, state, changes, runtime)
        self._state.update(changes)
