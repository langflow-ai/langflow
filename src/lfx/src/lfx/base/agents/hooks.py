"""Contracts and ordered execution for flow implementations of the Hook slot."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lfx.projects.bindings import FlowBinding

HookEvent = Literal["before_llm_call", "after_llm_call", "before_tool_call", "after_tool_call"]


class HookDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["pass", "block", "modify"] = "pass"
    reason: str = ""
    modified_payload: dict[str, Any] | None = None

    @model_validator(mode="after")
    def require_modified_payload(self):
        if (self.action == "modify") != (self.modified_payload is not None):
            msg = "Only a modify decision must supply modified_payload."
            raise ValueError(msg)
        return self


class HookBinding(FlowBinding):
    on_event: HookEvent
    priority: int = Field(default=0, ge=-10000, le=10000)
    mode: Literal["observe", "control"] = "observe"
    timeout_seconds: float = Field(default=10, gt=0, le=300)
    on_failure: Literal["continue", "stop"] = "continue"

    @model_validator(mode="after")
    def validate_control(self):
        if self.mode == "control" and (self.on_failure != "stop" or self.on_event == "after_llm_call"):
            msg = "Controlling hooks must stop on failure and cannot run after a model call."
            raise ValueError(msg)
        return self


class HookExecutionError(ValueError):
    """The required hook did not complete successfully; the affected operation must stop."""


class HookBlockedError(HookExecutionError):
    """A controlling hook blocked a model call."""


class HookSourceChangedError(ValueError):
    """A reviewed flow definition no longer matches its saved binding."""


class HookExecutor:
    """Run each event's hooks in priority/list order with one failure policy and evidence shape.

    The runner executes a reviewed flow; the validator constrains modifications for this
    invocation point. Both receive copies so a failed hook cannot mutate the caller's payload.
    Independent tool calls may execute concurrently. Hooks are not retried here.
    """

    def __init__(self, bindings, runner, emit):
        self.bindings = sorted(enumerate(bindings), key=lambda item: (item[1].priority, item[0]))
        self.runner = runner
        self.emit = emit

    async def invoke(self, event: HookEvent, payload: dict, validate):
        current = deepcopy(payload)
        for index, binding in self.bindings:
            if binding.on_event != event:
                continue
            evidence = {
                "kind": "hook_completed",
                "event": event,
                "hook_index": index,
                "flow_id": binding.flow_id,
                "revision": binding.revision,
                "version_id": binding.version_id,
                "priority": binding.priority,
                "mode": binding.mode,
                "timeout_seconds": binding.timeout_seconds,
                "tool_call_id": current.get("tool_call_id"),
            }
            try:
                result = await asyncio.wait_for(self.runner(binding, deepcopy(current)), binding.timeout_seconds)
                decision = result if isinstance(result, HookDecision) else HookDecision.model_validate(result)
                if binding.mode == "observe" and decision.action != "pass":
                    msg = "An observation hook cannot change or block an invocation."
                    raise ValueError(msg)
                if event == "after_tool_call" and decision.action == "block":
                    msg = "A hook cannot block a tool that has already executed."
                    raise ValueError(msg)
                if decision.action == "modify":
                    updated = {**current, **deepcopy(decision.modified_payload)}
                    validate(updated, decision.modified_payload)
                    current = updated
                evidence.update(action=decision.action, reason=decision.reason)
            except Exception as exc:
                # Flow errors may contain source code, credentials, or tool arguments.
                # Publish the exception type, never its rendered payload.
                evidence.update(kind="hook_failed", error_type=type(exc).__name__, on_failure=binding.on_failure)
                if isinstance(exc, HookSourceChangedError):
                    evidence["reason"] = "The Hook flow changed. Review it and update the binding."
                elif isinstance(exc, (TimeoutError, asyncio.TimeoutError)):
                    evidence["reason"] = "The Hook flow exceeded its configured timeout."
                await self.emit(evidence)
                if binding.on_failure == "stop":
                    msg = f"Hook {index + 1} failed during {event}. The operation stopped; inspect the hook evidence."
                    raise HookExecutionError(msg) from exc
                continue
            await self.emit(evidence)
            if decision.action == "block":
                return current, decision.reason or "Blocked by a harness hook."
        return current, None
