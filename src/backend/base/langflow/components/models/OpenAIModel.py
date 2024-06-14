from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.constants import STREAM_INFO_TEXT
from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import MODEL_NAMES
from langflow.field_typing import BaseLanguageModel, Text
from langflow.inputs import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput
from langflow.template import Output



class OpenAIModelComponent(LCModelComponent):
    display_name = "OpenAI"
    description = "Generates text using OpenAI LLMs."
    icon = "OpenAI"

    inputs = [
        StrInput(name="input_value", display_name="Input", input_types=["Text", "Data", "Prompt"]),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        DropdownInput(
            name="model_name", display_name="Model Name", advanced=False, options=MODEL_NAMES, value=MODEL_NAMES[0]
        ),
        StrInput(
            name="openai_api_base",
            display_name="OpenAI API Base",
            advanced=True,
            info="The base URL of the OpenAI API. Defaults to https://api.openai.com/v1. You can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="The OpenAI API Key to use for the OpenAI model.",
            advanced=False,
            value="OPENAI_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        BoolInput(name="stream", display_name="Stream", info=STREAM_INFO_TEXT, advanced=True),
        StrInput(
            name="system_message",
            display_name="System Message",
            info="System message to pass to the model.",
            advanced=True,
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            info="Enable JSON mode for the model output.",
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]
    outputs = [
        Output(display_name="Text", name="text_output", method="text_response"),
        Output(display_name="Language Model", name="model_output", method="build_model"),
    ]

    def text_response(self) -> Text:
        input_value = self.input_value
        stream = self.stream
        system_message = self.system_message
        output = self.build_model()
        result = self.get_chat_result(output, stream, input_value, system_message)
        self.status = result
        return result

    def build_model(self) -> BaseLanguageModel:
        openai_api_key = self.openai_api_key
        temperature = self.temperature
        model_name = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs
        openai_api_base = self.openai_api_base or "https://api.openai.com/v1"
        json_mode = self.json_mode
        seed = self.seed
        if openai_api_key:
            api_key = SecretStr(openai_api_key)
        else:
            api_key = None
        response_format = None
        if json_mode:
            response_format = {"type": "json_object"}
        output = ChatOpenAI(
            max_tokens=max_tokens or None,
            model_kwargs=model_kwargs or {},
            model=model_name or None,
            base_url=openai_api_base,
            api_key=api_key,
            temperature=temperature or 0.1,
            response_format=response_format,
            seed=seed,
        )

        return output
