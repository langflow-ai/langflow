from __future__ import annotations

from lfx.base.models.unified_models import (
    get_language_model_options,
    update_model_options_in_build_config,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.custom.custom_component.component import Component
from lfx.io import (
    BoolInput,
    DataFrameInput,
    DropdownInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    ModelInput,
    Output,
    SecretStrInput,
    StrInput,
    TableInput,
)
from lfx.schema.dataframe import DataFrame
from lfx.schema.table import EditMode

DEFAULT_OLLAMA_URL = "http://localhost:11434"


class SemanticFilter(Component):
    display_name = "SemanticFilter"
    description = "Reads each of the input rows and filter those matching provided predicate template"
    documentation: str = "github.com/IBM/agentics/"
    icon = "List"

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
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
        ),
        SecretStrInput(
            name="project_id",
            display_name="Project ID",
            info="Required Only for WatsonX",
            real_time_refresh=True,
            advanced=True,
        ),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        
        
        MessageTextInput(
            name="predicate_template",
            display_name="predicate_template",
            value="",
            advanced=False,
        ),
        IntInput(name="batch_size", display_name="Batch Size", value=10, advanced=True),

    ]

    outputs = [
        Output(name="states", display_name="Target DataFrame", method="semantic_filter", tool_mode=True),

    ]
    
    
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        """Dynamically update build config with user-filtered model options."""
        build_config = update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )

        # Show/hide provider-specific fields based on selected model
        # Get current model value - from field_value if model is being changed, otherwise from build_config
        current_model_value = field_value if field_name == "model" else build_config.get("model", {}).get("value")
        if isinstance(current_model_value, list) and len(current_model_value) > 0:
            selected_model = current_model_value[0]
            provider = selected_model.get("provider", "")

            # Show/hide watsonx fields
            is_watsonx = provider == "IBM WatsonX"
            build_config["base_url_ibm_watsonx"]["show"] = is_watsonx
            build_config["project_id"]["show"] = is_watsonx
            build_config["base_url_ibm_watsonx"]["required"] = is_watsonx
            build_config["project_id"]["required"] = is_watsonx

            # Show/hide Ollama fields
            is_ollama = provider == "Ollama"
            build_config["ollama_base_url"]["show"] = is_ollama

        return build_config

    def _create_llm(self, provider: str, model_name: str, api_key: str | None):
        """Create LLM instance based on provider."""
        from crewai import LLM

        if provider == "IBM WatsonX":
            return LLM(
                model="watsonx/" + model_name,
                base_url=getattr(self, "base_url_ibm_watsonx", IBM_WATSONX_URLS[0]),
                project_id=self.project_id,
                api_key=api_key,
                temperature=0,
                max_tokens=4000,
                max_input_tokens=100000,
            )

        if provider == "Google Generative AI":
            return LLM(model="gemini/" + model_name, api_key=api_key)

        if provider == "OpenAI":
            return LLM(model="openai/" + model_name, api_key=api_key)

        if provider == "Anthropic":
            return LLM(model="anthropic/" + model_name, api_key=api_key)

        if provider == "Ollama":
            ollama_url = getattr(self, "ollama_base_url", DEFAULT_OLLAMA_URL)
            return LLM(model="ollama/" + model_name, base_url=ollama_url)

        msg = (
            f"Unsupported provider: {provider}. Supported: IBM WatsonX, Google Generative AI, OpenAI, Anthropic, Ollama"
        )
        raise ValueError(msg)

    
    async def semantic_filter(self) -> DataFrame:
        """Process each row in df[column_name] with the language model asynchronously."""
        # Check if model is already an instance (for testing) or needs to be instantiated
        try:
            from agentics import AG
            from agentics.core.semantic_operators import sem_filter
        except ImportError as e:
            msg = "Agentics-py is not installed. Please install it with `uv pip install agentics-py`."
            raise ImportError(msg) from e

        # Extract model configuration
        model_selection = self.model[0]
        model_name = model_selection.get("name")
        provider = model_selection.get("provider")

        # Get API key from global variables
        from lfx.base.models.unified_models import get_api_key_for_provider

        api_key = get_api_key_for_provider(self.user_id, provider, self.api_key)

        if not api_key and provider != "Ollama":
            msg = f"{provider} API key is required. Please configure it globally."
            raise ValueError(msg)

        llm = self._create_llm(provider, model_name, api_key)


        source = AG.from_dataframe(DataFrame(self.source))
        output = await sem_filter(
            source,
            self.predicate_template,
            batch_size=self.batch_size,
            llm=llm
        )
        df = output.to_dataframe()
        return df.to_dict(orient="records")
