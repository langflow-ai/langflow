from lfx.base.models.model import LCModelComponent
from lfx.base.models.unified_models import (
    get_llm,
    handle_model_input_update,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.field_typing.constants import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, StrInput
from lfx.io import IntInput, MessageInput, ModelInput, MultilineInput, SecretStrInput, SliderInput

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class LanguageModelComponent(LCModelComponent):
    display_name = "Language Model"
    description = "Runs a language model given a specified provider."
    documentation: str = "https://docs.langflow.org/components-models"
    icon = "brain-circuit"
    category = "models"

    inputs = [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
            required=False,
            show=True,
            real_time_refresh=True,
            advanced=True,
        ),
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            combobox=True,
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
            info="The project ID associated with the foundation model (IBM watsonx.ai only)",
            show=False,
            required=False,
        ),
        StrInput(
            name="ollama_base_url",
            display_name="Ollama API URL",
            info=f"Endpoint of the Ollama API (Ollama only). Defaults to {DEFAULT_OLLAMA_URL}",
            value=DEFAULT_OLLAMA_URL,
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            info="Your Azure endpoint, including the resource (Azure OpenAI only). "
            "Example: https://example-resource.openai.azure.com/",
            show=False,
            required=False,
        ),
        StrInput(
            name="azure_deployment",
            display_name="Deployment Name",
            info="Your Azure deployment name, as defined in the Azure Portal (Azure OpenAI only).",
            show=False,
            required=False,
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
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate. Field name varies by provider.",
            advanced=True,
            range_spec=RangeSpec(min=1, max=128000, step=1, step_type="int"),
        ),
    ]

    def build_model(self) -> LanguageModel:
        model = get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=self.api_key,
            temperature=self.temperature,
            stream=self.stream,
            max_tokens=getattr(self, "max_tokens", None),
            watsonx_url=getattr(self, "base_url_ibm_watsonx", None),
            watsonx_project_id=getattr(self, "project_id", None),
            ollama_base_url=getattr(self, "ollama_base_url", None),
            azure_endpoint=getattr(self, "azure_endpoint", None),
            azure_deployment=getattr(self, "azure_deployment", None),
        )
        # Stash the built model so _get_exception_message can report the exact
        # endpoint/deployment/api_version that were sent if invoke fails.
        self._built_model = model
        return model

    def _get_exception_message(self, e: Exception):
        """Add Azure-specific context to invoke-time errors.

        The lfx logger defaults to ERROR level, so debug logs about the Azure
        request are usually suppressed. A 404 ("Resource not found") from Azure
        means the deployment path doesn't exist at the endpoint, so surface the
        exact values that were sent directly in the (always-visible) error.
        """
        msg = str(e)
        built = getattr(self, "_built_model", None)
        if ("404" in msg or "resource not found" in msg.lower()) and type(built).__name__ == "AzureChatOpenAI":
            endpoint = getattr(built, "azure_endpoint", None)
            deployment = getattr(built, "deployment_name", None)
            api_version = getattr(built, "openai_api_version", None)
            return (
                f"Azure OpenAI returned 404 (Resource not found).\n"
                f"Request used: endpoint='{endpoint}', deployment='{deployment}', api_version='{api_version}'.\n"
                "Verify a deployment with that exact name exists at that endpoint in the Azure Portal "
                "(deployment names are user-defined and case-sensitive). Original error: "
                f"{msg}"
            )
        return msg

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        return handle_model_input_update(self, build_config, field_value, field_name)
