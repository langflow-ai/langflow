from typing import Any

from langchain_openai import AzureChatOpenAI, ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.base.models.openai_constants import OPENAI_MODELS_DETAILED
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DictInput, MessageTextInput
from lfx.io import DropdownInput, IntInput, SecretStrInput, SliderInput

AZURE_OPENAI_API_VERSIONS = [
    "2025-04-01-preview",
    "2025-03-01-preview",
    "2025-02-01-preview",
    "2025-01-01-preview",
    "2024-12-01-preview",
    "2024-10-01-preview",
    "2024-09-01-preview",
    "2024-08-01-preview",
    "2024-07-01-preview",
    "2024-06-01",
    "2024-03-01-preview",
    "2024-02-15-preview",
    "2023-12-01-preview",
    "2023-05-15",
]

REASONING_MODEL_NAMES = {m["name"] for m in OPENAI_MODELS_DETAILED if m.get("reasoning")}

MODEL_TO_DEPLOYMENT: dict[str, str] = {}
AZURE_MODEL_NAMES = ["gpt-5.1", "gpt-5-mini", "gpt-4.1", "gpt-4.1-mini"]


class AzureChatOpenAIComponent(LCModelComponent):
    display_name: str = "Azure OpenAI"
    description: str = "Generate text using Azure OpenAI LLMs."
    documentation: str = "https://python.langchain.com/docs/integrations/llms/azure_openai"
    beta = False
    icon = "Azure"
    name = "AzureOpenAIModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        MessageTextInput(
            name="azure_endpoint",
            display_name="Azure Endpoint",
            info="Your Azure endpoint, including the resource. Example: `https://example-resource.azure.openai.com/`",
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=AZURE_MODEL_NAMES,
            value=AZURE_MODEL_NAMES[0],
            combobox=True,
            required=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="azure_deployment",
            display_name="Deployment Name",
            info=(
                "The Azure deployment name to use. Auto-populated from model selection; "
                "override for custom deployments."
            ),
            required=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
        ),
        BoolInput(
            name="use_legacy_api",
            display_name="Use Legacy API",
            info="Use the legacy versioned API instead of the V1 Foundry API.",
            value=False,
            advanced=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="api_version",
            display_name="API Version",
            options=AZURE_OPENAI_API_VERSIONS,
            value=AZURE_OPENAI_API_VERSIONS[0],
            advanced=False,
            show=False,
        ),
        DropdownInput(
            name="reasoning_effort",
            display_name="Reasoning Effort",
            info="Controls reasoning depth. Higher values use more tokens but may produce better results.",
            options=["none", "minimal", "low", "medium", "high"],
            value="medium",
            advanced=False,
            show=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            info="Controls randomness. Lower values are more deterministic, higher values are more creative.",
            advanced=True,
            show=False,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            show=False,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
    ]

    def update_build_config(self, build_config: dict, field_value: Any, field_name: str | None = None) -> dict:
        """Toggle UI field visibility based on the changed field.

        Handles two field triggers:
        - ``use_legacy_api``: shows/hides the ``api_version`` dropdown.
        - ``model_name``: toggles reasoning-specific vs standard parameters
          and auto-populates the deployment name.
        """
        if field_name == "use_legacy_api":
            self._apply_legacy_api_visibility(build_config, is_legacy=bool(field_value))

        if field_name == "model_name":
            model = str(field_value) if field_value else ""
            is_reasoning = self._is_reasoning_model(model)
            self._apply_reasoning_visibility(build_config, is_reasoning=is_reasoning)
            if "azure_deployment" in build_config and isinstance(build_config["azure_deployment"], dict):
                build_config["azure_deployment"]["value"] = MODEL_TO_DEPLOYMENT.get(model, model)

        return build_config

    def _is_reasoning_model(self, model_name: str) -> bool:
        """Check whether *model_name* is a reasoning model.

        Performs a case-insensitive substring match against the known
        reasoning model names from ``OPENAI_MODELS_DETAILED``.
        """
        name = model_name.lower()
        return any(model in name for model in REASONING_MODEL_NAMES)

    def _resolve_deployment_name(self) -> str:
        """Return the Azure deployment name.

        Uses azure_deployment as the primary source. Falls back to mapping
        the model name if deployment is not set.
        """
        return self.azure_deployment or MODEL_TO_DEPLOYMENT.get(self.model_name, self.model_name)

    def _apply_legacy_api_visibility(self, build_config: dict, *, is_legacy: bool) -> None:
        """Show the ``api_version`` field only when the legacy API is selected."""
        if "api_version" in build_config and isinstance(build_config["api_version"], dict):
            build_config["api_version"]["show"] = is_legacy

    def _apply_reasoning_visibility(self, build_config: dict, *, is_reasoning: bool) -> None:
        """Toggle parameter visibility based on whether the model supports reasoning.

        Reasoning models expose ``reasoning_effort`` and hide ``temperature``
        and ``seed``; standard models do the inverse.
        """
        if "temperature" in build_config and isinstance(build_config["temperature"], dict):
            build_config["temperature"]["show"] = not is_reasoning
        if "seed" in build_config and isinstance(build_config["seed"], dict):
            build_config["seed"]["show"] = not is_reasoning
        if "reasoning_effort" in build_config and isinstance(build_config["reasoning_effort"], dict):
            build_config["reasoning_effort"]["show"] = is_reasoning

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        """Build and return a configured language model instance.

        Routes to the V1 Foundry API (``ChatOpenAI``) or the legacy versioned
        API (``AzureChatOpenAI``) depending on ``use_legacy_api``.
        """
        api_key_value = self._resolve_api_key()
        model_kwargs = self._prepare_model_kwargs()
        is_reasoning = self._is_reasoning_model(self.model_name or "")

        if self.use_legacy_api:
            return self._build_legacy_model(api_key_value, model_kwargs, is_reasoning=is_reasoning)
        return self._build_v1_model(api_key_value, model_kwargs, is_reasoning=is_reasoning)

    def _resolve_api_key(self) -> str | None:
        """Unwrap the API key from a ``SecretStr`` or return it as a plain string."""
        if not self.api_key:
            return None
        if isinstance(self.api_key, SecretStr):
            return self.api_key.get_secret_value()
        return str(self.api_key)

    def _prepare_model_kwargs(self) -> dict:
        """Return a sanitised copy of ``model_kwargs``.

        Strips ``api_key`` to prevent it from being passed twice to the
        underlying LangChain constructor.
        """
        model_kwargs = dict(self.model_kwargs) if self.model_kwargs else {}
        model_kwargs.pop("api_key", None)
        return model_kwargs

    def _build_v1_model(self, api_key: str | None, model_kwargs: dict, *, is_reasoning: bool) -> LanguageModel:
        """Construct a ``ChatOpenAI`` instance targeting the V1 Foundry API.

        Reasoning models receive ``reasoning_effort`` in *model_kwargs* and
        ``max_completion_tokens`` instead of ``max_tokens``.
        """
        base_url = self.azure_endpoint.rstrip("/") + "/openai/v1"
        if is_reasoning:
            model_kwargs = {**model_kwargs, "reasoning_effort": self.reasoning_effort}

        parameters: dict[str, Any] = {
            "model": self._resolve_deployment_name(),
            "api_key": api_key,
            "base_url": base_url,
            "streaming": self.stream,
            "model_kwargs": model_kwargs,
        }

        if is_reasoning:
            if self.max_tokens:
                parameters["max_completion_tokens"] = self.max_tokens
        else:
            parameters["temperature"] = self.temperature if self.temperature is not None else 0.7
            if self.seed:
                parameters["seed"] = self.seed
            if self.max_tokens:
                parameters["max_tokens"] = self.max_tokens

        try:
            return ChatOpenAI(**parameters)
        except Exception as e:
            msg = f"Could not connect to Azure OpenAI V1 API: {e}"
            raise ValueError(msg) from e

    def _build_legacy_model(self, api_key: str | None, model_kwargs: dict, *, is_reasoning: bool) -> LanguageModel:
        """Construct an ``AzureChatOpenAI`` instance using the legacy versioned API.

        Reasoning models receive ``reasoning_effort`` in *model_kwargs* and
        ``max_completion_tokens`` instead of ``max_tokens``.
        """
        if is_reasoning:
            model_kwargs = {**model_kwargs, "reasoning_effort": self.reasoning_effort}

        parameters: dict[str, Any] = {
            "azure_endpoint": self.azure_endpoint,
            "azure_deployment": self._resolve_deployment_name(),
            "api_version": self.api_version,
            "api_key": api_key,
            "streaming": self.stream,
            "model_kwargs": model_kwargs,
        }

        if is_reasoning:
            if self.max_tokens:
                parameters["max_completion_tokens"] = self.max_tokens
        else:
            parameters["temperature"] = self.temperature if self.temperature is not None else 0.7
            if self.seed:
                parameters["seed"] = self.seed
            if self.max_tokens:
                parameters["max_tokens"] = self.max_tokens

        try:
            return AzureChatOpenAI(**parameters)
        except Exception as e:
            msg = f"Could not connect to Azure OpenAI API: {e}"
            raise ValueError(msg) from e
