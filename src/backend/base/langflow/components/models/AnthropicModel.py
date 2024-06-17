from typing import Optional

from langchain_anthropic.chat_models import ChatAnthropic
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import BaseLanguageModel, Text
from langflow.inputs import BoolInput, DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput
from langflow.template import Output


class AnthropicModelComponent(LCModelComponent):
    display_name = "Anthropic"
    description = "Generate text using Anthropic Chat&Completion LLMs with prefill support."
    icon = "Anthropic"

    inputs = [
        StrInput(
            name="input_value",
            display_name="Input",
            input_types=["Text", "Data", "Prompt", "Message"]),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model",
            display_name="Model Name",
            options=[
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229", 
                "claude-3-haiku-20240307",
                "claude-2.1",
                "claude-2.0",
                "claude-instant-1.2",
                "claude-instant-1",
            ],
            info="https://python.langchain.com/docs/integrations/chat/anthropic",
            value="claude-3-opus-20240229",
        ),
        SecretStrInput(
            name="anthropic_api_key",
            display_name="Anthropic API Key",
            info="Your Anthropic API key.",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        StrInput(
            name="anthropic_api_url",
            display_name="Anthropic API URL",
            advanced=True,
            info="Endpoint of the Anthropic API. Defaults to 'https://api.anthropic.com' if not specified.",
        ),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        StrInput(
            name="prefill",
            display_name="Prefill",
            info="Prefill text to guide the model's response.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def text_response(self) -> Text:
        input_value = self.input_value
        system_message = self.system_message
        prefill = self.prefill
        output = self.build_model()
        messages = [
            ("system", system_message),
            ("human", input_value),
        ]
        if prefill:
            messages.append(("assistant", prefill))
        result = output.invoke(messages)
        self.status = result.content
        return prefill + result.content

    def build_model(self) -> BaseLanguageModel:
        model = self.model
        anthropic_api_key = self.anthropic_api_key
        max_tokens = self.max_tokens
        temperature = self.temperature
        anthropic_api_url = self.anthropic_api_url or "https://api.anthropic.com"

        try:
            output = ChatAnthropic(
                model=model,
                anthropic_api_key=(SecretStr(anthropic_api_key) if anthropic_api_key else None),
                max_tokens_to_sample=max_tokens,  # type: ignore
                temperature=temperature,
                anthropic_api_url=anthropic_api_url,
            )
        except Exception as e:
            raise ValueError("Could not connect to Anthropic API.") from e

        return output
    
