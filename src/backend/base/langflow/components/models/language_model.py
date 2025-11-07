import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI, AzureChatOpenAI

from langflow.base.models.anthropic_constants import ANTHROPIC_MODELS
from langflow.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from langflow.base.models.model import LCModelComponent
from langflow.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES, OPENAI_REASONING_MODEL_NAMES
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.inputs.inputs import BoolInput, MessageTextInput
from langflow.io import DropdownInput, MessageInput, MultilineInput, SecretStrInput, SliderInput
from langflow.schema.dotdict import dotdict


class LanguageModelComponent(LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 0  # Set priority to 0 to make it appear first

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            options=["OpenAI", "Azure OpenAI", "Anthropic", "Google"],
            value="OpenAI",
            info="Select the model provider",
            real_time_refresh=True,
            options_metadata=[{"icon": "OpenAI"}, {"icon": "Azure"}, {"icon": "Anthropic"}, {"icon": "GoogleGenerativeAI"}],
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            options=OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES,
            value=OPENAI_CHAT_MODEL_NAMES[0],
            info="Select the model to use",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="OpenAI API Key",
            info="Model Provider API key",
            required=False,
            show=True,
            real_time_refresh=True,
            value=os.getenv("OPENAI_API_KEY", ""),
        ),
        MessageTextInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            info="Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
            show=False,
            real_time_refresh=True,
            value=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        ),
        MessageTextInput(
            name="azure_deployment",
            display_name="Deployment Name",
            info="The name of your Azure OpenAI deployment",
            show=False,
            real_time_refresh=True,
            value=os.getenv("AZURE_DEPLOYMENT_NAME", ""),
        ),
        DropdownInput(
            name="api_version",
            display_name="API Version",
            options=["2024-06-01", "2024-07-01-preview", "2024-08-01-preview", "2024-09-01-preview"],
            value=os.getenv("AZURE_API_VERSION", "2024-06-01"),
            show=False,
            real_time_refresh=True,
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
        BoolInput(
            name="stream",
            display_name="Stream",
            info="Whether to stream the response",
            value=False,
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
            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                msg = "OpenAI API key is required when using OpenAI provider"
                raise ValueError(msg)

            if model_name in OPENAI_REASONING_MODEL_NAMES:
                # reasoning models do not support temperature (yet)
                temperature = None

            return ChatOpenAI(
                model_name=model_name,
                temperature=temperature,
                streaming=stream,
                openai_api_key=api_key,
            )
        if provider == "Azure OpenAI":
            api_key = self.api_key or os.getenv("AZURE_OPENAI_API_KEY")
            azure_endpoint = self.azure_endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_deployment = self.azure_deployment or os.getenv("AZURE_DEPLOYMENT_NAME")
            api_version = self.api_version or os.getenv("AZURE_API_VERSION", "2024-06-01")
            
            if not api_key:
                msg = "Azure OpenAI API key is required when using Azure OpenAI provider"
                raise ValueError(msg)
            if not azure_endpoint:
                msg = "Azure endpoint is required when using Azure OpenAI provider"
                raise ValueError(msg)
            if not azure_deployment:
                msg = "Azure deployment name is required when using Azure OpenAI provider"
                raise ValueError(msg)

            return AzureChatOpenAI(
                azure_endpoint=azure_endpoint,
                azure_deployment=azure_deployment,
                api_version=api_version,
                api_key=api_key,
                temperature=temperature,
                streaming=stream,
            )
        if provider == "Anthropic":
            api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                msg = "Anthropic API key is required when using Anthropic provider"
                raise ValueError(msg)
            return ChatAnthropic(
                model=model_name,
                temperature=temperature,
                streaming=stream,
                anthropic_api_key=api_key,
            )
        if provider == "Google":
            # Allow both API key and service account (managed identity) authentication
            if self.api_key:
                # Use API Key authentication (for local or quick setup)
                return ChatGoogleGenerativeAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=stream,
                    google_api_key=self.api_key,
                )
            else:
                # Check for API key in environment
                google_api_key = os.getenv("GOOGLE_API_KEY")
                if google_api_key:
                    return ChatGoogleGenerativeAI(
                        model=model_name,
                        temperature=temperature,
                        streaming=stream,
                        google_api_key=google_api_key,
                    )
                # Use default Google credentials (service account or managed identity)
                # This will automatically pick up credentials from environment or GCP runtime
                return ChatGoogleGenerativeAI(
                    model=model_name,
                    temperature=temperature,
                    streaming=stream,
                )

        msg = f"Unknown provider: {provider}"
        raise ValueError(msg)

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        if field_name == "provider":
            # Hide Azure-specific fields for all providers first
            build_config["azure_endpoint"]["show"] = False
            build_config["azure_deployment"]["show"] = False
            build_config["api_version"]["show"] = False
            build_config["model_name"]["show"] = True

            if field_value == "OpenAI":
                build_config["model_name"]["options"] = OPENAI_CHAT_MODEL_NAMES + OPENAI_REASONING_MODEL_NAMES
                build_config["model_name"]["value"] = OPENAI_CHAT_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["value"] = os.getenv("OPENAI_API_KEY", "")
            elif field_value == "Azure OpenAI":
                # Show Azure-specific fields
                build_config["azure_endpoint"]["show"] = True
                build_config["azure_deployment"]["show"] = True
                build_config["api_version"]["show"] = True
                build_config["model_name"]["show"] = False  # Azure uses deployment name instead
                build_config["api_key"]["display_name"] = "Azure OpenAI API Key"
                # Prefill Azure fields from environment variables
                build_config["api_key"]["value"] = os.getenv("AZURE_OPENAI_API_KEY", "")
                build_config["azure_endpoint"]["value"] = os.getenv("AZURE_OPENAI_ENDPOINT", "")
                build_config["azure_deployment"]["value"] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1")
                build_config["api_version"]["value"] = os.getenv("AZURE_API_VERSION", "2024-06-01")
            elif field_value == "Anthropic":
                build_config["model_name"]["options"] = ANTHROPIC_MODELS
                build_config["model_name"]["value"] = ANTHROPIC_MODELS[0]
                build_config["api_key"]["display_name"] = "Anthropic API Key"
                build_config["api_key"]["value"] = os.getenv("ANTHROPIC_API_KEY", "")
            elif field_value == "Google":
                build_config["model_name"]["options"] = GOOGLE_GENERATIVE_AI_MODELS
                # Prefill Google Model from environment variable if available, otherwise use default
                google_model = os.getenv("GOOGLE_GENAI_MODEL", "")
                build_config["model_name"]["value"] = google_model if google_model else GOOGLE_GENERATIVE_AI_MODELS[0]
                build_config["api_key"]["display_name"] = "Google API Key"
                build_config["api_key"]["value"] = os.getenv("GOOGLE_API_KEY", "")
        elif field_name == "model_name" and field_value.startswith("o1") and self.provider == "OpenAI":
            # Hide system_message for o1 models - currently unsupported
            if "system_message" in build_config:
                build_config["system_message"]["show"] = False
        elif field_name == "model_name" and not field_value.startswith("o1") and "system_message" in build_config:
            build_config["system_message"]["show"] = True
        return build_config
