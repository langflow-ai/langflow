from typing import Optional

from langchain_groq import ChatGroq
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.groq_constants import MODEL_NAMES
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import BaseLanguageModel, Text
from langflow.template import Input, Output


class GroqModelComponent(LCModelComponent):
    display_name: str = "Groq"
    description: str = "Generate text using Groq."
    icon = "Groq"

    inputs = [
        Input(
            name="groq_api_key",
            field_type=str,
            display_name="Groq API Key",
            info="API key for the Groq API.",
            password=True,
        ),
        Input(
            name="groq_api_base",
            field_type=Optional[str],
            display_name="Groq API Base",
            advanced=True,
            info="Base URL path for API requests, leave blank if not using a proxy or service emulator.",
        ),
        Input(
            name="max_tokens",
            field_type=Optional[int],
            display_name="Max Output Tokens",
            advanced=True,
            info="The maximum number of tokens to generate.",
        ),
        Input(
            name="temperature",
            field_type=float,
            display_name="Temperature",
            info="Run inference with this temperature. Must be in the closed interval [0.0, 1.0].",
        ),
        Input(
            name="n",
            field_type=Optional[int],
            display_name="N",
            advanced=True,
            info="Number of chat completions to generate for each prompt. Note that the API may not return the full n completions if duplicates are generated.",
        ),
        Input(
            name="model_name",
            field_type=str,
            display_name="Model",
            info="The name of the model to use. Supported examples: gemini-pro",
            options=MODEL_NAMES,
        ),
        Input(name="input_value", field_type=str, display_name="Input", input_types=["Text", "Record", "Prompt"]),
        Input(name="stream", field_type=bool, display_name="Stream", advanced=True, info=STREAM_INFO_TEXT),
        Input(
            name="system_message",
            field_type=Optional[str],
            display_name="System Message",
            advanced=True,
            info="System message to pass to the model.",
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
        groq_api_key = self.groq_api_key
        model_name = self.model_name
        groq_api_base = self.groq_api_base or None
        max_tokens = self.max_tokens
        temperature = self.temperature
        n = self.n or 1
        stream = self.stream

        output = ChatGroq(
            model_name=model_name,
            max_tokens=max_tokens or None,  # type: ignore
            temperature=temperature,
            groq_api_base=groq_api_base,
            n=n,
            groq_api_key=SecretStr(groq_api_key),
            streaming=stream,
        )
        return output
