import json

from desco_llm.commons.enums import LLMsEnum
from desco_llm.langchain.gateway_chat import GatewayChat
from loguru import logger

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import BoolInput, DropdownInput, FloatInput, IntInput, MultilineInput, StrInput


models = [
    LLMsEnum.GPT_4O_MINI_128K,
    LLMsEnum.GPT_4O_128K,
    LLMsEnum.GPT_4_TURBO_128K,
    LLMsEnum.CLAUDE_35_SONNET_200K,
    LLMsEnum.CLAUDE_35_HAIKU_200K,
    LLMsEnum.CLAUDE_3_SONNET_200K,
    LLMsEnum.CLAUDE_3_HAIKU_200K,
    LLMsEnum.CLAUDE_3_OPUS_200K,
]


class DescoGatewayChatModelComponent(LCModelComponent):
    display_name = "DescoGatewayChat"
    description = "Generates text using DescoGatewayChat LLMs."
    icon = "DescoGatewayChat"
    name = "DescoGatewayChatModel"

    inputs = [
        *LCModelComponent._base_inputs,
        StrInput(
            name="project_name",
            display_name="Project Name",
            info="Enter the project name",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=models,
            value=LLMsEnum.GPT_4_TURBO_128K,
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing an output schema. Make sure to instruct the model to output in JSON in the System message",
            value=False,
        ),
        MultilineInput(
            name="output_schema",
            display_name="Output Schema",
            advanced=True,
            info="The output schema in JSON schema format. Make sure to turn off stream when using structured output. It is currently not supported.",
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            value=0.1
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=128000),
            value=0,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]

        project_name: str = self.project_name
        model: str = self.model_name
        streaming: bool = self.stream
        temperature = self.temperature

        logger.info(f"Building Desco Gateway Chat model with project name: {project_name}, model name: {model}")
        
        output = GatewayChat(
            project_name=project_name,
            model=model,
            temperature=temperature if temperature is not None else 0.1,
            streaming=streaming,
        )
        
        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})
            return output
            
        if self.output_schema:
            logger.info(f"Received Output Schema: {self.output_schema}")
            output_schema_dict = json.loads(self.output_schema)
            logger.info(f"Transformed dict: {output_schema_dict}")
            output = output.with_structured_output(schema=output_schema_dict)
            return output
        
        return output

    def _get_exception_message(self, e: Exception):
        """Get a message from an DescoGatewayChat exception.

        Args:
            e (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        if e.message:
                return e.message
        
        return super()._get_exception_message(e)