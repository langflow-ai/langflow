from typing import Any

from lfx.base.models.language_model_mixin import LanguageModelMixin
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.io import MessageInput, MultilineInput
from lfx.schema.dotdict import dotdict


class LanguageModelComponent(LanguageModelMixin, LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 0  # Set priority to 0 to make it appear first

    inputs = [
        *LanguageModelMixin.get_llm_inputs(
            include_input_value=False,
            include_system_message=False,
            include_stream=True,
            include_temperature=True,
        ),
        MessageInput(
            name="input_value",
            display_name="Input",
            info="The input text to send to the model",
        ),
        MultilineInput(
            name="system_message",
            display_name="System Message",
            info="A system message that helps set the behavior of the assistant",
            advanced=False,
        ),
    ]

    def build_model(self) -> LanguageModel:
        return self.build_llm()

    async def update_build_config(
        self, build_config: dotdict, field_value: Any, field_name: str | None = None
    ) -> dotdict:
        return await self.update_llm_provider_config(build_config, field_value, field_name)
