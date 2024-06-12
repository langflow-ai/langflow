from typing import Optional

from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import MODEL_NAMES
from langflow.field_typing import BaseLanguageModel, Text
from langflow.template import Input, Output


class OpenAIModelComponent(LCModelComponent):
    display_name = "OpenAI"
    description = "Generates text using OpenAI LLMs."
    icon = "OpenAI"

    inputs = [
        Input(name="input_value", type=str, display_name="Input", input_types=["Text", "Record", "Prompt"]),
        Input(
            name="max_tokens",
            type=Optional[int],
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        Input(name="model_kwargs", type=dict, display_name="Model Kwargs", advanced=True),
        Input(name="model_name", type=str, display_name="Model Name", advanced=False, options=MODEL_NAMES),
        Input(
            name="openai_api_base",
            type=Optional[str],
            display_name="OpenAI API Base",
            advanced=True,
            info="The base URL of the OpenAI API. Defaults to https://api.openai.com/v1.\n\nYou can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),
        Input(
            name="openai_api_key",
            type=str,
            display_name="OpenAI API Key",
            info="The OpenAI API Key to use for the OpenAI model.",
            advanced=False,
            password=True,
        ),
        Input(name="temperature", type=float, display_name="Temperature", advanced=False, default=0.1),
        Input(name="stream", type=bool, display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        Input(
            name="system_message",
            type=Optional[str],
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="model_response"),
    ]

    def text_response(self) -> Text:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.model_response()
        result = self.get_chat_result(output, stream, input_value, system_message)
        self.status = result
        return result

    def model_response(self) -> BaseLanguageModel:
        openai_api_key = self.openai_api_key
        temperature = self.temperature
        model_name = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs
        openai_api_base = self.openai_api_base or "https://api.openai.com/v1"

        if openai_api_key:
            api_key = SecretStr(openai_api_key)
        else:
            api_key = None

        output = ChatOpenAI(
            max_tokens=max_tokens or None,
            model_kwargs=model_kwargs,
            model=model_name,
            base_url=openai_api_base,
            api_key=api_key,
            temperature=temperature,
        )
        return output
