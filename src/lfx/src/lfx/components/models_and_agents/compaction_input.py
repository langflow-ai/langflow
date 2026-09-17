import json

from lfx.custom import Component
from lfx.field_typing import LanguageModel
from lfx.io import HandleInput, MultilineInput, Output
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame


class CompactionInputComponent(Component):
    display_name = "Compaction Input"
    description = "Conversation, trigger details, and the harness model supplied when compaction runs."
    icon = "MessagesSquare"
    name = "CompactionInput"
    inputs = [
        MultilineInput(
            name="sample_messages",
            display_name="Preview messages",
            value='[{"type":"human","data":{"content":"Earlier question"}},'
            '{"type":"ai","data":{"content":"Earlier evidence [source-1]"}},'
            '{"type":"human","data":{"content":"Continue researching."}}]',
            info="Standalone preview only. Runtime uses the actual conversation.",
        ),
        HandleInput(
            name="preview_model",
            display_name="Preview model",
            input_types=["LanguageModel"],
            info="Connect a model for standalone previews. Runtime borrows the harness model.",
            required=False,
        ),
    ]
    outputs = [
        Output(name="messages", display_name="Messages", method="build_messages", group_outputs=True),
        Output(name="trigger", display_name="Trigger", method="build_trigger", group_outputs=True),
        Output(name="model", display_name="Model", method="build_model", group_outputs=True),
    ]

    def _context(self):
        from lfx.projects.compaction import COMPACTION_INPUT

        return (self.graph.context or {}).get(COMPACTION_INPUT) if self.graph else None

    def build_messages(self) -> DataFrame:
        from lfx.base.agents.context_messages import messages_from_rows, messages_to_table

        context = self._context()
        rows = context["messages"] if context is not None else json.loads(self.sample_messages)
        return messages_to_table(messages_from_rows(rows))

    def build_trigger(self) -> Data:
        context = self._context()
        return Data(
            data={key: value for key, value in context.items() if key != "messages"}
            if context is not None
            else {"trigger_reason": "manual"}
        )

    def build_model(self) -> LanguageModel:
        from lfx.base.agents.compaction import COMPACTION_MODEL

        model = COMPACTION_MODEL.get() if self._context() is not None else self.preview_model
        if model is None:
            msg = "Connect a Preview model to run this flow outside its harness."
            raise ValueError(msg)
        return model
