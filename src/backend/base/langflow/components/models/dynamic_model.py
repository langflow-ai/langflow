from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS
from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import OPENAI_MODEL_NAMES
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DropdownInput, SecretStrInput, SliderInput, MessageTextInput
from langflow.schema.dotdict import dotdict


class DynamicModelComponent(LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider. "
    icon = "brain-circuit"
    name = "LanguageModel"
    category = "models"

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            options=["OpenAI", "Anthropic"],
            value="OpenAI",
            info="Select the model provider",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=OPENAI_MODEL_NAMES,
            value="gpt-4-0125-preview",
            info="Select the model to use",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="openai_api_key",
            display_name="OpenAI API Key",
            info="Your OpenAI API key",
            required=False,
            show=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="anthropic_api_key",
            display_name="Anthropic API Key",
            info="Your Anthropic API key",
            required=False,
            show=False,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="input",
            display_name="Input",
            info="The input text to send to the model",
            required=True,
        ),
        MessageTextInput(
            name="system_message",
            display_name="System Message",
            info="A system message that helps set the behavior of the assistant",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Controls randomness in responses",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
    ]

    def build_model(self) -> LanguageModel:
        provider = self.provider
        model_name = self.model_name
        temperature = self.temperature
        stream = self.stream

        if provider == "OpenAI":
            if not self.openai_api_key:
                raise ValueError("OpenAI API key is required when using OpenAI provider")
            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                api_key=self.openai_api_key,
            )
        elif provider == "Anthropic":
            if not self.anthropic_api_key:
                raise ValueError("Anthropic API key is required when using Anthropic provider")
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                anthropic_api_key=self.anthropic_api_key,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "provider":
            if field_value == "OpenAI":
                build_config["model_name"]["options"] = OPENAI_MODEL_NAMES
                build_config["model_name"]["value"] = OPENAI_MODEL_NAMES[0]
                build_config["openai_api_key"]["show"] = True
                build_config["anthropic_api_key"]["show"] = False
            elif field_value == "Anthropic":
                build_config["model_name"]["options"] = ANTHROPIC_MODELS
                build_config["model_name"]["value"] = ANTHROPIC_MODELS[0]
                build_config["openai_api_key"]["show"] = False
                build_config["anthropic_api_key"]["show"] = True

        return build_config