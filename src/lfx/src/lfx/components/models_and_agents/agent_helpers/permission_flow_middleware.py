"""Apply a reviewed permission decision without bypassing per-call human approval."""

import asyncio
from copy import deepcopy

from langchain_core.callbacks.manager import adispatch_custom_event
from langchain_core.messages import ToolMessage
from langgraph.func import task

from lfx.base.agents.permissions import Permission, PermissionFlowError, PermissionSourceChangedError
from lfx.components.models_and_agents.agent_helpers.harness_middleware import HARNESS_EVENT
from lfx.components.models_and_agents.agent_helpers.permission_middleware import ToolApprovalMiddleware
from lfx.projects.permissions import PermissionFlowRunner


class PermissionFlowMiddleware(ToolApprovalMiddleware):
    def __init__(self, component, binding, interrupt_on):
        super().__init__(interrupt_on, policy="flow")
        self.binding = binding
        self.required_actions = {
            tool.name: list((tool.metadata or {}).get("approval_actions") or []) for tool in component.tools or []
        }
        self.runner = PermissionFlowRunner(component, binding)

    def wrap_tool_call(self, request, handler):  # noqa: ARG002
        msg = "Permission flows require asynchronous Agent execution. Use the flow runtime or ainvoke."
        raise PermissionFlowError(msg)

    def _evidence(self, call, **values):
        return {
            "kind": "permission_decision",
            "policy": "flow",
            "tool_name": call["name"],
            "tool_call_id": call["id"],
            "flow_id": self.binding.flow_id,
            "revision": self.binding.revision,
            "version_id": self.binding.version_id,
            "timeout_seconds": self.binding.timeout_seconds,
            **values,
        }

    async def _decide(self, call, *, phase="requested"):
        snapshot = {
            "binding": self.binding.model_dump(),
            "request": {
                "tool_name": call["name"],
                "args": deepcopy(call["args"]),
                "tool_call_id": call["id"],
                "approval_actions": self.required_actions.get(call["name"], []),
            },
        }
        completed = None

        @task(name="harness_permission_decision")
        async def decide(value):
            nonlocal completed
            # Pin the decision and its exact request in the checkpoint before an
            # interrupt. Replays reuse it even if the flow would now decide differently.
            decision = await asyncio.wait_for(self.runner(deepcopy(value["request"])), self.binding.timeout_seconds)
            completed = {"snapshot": value, "decision": decision.model_dump()}
            return completed

        try:
            recorded = await decide(snapshot)
            # Installed LangGraph's astream_events writes the task result to the
            # checkpoint but resolves the first execution's future with None. Keep
            # that invocation's result locally; replay still uses the durable value.
            if recorded is None:
                recorded = completed
            if recorded["snapshot"] != snapshot:
                msg = "Permission configuration or tool arguments changed after review. Start a new run."
                raise PermissionSourceChangedError(msg)
            decision = Permission.model_validate(recorded["decision"])
        except Exception as exc:
            reason = "The permission flow failed. The tool was not executed; inspect the permission evidence."
            if isinstance(exc, PermissionSourceChangedError):
                reason = "Permission configuration or tool arguments changed. Review them and start a new run."
            elif isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
                reason = "The permission flow timed out. The tool was not executed."
            await adispatch_custom_event(
                HARNESS_EVENT,
                self._evidence(
                    call, kind="permission_failed", error_type=type(exc).__name__, reason=reason, phase=phase
                ),
            )
            raise PermissionFlowError(reason) from exc
        await adispatch_custom_event(
            HARNESS_EVENT, self._evidence(call, decision=decision.action, reason=decision.reason, phase=phase)
        )
        return decision

    @staticmethod
    def _reject(call, reason):
        return ToolMessage(
            content=reason or "The permission flow rejected this call. The tool was not executed. Do not retry it.",
            name=call["name"],
            tool_call_id=call["id"],
            status="error",
        )

    async def awrap_tool_call(self, request, handler):
        decision = await self._decide(request.tool_call)
        if decision.action == "reject":
            return self._reject(request.tool_call, decision.reason)
        reviewed = request
        if decision.action == "ask" or self.required_actions.get(request.tool_call["name"]):
            reviewed, result, evidence = self._review(request, description=decision.reason)
            if evidence:
                await adispatch_custom_event(
                    HARNESS_EVENT, {**self._evidence(request.tool_call, phase="human"), **evidence}
                )
            if result is not None:
                return result
            if reviewed.tool_call != request.tool_call:
                # Human edits can change the capability being exercised. Recheck the
                # edited call against the flow before invoking the tool. An ask result
                # needs no second approval: this exact edit was supplied by the human.
                edited = await self._decide(reviewed.tool_call, phase="edited")
                if edited.action == "reject":
                    return self._reject(reviewed.tool_call, edited.reason)
        return await handler(reviewed)
