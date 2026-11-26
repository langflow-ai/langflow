"""Typed compaction results and the shared summarization implementation."""

from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy

from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import HumanMessage, SystemMessage, get_buffer_string, messages_to_dict
from pydantic import BaseModel, ConfigDict, Field, field_serializer

from lfx.base.agents.context_messages import messages_from_table
from lfx.schema.dataframe import DataFrame
from lfx.schema.message import Message

SUMMARY_TAG = "harness:compaction"
SUMMARY_MARKER = "harness_compaction_summary"
# The borrowed model is invocation-local; it never enters a serialized flow definition or payload.
COMPACTION_MODEL: ContextVar = ContextVar("harness_compaction_model", default=None)


class CompactionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, arbitrary_types_allowed=True)

    kept_messages: DataFrame
    summary_message: Message | None = None
    dropped_count: int = Field(ge=0)

    @field_serializer("kept_messages")
    def serialize_messages(self, value):
        return value.to_dict(orient="records")

    def apply(self, original: list):
        """Validate the entire replacement before the caller changes conversation state."""
        kept = messages_from_table(self.kept_messages)
        before = messages_to_dict(original)
        retained = messages_to_dict(kept)
        cursor = 0
        for row in retained:
            while cursor < len(before) and before[cursor] != row:
                cursor += 1
            if cursor == len(before):
                msg = "Compaction must retain original messages unchanged and in order."
                raise ValueError(msg)
            cursor += 1
        if self.dropped_count != len(original) - len(kept):
            msg = "Compaction dropped_count must match the messages removed."
            raise ValueError(msg)
        # Compare content, including IDs when present. Greedy subsequence matches can
        # otherwise mistake a repeated latest message without an ID for an older copy.
        original_systems = messages_to_dict([message for message in original if isinstance(message, SystemMessage)])
        retained_systems = messages_to_dict([message for message in kept if isinstance(message, SystemMessage)])
        if original_systems != retained_systems or (original and (not retained or retained[-1] != before[-1])):
            msg = "Compaction must preserve system messages and the latest message."
            raise ValueError(msg)
        summary = self.summary_message
        if summary is not None:
            if not self.dropped_count or not isinstance(summary.text, str) or not summary.text.strip():
                msg = "A compaction summary must be non-empty and replace at least one message."
                raise ValueError(msg)
            prefix = next((i for i, message in enumerate(kept) if not isinstance(message, SystemMessage)), len(kept))
            kept.insert(
                prefix,
                HumanMessage(
                    content=f"Summary of earlier conversation:\n{summary.text.strip()}",
                    additional_kwargs={SUMMARY_MARKER: True},
                ),
            )
        return deepcopy(kept)


class ConversationSummarizer(SummarizationMiddleware):
    """LangChain owns thresholds and pair-safe partitioning; this owns summary content/failure."""

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
