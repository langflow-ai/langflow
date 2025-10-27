from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_ibm import ChatWatsonx, WatsonxEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from lfx.base.models.anthropic_constants import ANTHROPIC_MODELS
from lfx.base.models.google_generative_ai_constants import GOOGLE_GENERATIVE_AI_MODELS
from lfx.base.models.google_generative_ai_model import ChatGoogleGenerativeAIFixed
from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_CHAT_MODEL_NAMES, OPENAI_EMBEDDING_MODEL_NAMES
from lfx.base.models.unified_models import get_api_key_for_provider
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.io import DropdownInput, MessageTextInput, SecretStrInput, SliderInput
from lfx.schema.dotdict import dotdict
from lfx.template.field.base import Output


class ModelsProviderSetupComponent(LCModelComponent):
    """Example component showing how to setup and configure model providers with API keys."""

    display_name = "Models Provider Setup"
    description = "Configure and setup language models from different providers with API key management."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"
    priority = 100

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            options=["OpenAI", "Anthropic", "Google Generative AI", "Ollama", "IBM WatsonX"],
            value="OpenAI",
            info="Select the model provider",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_type",
            display_name="Model Type",
            options=["Language Model", "Embedding Model"],
            value="Language Model",
            info="Select whether to use a language model or embedding model",
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=OPENAI_CHAT_MODEL_NAMES,
            value=OPENAI_CHAT_MODEL_NAMES[0],
            info="Select the model to use",
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key (stored securely)",
            required=False,
            value="OPENAI_API_KEY",
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="Base URL for the API (for Ollama or custom endpoints)",
            advanced=True,
        ),
        MessageTextInput(
            name="project_id",
            display_name="Project ID",
            info="Project ID for IBM WatsonX",
            advanced=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Controls randomness: 0.0 = focused and deterministic, 1.0 = creative and varied",
            range_spec=RangeSpec(min=0, max=1, step=0.1),
        ),
        SliderInput(
            name="max_tokens",
            display_name="Max Tokens",
            value=1000,
            info="Maximum number of tokens to generate",
            range_spec=RangeSpec(min=1, max=4096, step=1),
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            display_name="Language Model",
            name="model_output",
            method="build_model",
        ),
    ]

    def build_model(self) -> LanguageModel:
        """Build and return the language or embedding model using the selected provider and API key."""
        provider = self.provider
        model_name = self.model_name
        model_type = self.model_type
        temperature = self.temperature

        # Get API key from user input or global variables
        api_key = get_api_key_for_provider(self.user_id, provider, self.api_key)

        # Validate API key (Ollama doesn't require one)
        if not api_key and provider != "Ollama":
            msg = (
                f"{provider} API key is required. "
                f"Please provide it in the component or configure it globally as "
                f"{provider.upper().replace(' ', '_')}_API_KEY."
            )
            raise ValueError(msg)

        # Build Language Models
        if model_type == "Language Model":
            if provider == "OpenAI":
                return ChatOpenAI(
                    model=model_name,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=self.max_tokens,
                )
            if provider == "Anthropic":
                return ChatAnthropic(
                    model=model_name,
                    api_key=api_key,
                    temperature=temperature,
                    max_tokens=self.max_tokens,
                )
            if provider == "Google Generative AI":
                return ChatGoogleGenerativeAIFixed(
                    model=model_name,
                    google_api_key=api_key,
                    temperature=temperature,
                    max_tokens=self.max_tokens,
                )
            if provider == "Ollama":
                kwargs = {"model": model_name, "temperature": temperature}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                return ChatOllama(**kwargs)
            if provider == "IBM WatsonX":
                kwargs = {
                    "model_id": model_name,
                    "apikey": api_key,
                    "url": self.base_url or "https://us-south.ml.cloud.ibm.com",
                }
                if self.project_id:
                    kwargs["project_id"] = self.project_id
                return ChatWatsonx(**kwargs)

        # Build Embedding Models
        elif model_type == "Embedding Model":
            if provider == "OpenAI":
                return OpenAIEmbeddings(
                    model=model_name,
                    api_key=api_key,
                )
            if provider == "Google Generative AI":
                return GoogleGenerativeAIEmbeddings(
                    model=model_name,
                    google_api_key=api_key,
                )
            if provider == "Ollama":
                kwargs = {"model": model_name}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                return OllamaEmbeddings(**kwargs)
            if provider == "IBM WatsonX":
                kwargs = {
                    "model_id": model_name,
                    "apikey": api_key,
                    "url": self.base_url or "https://us-south.ml.cloud.ibm.com",
                }
                if self.project_id:
                    kwargs["project_id"] = self.project_id
                return WatsonxEmbeddings(**kwargs)

        msg = f"Unsupported provider: {provider} with model type: {model_type}"
        raise ValueError(msg)

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        """Update the build configuration dynamically based on field changes."""
        # Get current model type
        model_type = build_config.get("model_type", {}).get("value", "Language Model")

        # Update model options and API key label based on selected provider and model type
        if field_name in {"provider", "model_type"}:
            provider = (
                field_value if field_name == "provider" else build_config.get("provider", {}).get("value", "OpenAI")
            )

            # Update model type if changed
            if field_name == "model_type":
                model_type = field_value

            # Configure based on provider and model type
            if provider == "OpenAI":
                if model_type == "Language Model":
                    build_config["model_name"]["options"] = OPENAI_CHAT_MODEL_NAMES
                    build_config["model_name"]["value"] = OPENAI_CHAT_MODEL_NAMES[0]
                else:  # Embedding Model
                    build_config["model_name"]["options"] = OPENAI_EMBEDDING_MODEL_NAMES
                    build_config["model_name"]["value"] = OPENAI_EMBEDDING_MODEL_NAMES[0]
                build_config["api_key"]["display_name"] = "OpenAI API Key"
                build_config["api_key"]["value"] = "OPENAI_API_KEY"
                build_config["api_key"]["required"] = True
                build_config["base_url"]["show"] = False
                build_config["project_id"]["show"] = False

            elif provider == "Anthropic":
                # Anthropic only supports language models
                build_config["model_name"]["options"] = ANTHROPIC_MODELS
                build_config["model_name"]["value"] = ANTHROPIC_MODELS[0]
                build_config["api_key"]["display_name"] = "Anthropic API Key"
                build_config["api_key"]["value"] = "ANTHROPIC_API_KEY"
                build_config["api_key"]["required"] = True
                build_config["base_url"]["show"] = False
                build_config["project_id"]["show"] = False
                build_config["model_type"]["options"] = ["Language Model"]
                build_config["model_type"]["value"] = "Language Model"

            elif provider == "Google Generative AI":
                if model_type == "Language Model":
                    build_config["model_name"]["options"] = GOOGLE_GENERATIVE_AI_MODELS
                    build_config["model_name"]["value"] = GOOGLE_GENERATIVE_AI_MODELS[0]
                else:  # Embedding Model
                    build_config["model_name"]["options"] = ["models/embedding-001", "models/text-embedding-004"]
                    build_config["model_name"]["value"] = "models/embedding-001"
                build_config["api_key"]["display_name"] = "Google API Key"
                build_config["api_key"]["value"] = "GOOGLE_API_KEY"
                build_config["api_key"]["required"] = True
                build_config["base_url"]["show"] = False
                build_config["project_id"]["show"] = False

            elif provider == "Ollama":
                # Ollama - local models, no API key needed
                if model_type == "Language Model":
                    build_config["model_name"]["options"] = ["llama3.2", "llama3.1", "mistral", "codellama", "phi3"]
                    build_config["model_name"]["value"] = "llama3.2"
                else:  # Embedding Model
                    build_config["model_name"]["options"] = ["nomic-embed-text", "mxbai-embed-large", "all-minilm"]
                    build_config["model_name"]["value"] = "nomic-embed-text"
                build_config["api_key"]["display_name"] = "API Key (Not Required)"
                build_config["api_key"]["required"] = False
                build_config["api_key"]["show"] = False
                build_config["base_url"]["show"] = True
                build_config["base_url"]["value"] = "http://localhost:11434"
                build_config["project_id"]["show"] = False

            elif provider == "IBM WatsonX":
                # WatsonX models
                if model_type == "Language Model":
                    build_config["model_name"]["options"] = [
                        "ibm/granite-13b-chat-v2",
                        "meta-llama/llama-3-70b-instruct",
                        "mistralai/mistral-large",
                    ]
                    build_config["model_name"]["value"] = "ibm/granite-13b-chat-v2"
                else:  # Embedding Model
                    build_config["model_name"]["options"] = [
                        "ibm/slate-125m-english-rtrvr",
                        "sentence-transformers/all-minilm-l12-v2",
                    ]
                    build_config["model_name"]["value"] = "ibm/slate-125m-english-rtrvr"
                build_config["api_key"]["display_name"] = "IBM WatsonX API Key"
                build_config["api_key"]["value"] = "WATSONX_APIKEY"
                build_config["api_key"]["required"] = True
                build_config["base_url"]["show"] = True
                build_config["base_url"]["display_name"] = "WatsonX URL"
                build_config["base_url"]["value"] = "https://us-south.ml.cloud.ibm.com"
                build_config["project_id"]["show"] = True
                build_config["project_id"]["display_name"] = "Project ID"

        return build_config
