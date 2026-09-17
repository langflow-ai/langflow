"""Prepare model context and compact history through the existing agent middleware path."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware
from langchain_core.callbacks.manager import adispatch_custom_event, dispatch_custom_event
from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage, get_buffer_string
from langchain_core.messages.utils import count_tokens_approximately

if TYPE_CHECKING:
    from lfx.base.agents.harness import HarnessRuntimeConfig

HARNESS_EVENT = "harness_runtime"
SUMMARY_TAG = "harness:compaction"
SUMMARY_MARKER = "harness_compaction_summary"


def prepare_context(messages: list, turns: int) -> list:
    """Select whole user turns; never split a call from its results or mutate stored history."""
    starts = [
        index
        for index, message in enumerate(messages)
        if isinstance(message, HumanMessage) and not message.additional_kwargs.get(SUMMARY_MARKER)
    ]
    if len(starts) <= turns:
        return list(messages)
    cutoff = starts[-turns]
    return [
        message
        for index, message in enumerate(messages)
        if index >= cutoff or isinstance(message, SystemMessage) or message.additional_kwargs.get(SUMMARY_MARKER)
    ]


class HarnessContextMiddleware(AgentMiddleware):
    def __init__(self, policy: HarnessRuntimeConfig, *, context_flow=None):
        self.policy = policy
        self.context_flow = context_flow

    def _prepare(self, request):
        messages = request.messages
        prepared = (
            prepare_context(messages, self.policy.context_turns)
            if self.policy.context_strategy == "recent_turns"
            else list(messages)
        )
        return request.override(messages=prepared), self._evidence(messages, prepared)

    def _evidence(self, messages, prepared):
        return {
            "kind": "context_prepared",
            "strategy": "flow" if self.context_flow else self.policy.context_strategy,
            "messages_before": len(messages),
            "messages_after": len(prepared),
            "estimated_tokens": count_tokens_approximately(prepared),
            "retained_message_ids": [m.id for m in prepared if m.id],
            "iteration_limit": self.policy.max_iterations,
        }

    def wrap_model_call(self, request, handler):
        if self.context_flow:
            from lfx.projects.context import ContextFlowError

            msg = "Context flows require asynchronous Agent execution. Use the flow runtime or ainvoke."
            raise ContextFlowError(msg)
        prepared, evidence = self._prepare(request)
        dispatch_custom_event(HARNESS_EVENT, evidence)
        return handler(prepared)

    async def awrap_model_call(self, request, handler):
        if self.context_flow:
            from lfx.projects.context import ContextFlowError, ContextSourceChangedError

            binding = self.context_flow.binding
            try:
                messages = await asyncio.wait_for(self.context_flow(request.messages), timeout=binding.timeout_seconds)
                prepared, evidence = request.override(messages=messages), self._evidence(request.messages, messages)
            except Exception as exc:
                reason = (
                    str(exc)
                    if isinstance(exc, ContextSourceChangedError)
                    else "Context flow timed out. Its output was not applied; review the flow or its timeout."
                    if isinstance(exc, (TimeoutError, asyncio.TimeoutError))
                    else "Context flow failed. Its output was not applied; review its message table before retrying."
                )
                await adispatch_custom_event(
                    HARNESS_EVENT,
                    {
                        "kind": "context_failed",
                        "strategy": "flow",
                        **binding.model_dump(),
                        "error_type": type(exc).__name__,
                        "reason": reason,
                    },
                )
                raise ContextFlowError(reason) from exc
            evidence.update(binding.model_dump())
        else:
            prepared, evidence = self._prepare(request)
        await adispatch_custom_event(HARNESS_EVENT, evidence)
        return await handler(prepared)


class HarnessCompactionMiddleware(SummarizationMiddleware):
    """Use LangChain's pair-safe partitioning; stop on summary failure without losing history."""

    def __init__(self, model: Any, policy: HarnessRuntimeConfig):
        super().__init__(
            model=model,
            trigger=("tokens", policy.compaction_trigger_tokens),
            keep=("messages", policy.compaction_keep_messages),
            trim_tokens_to_summarize=None,
        )
        self.policy = policy

    def _prompt(self, messages):
        return self.summary_prompt.format(messages=get_buffer_string(messages, format="xml")).rstrip() + (
            "\nPreserve source identifiers, URLs, and unresolved questions. Distinguish evidence from inference."
        )

    @staticmethod
    def _summary_text(response):
        text = response.text
        if not isinstance(text, str) or not text.strip():
            msg = "Compaction returned no summary. No context was removed."
            raise ValueError(msg)
        return text.strip()

    def _create_summary(self, messages_to_summarize):
        try:
            return self._summary_text(
                self.model.invoke(self._prompt(messages_to_summarize), config={"tags": [SUMMARY_TAG]})
            )
        except Exception as exc:
            msg = "Compaction failed. No context was removed; retry or turn compaction off."
            raise ValueError(msg) from exc

    async def _acreate_summary(self, messages_to_summarize):
        try:
            return self._summary_text(
                await self.model.ainvoke(self._prompt(messages_to_summarize), config={"tags": [SUMMARY_TAG]})
            )
        except Exception as exc:
            msg = "Compaction failed. No context was removed; retry or turn compaction off."
            raise ValueError(msg) from exc

    @staticmethod
    def _build_new_messages(summary):
        return [
            HumanMessage(
                content=f"Summary of earlier conversation:\n{summary}", additional_kwargs={SUMMARY_MARKER: True}
            )
        ]

    def _evidence(self, before, update):
        after = [message for message in update["messages"] if not isinstance(message, RemoveMessage)]
        return {
            "kind": "compacted",
            "messages_before": len(before),
            "messages_after": len(after),
            "trigger_tokens": self.policy.compaction_trigger_tokens,
            "retained_messages": len(after) - 1,
            "summary": after[0].content,
        }

    def before_model(self, state, runtime):
        update = super().before_model(state, runtime)
        if update:
            dispatch_custom_event(HARNESS_EVENT, self._evidence(state["messages"], update))
        return update

    async def abefore_model(self, state, runtime):
        update = await super().abefore_model(state, runtime)
        if update:
            await adispatch_custom_event(HARNESS_EVENT, self._evidence(state["messages"], update))
        return update
