"""Tool policy using the existing approval vocabulary, checkpoints, and event stream."""

from langchain.agents.middleware import AgentMiddleware, HumanInTheLoopMiddleware
from langchain_core.callbacks.manager import adispatch_custom_event, dispatch_custom_event
from langchain_core.messages import ToolMessage
from langgraph.types import interrupt

from lfx.components.models_and_agents.agent_helpers.harness_middleware import HARNESS_EVENT


def permission_evidence(tool_call, decision, policy):
    return {
        "kind": "permission_decision",
        "policy": policy,
        "decision": decision,
        "tool_name": tool_call["name"],
        "tool_call_id": tool_call["id"],
    }


class DenyToolsMiddleware(AgentMiddleware):
    """Return a matched tool result without invoking the tool, including during retries."""

    @staticmethod
    def _result(request):
        return ToolMessage(
            content="Harness permissions block all tools. This tool was not executed. Do not retry it.",
            name=request.tool_call["name"],
            tool_call_id=request.tool_call["id"],
            status="error",
        )

    def wrap_tool_call(self, request, handler):  # noqa: ARG002
        dispatch_custom_event(HARNESS_EVENT, permission_evidence(request.tool_call, "reject", "deny"))
        return self._result(request)

    async def awrap_tool_call(self, request, handler):  # noqa: ARG002
        await adispatch_custom_event(HARNESS_EVENT, permission_evidence(request.tool_call, "reject", "deny"))
        return self._result(request)


class ToolApprovalMiddleware(HumanInTheLoopMiddleware):
    """Interrupt at each tool call so one card can authorize only that identified call.

    LangGraph checkpoints parallel tool tasks independently. A resume must be keyed by
    interrupt ID; otherwise an answer can be applied to another pending tool task.
    The inherited decision processor preserves approve/edit/reject/respond semantics.
    """

    def __init__(self, interrupt_on, *, policy):
        super().__init__(interrupt_on=interrupt_on)
        self.policy = policy

    def after_model(self, state, runtime):  # noqa: ARG002
        return None

    async def aafter_model(self, state, runtime):  # noqa: ARG002
        return None

    def _review(self, request, *, description=None):
        config = self.interrupt_on.get(request.tool_call["name"])
        if config is None:
            return request, None, None
        action, review = self._create_action_and_config(request.tool_call, config, request.state, request.runtime)
        action["tool_call_id"] = request.tool_call["id"]
        if description:
            action["description"] = description
        response = interrupt({"action_requests": [action], "review_configs": [review]})
        reviewed = response.get("reviewed_action")
        if reviewed and any(reviewed.get(key) != action.get(key) for key in ("name", "args", "tool_call_id")):
            # A replayed before-tool hook may return different arguments. The old
            # approval cannot authorize those newly computed arguments.
            msg = "Tool arguments changed after review. The tool was not executed; run again for a fresh approval."
            return (
                request,
                ToolMessage(
                    content=msg, name=request.tool_call["name"], tool_call_id=request.tool_call["id"], status="error"
                ),
                permission_evidence(request.tool_call, "reject_changed_arguments", self.policy),
            )
        decisions = response.get("decisions", [])
        if len(decisions) != 1:
            msg = "Exactly one decision is required for this pending tool call."
            raise ValueError(msg)
        call, result = self._process_decision(decisions[0], request.tool_call, config)
        evidence = permission_evidence(request.tool_call, decisions[0]["type"], self.policy)
        return request.override(tool_call=call) if call else request, result, evidence

    def wrap_tool_call(self, request, handler):
        reviewed, result, evidence = self._review(request)
        if evidence:
            dispatch_custom_event(HARNESS_EVENT, evidence)
        return result if result is not None else handler(reviewed)

    async def awrap_tool_call(self, request, handler):
        reviewed, result, evidence = self._review(request)
        if evidence:
            await adispatch_custom_event(HARNESS_EVENT, evidence)
        return result if result is not None else await handler(reviewed)
