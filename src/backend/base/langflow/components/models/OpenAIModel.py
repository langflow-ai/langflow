import operator
from functools import reduce

from langflow.field_typing.range_spec import RangeSpec
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.field_typing import LanguageModel
from langflow.inputs import (
    BoolInput,
    DictInput,
    DropdownInput,
    FloatInput,
    IntInput,
    SecretStrInput,
    StrInput,
)


class OpenAIModelComponent(LCModelComponent):
    display_name = "OpenAI"
    description = "Generates text using OpenAI LLMs."
    icon = "OpenAI"
    name = "OpenAIModel"

    inputs = LCModelComponent._base_inputs + [
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(name="model_kwargs", display_name="Model Kwargs", advanced=True),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DictInput(
            name="output_schema",
            is_list=True,
            display_name="Schema",
            advanced=True,
            info="The schema for the Output of the model. You must pass the word JSON in the prompt. If left blank, JSON mode will be disabled.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=OPENAI_MODEL_NAMES,
            value=OPENAI_MODEL_NAMES[0],
        ),
        StrInput(
            name="openai_api_base",
            display_name="OpenAI API Base",
            advanced=True,
            info="The base URL of the OpenAI API. Defaults to https://api.openai.com/v1. You can change this to use other APIs like JinaChat, LocalAI and Prem.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="The OpenAI API Key to use for the OpenAI model.",
            advanced=False,
            value="OPENAI_API_KEY",
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        # self.output_schema is a list of dictionaries
        # let's convert it to a dictionary
        output_schema_dict: dict[str, str] = reduce(operator.ior, self.output_schema or {}, {})
        openai_api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs or {}
        openai_api_base = self.openai_api_base or "https://api.openai.com/v1"
        json_mode = bool(output_schema_dict) or self.json_mode
        seed = self.seed

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
            temperature=temperature if temperature is not None else 0.1,
            seed=seed,
        )
        if json_mode:
            if output_schema_dict:
                output = output.with_structured_output(schema=output_schema_dict, method="json_mode")  # type: ignore
            else:
                output = output.bind(response_format={"type": "json_object"})  # type: ignore

        return output  # type: ignore

    def _get_exception_message(self, e: Exception):
        """
        Get a message from an OpenAI exception.

        Args:
            exception (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """

        try:
            from openai import BadRequestError
        except ImportError:
            return
        if isinstance(e, BadRequestError):
            message = e.body.get("message")  # type: ignore
            if message:
                return message
        return
