"""Adapt four model/tool invocation points to the ordered Hook contract."""

import json
from copy import deepcopy

from langchain.agents.middleware import AgentMiddleware
from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import AIMessage, ToolMessage, message_to_dict, messages_from_dict
from langchain_core.runnables import RunnableLambda
from pydantic import TypeAdapter

from lfx.base.agents.hooks import HookBinding, HookBlockedError, HookExecutionError, HookExecutor
from lfx.components.models_and_agents.agent_helpers.harness_middleware import HARNESS_EVENT
from lfx.projects.hooks import HookFlowRunner


def parse_hook_bindings(value: str) -> list[HookBinding]:
    return TypeAdapter(list[HookBinding]).validate_python(json.loads(value or "[]"))


def _tool_name(tool):
    if isinstance(tool, dict):
        return tool.get("name") or tool.get("function", {}).get("name") or tool.get("type")
    return tool.name


def _messages(value):
    messages = messages_from_dict(value)
    pending = set()
    for message in messages:
        if isinstance(message, ToolMessage):
            if message.tool_call_id not in pending:
                msg = "A modified tool result must match a preceding call."
                raise ValueError(msg)
            pending.remove(message.tool_call_id)
        else:
            if pending:
                msg = "A hook must keep tool calls and results together."
                raise ValueError(msg)
            if isinstance(message, AIMessage):
                pending = {call["id"] for call in message.tool_calls}
    if pending:
        msg = "A hook must keep tool calls and results together."
        raise ValueError(msg)
    return messages


class HarnessHookMiddleware(AgentMiddleware):
    def __init__(self, component, bindings):
        async def emit(evidence):
            await adispatch_custom_event(HARNESS_EVENT, evidence)

        flow_runner = HookFlowRunner(component)

        async def invoke_flow(invocation):
            binding, payload = invocation
            return await flow_runner(binding, payload)

        async def run_hook(binding, payload):
            # Nested hook models/tools remain visible to usage and trace callbacks,
            # while the presentation adapter excludes their tokens from the answer.
            return await RunnableLambda(invoke_flow, name="harness_hook_flow").ainvoke(
                (binding, payload), config={"tags": ["harness:hook"]}
            )

        self.hooks = HookExecutor(bindings, run_hook, emit)

    def wrap_model_call(self, request, handler):  # noqa: ARG002
        msg = "Hook flows require asynchronous Agent execution. Use the flow runtime or ainvoke."
        raise HookExecutionError(msg)

    def wrap_tool_call(self, request, handler):  # noqa: ARG002
        msg = "Hook flows require asynchronous Agent execution. Use the flow runtime or ainvoke."
        raise HookExecutionError(msg)

    async def awrap_model_call(self, request, handler):
        names = [_tool_name(tool) for tool in request.tools]
        original_messages = [message_to_dict(m) for m in request.messages]

        def validate(payload, changed):
            if set(changed) - {"messages", "tool_names"}:
                msg = "Before-model hooks may change only messages and tool_names."
                raise ValueError(msg)
            selected = payload["tool_names"]
            if not isinstance(selected, list) or any(name not in names for name in selected):
                msg = "A hook may only select tools already connected to this agent."
                raise ValueError(msg)
            if "messages" in changed:
                _messages(payload["messages"])

        payload, blocked = await self.hooks.invoke(
            "before_llm_call",
            {"messages": original_messages, "tool_names": names},
            validate,
        )
        if blocked:
            raise HookBlockedError(blocked)
        result = await handler(
            request.override(
                messages=request.messages
                if payload["messages"] == original_messages
                else _messages(payload["messages"]),
                tools=[tool for tool in request.tools if _tool_name(tool) in payload["tool_names"]],
            )
        )
        await self.hooks.invoke("after_llm_call", {"response": [message_to_dict(m) for m in result.result]}, validate)
        return result

    async def awrap_tool_call(self, request, handler):
        call = request.tool_call

        def validate_before(payload, changed):
            if set(changed) - {"args"} or not isinstance(payload["args"], dict):
                msg = "Before-tool hooks may change only the args object."
                raise ValueError(msg)

        payload, blocked = await self.hooks.invoke(
            "before_tool_call",
            {"tool_name": call["name"], "args": deepcopy(call["args"]), "tool_call_id": call["id"]},
            validate_before,
        )
        if blocked:
            return ToolMessage(content=blocked, name=call["name"], tool_call_id=call["id"], status="error")
        try:
            result = await handler(request.override(tool_call={**call, "args": payload["args"]}))
        except Exception as exc:

            def reject_modification(_payload, _changed):
                msg = "A failed tool invocation has no result to modify."
                raise ValueError(msg)

            await self.hooks.invoke(
                "after_tool_call",
                {
                    "tool_name": call["name"],
                    "tool_call_id": call["id"],
                    "is_error": True,
                    "error_type": type(exc).__name__,
                    "result": None,
                },
                reject_modification,
            )
            raise

        def validate_after(payload, changed):
            if (
                set(changed) - {"result"}
                or not isinstance(result, ToolMessage)
                or not isinstance(payload["result"], str)
            ):
                msg = "After-tool hooks may replace only a tool message's result text."
                raise ValueError(msg)

        payload, _ = await self.hooks.invoke(
            "after_tool_call",
            {
                "tool_name": call["name"],
                "tool_call_id": call["id"],
                "is_error": getattr(result, "status", None) == "error",
                "result": result.content if isinstance(result, ToolMessage) else None,
            },
            validate_after,
        )
        return result.model_copy(update={"content": payload["result"]}) if isinstance(result, ToolMessage) else result
