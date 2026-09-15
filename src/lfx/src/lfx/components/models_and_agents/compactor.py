from copy import deepcopy

from langchain_core.messages import SystemMessage

from lfx.base.agents.compaction import CompactionResult, ConversationSummarizer
from lfx.custom import Component
from lfx.io import DataFrameInput, HandleInput, IntInput, MultilineInput, Output
from lfx.schema.message import Message


class CompactorComponent(Component):
    display_name = "Compact Conversation"
    description = "Summarize older messages with a model while keeping recent messages and tool pairs intact."
    icon = "Archive"
    name = "Compactor"
    inputs = [
        DataFrameInput(name="messages", display_name="Messages", required=True),
        HandleInput(name="model", display_name="Model", input_types=["LanguageModel"], required=True),
        IntInput(name="keep_messages", display_name="Keep recent messages", value=12),
        MultilineInput(
            name="instructions",
            display_name="Summary instructions",
            value="",
            info="Additional guidance for the summary. Source identifiers and URLs are preserved by default.",
        ),
    ]
    outputs = [Output(name="result", display_name="Compaction", method="compact")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_output = True

    async def compact(self) -> CompactionResult:
        from lfx.base.agents.context_messages import messages_from_table, messages_to_table
        from lfx.base.agents.harness import HarnessRuntimeConfig

        policy = HarnessRuntimeConfig(compaction_keep_messages=self.keep_messages)
        messages = messages_from_table(self.messages)
        # System messages remain verbatim; they are not evidence to summarize away.
        conversation = [message for message in messages if not isinstance(message, SystemMessage)]
        summarizer = ConversationSummarizer(
            model=self.model,
            trigger=("tokens", 1),
            keep=("messages", policy.compaction_keep_messages),
            trim_tokens_to_summarize=None,
        )
        summarizer.summary_prompt += "\n" + self.instructions.replace("{", "{{").replace("}", "}}")
        update = await summarizer.abefore_model({"messages": deepcopy(conversation)}, None)
        if not update:
            return CompactionResult(kept_messages=messages_to_table(messages), dropped_count=0)
        # Remove-all sentinel, summary, then the untouched suffix selected by LangChain.
        suffix = update["messages"][2:]
        cutoff = len(conversation) - len(suffix)
        keep_indices = {i for i, message in enumerate(messages) if isinstance(message, SystemMessage)}
        conversation_indices = [i for i, message in enumerate(messages) if not isinstance(message, SystemMessage)]
        keep_indices.update(conversation_indices[cutoff:])
        kept = [message for i, message in enumerate(messages) if i in keep_indices]
        summary = update["messages"][1].content.removeprefix("Summary of earlier conversation:\n")
        return CompactionResult(
            kept_messages=messages_to_table(kept),
            summary_message=Message(text=summary),
            dropped_count=len(messages) - len(kept),
        )
