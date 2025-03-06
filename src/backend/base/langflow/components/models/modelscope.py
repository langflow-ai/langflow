import operator
from functools import reduce
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs import BoolInput, DictInput, DropdownInput, FloatInput, IntInput, SecretStrInput, StrInput
from langflow.inputs.inputs import HandleInput

MODELSCOPE_MODEL_NAMES = [
    "Qwen/Qwen2.5-32B-Instruct",
    "LLM-Research/Llama-3.3-70B-Instruct",
    "Qwen/QVQ-72B-Preview",
    "Qwen/QwQ-32B-Preview",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Qwen/Qwen2.5-Coder-14B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "custom",
]


class ModelScopeModelComponent(LCModelComponent):
    display_name = "ModelScope"
    description = "Generate text using ModelScope Inference APIs"
    icon = "ModelScope"
    name = "ModelScopeModel"
    inputs = [
        *LCModelComponent._base_inputs,
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
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
            info="The schema for the Output of the model. "
            "You must pass the word JSON in the prompt. "
            "If left blank, JSON mode will be disabled. [DEPRECATED]",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=MODELSCOPE_MODEL_NAMES,
            value=MODELSCOPE_MODEL_NAMES[0],
            required=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="custom_model",
            display_name="Custom Model Name",
            info="Enter a custom model name from ModelScope",
            value="",
            show=False,
            required=True,
        ),
        StrInput(
            name="openai_api_base",
            display_name="ModelScope Base URL",
            advanced=True,
            info="The base URL of the ModelScope. "
            "Defaults to https://api-inference.modelscope.cn/v1. "
            "You can change this to use other APIs like JinaChat, LocalAI and Prem.",
            required=True,
            value="https://api-inference.modelscope.cn/v1",
        ),
        SecretStrInput(
            name="api_key",
            display_name="ModelScope 访问令牌",
            info="在 (ModelScope 首页 -> 访问令牌) 获取你的令牌然后填入",
            advanced=False,
            value="OPENAI_API_KEY",
            required=True,
        ),
        FloatInput(name="temperature", display_name="Temperature", value=0.1),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        HandleInput(
            name="output_parser",
            display_name="Output Parser",
            info="The parser to use to parse the output of the model",
            advanced=True,
            input_types=["OutputParser"],
        ),
    ]

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        # self.output_schema is a list of dictionaries
        # let's convert it to a dictionary
        output_schema_dict: dict[str, str] = reduce(operator.ior, self.output_schema or {}, {})
        openai_api_key = self.api_key
        temperature = self.temperature
        model_name: str = self.custom_model if self.model_name == "custom" else self.model_name
        max_tokens = self.max_tokens
        model_kwargs = self.model_kwargs or {}
        openai_api_base = self.openai_api_base or "https://api-inference.modelscope.cn/v1"
        json_mode = bool(output_schema_dict) or self.json_mode
        seed = self.seed
        api_key = SecretStr(openai_api_key).get_secret_value() if openai_api_key else None
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
                output = output.with_structured_output(schema=output_schema_dict, method="json_mode")
            else:
                output = output.bind(response_format={"type": "json_object"})
        return output

    def _get_exception_message(self, e: Exception):
        """Get a message from an OpenAI exception.

        Args:
            e (Exception): The exception to get the message from.

        Returns:
            str: The message from the exception.
        """
        try:
            from openai import BadRequestError
        except ImportError:
            return None
        if isinstance(e, BadRequestError):
            message = e.body.get("message")
            if message:
                return message
        return None

    async def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Update build configuration based on field updates."""
        try:
            if field_name is None or field_name == "model_name":
                # If model_name is custom, show custom model field
                if field_value == "custom":
                    build_config["custom_model"]["show"] = True
                    build_config["custom_model"]["required"] = True
                else:
                    build_config["custom_model"]["show"] = False
                    build_config["custom_model"]["value"] = ""

        except (KeyError, AttributeError) as e:
            self.log(f"Error updating build config: {e!s}")
        return build_config
