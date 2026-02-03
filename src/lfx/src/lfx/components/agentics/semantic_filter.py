"""SemanticFilter component for filtering DataFrame rows using LLM predicates."""

from __future__ import annotations

from lfx.base.models.unified_models import (
    get_api_key_for_provider,
    get_language_model_options,
    update_model_options_in_build_config,
)
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.components.agentics.constants import (
    DEFAULT_OLLAMA_URL,
    ERROR_AGENTICS_NOT_INSTALLED,
    ERROR_API_KEY_REQUIRED,
    PROVIDER_OLLAMA,
)
from lfx.components.agentics.helpers import (
    create_llm,
    update_provider_fields_visibility,
    validate_model_selection,
)
from lfx.custom.custom_component.component import Component
from lfx.io import (
    DataFrameInput,
    DropdownInput,
    IntInput,
    MessageInput,
    MessageTextInput,
    ModelInput,
    Output,
    SecretStrInput,
    StrInput,
)
from lfx.schema.dataframe import DataFrame


class SemanticFilter(Component):
    """Filters DataFrame rows based on a semantic predicate evaluated by an LLM."""

    display_name = "SemanticFilter"
    description = "Reads each of the input rows and filters those matching the provided predicate template"
    documentation: str = "github.com/IBM/agentics/"
    icon = "Agentics"

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
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
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
        MessageInput(
            name="ollama_base_url",
            display_name="Ollama API URL",
            info=f"Endpoint of the Ollama API (Ollama only). Defaults to {DEFAULT_OLLAMA_URL}",
            value=DEFAULT_OLLAMA_URL,
            show=False,
            real_time_refresh=True,
            load_from_db=True,
        ),
        DataFrameInput(
            name="source",
            display_name="Source DataFrame",
            info="Accepts JSON (list of dicts) or DataFrame.",
        ),
        MessageTextInput(
            name="predicate_template",
            display_name="Predicate Template",
            info="The predicate condition to filter rows by",
            value="",
        ),
        IntInput(
            name="batch_size",
            display_name="Batch Size",
            value=10,
            advanced=True,
        ),
    ]

    outputs = [
        Output(
            name="states",
            display_name="Target DataFrame",
            method="semantic_filter",
            tool_mode=True,
        ),
    ]

    def update_build_config(
        self,
        build_config: dict,
        field_value: str,
        field_name: str | None = None,
    ) -> dict:
        """Dynamically update build config with user-filtered model options."""
        build_config = update_model_options_in_build_config(
            component=self,
            build_config=build_config,
            cache_key_prefix="language_model_options",
            get_options_func=get_language_model_options,
            field_name=field_name,
            field_value=field_value,
        )
        return update_provider_fields_visibility(build_config, field_value, field_name)

    async def semantic_filter(self) -> DataFrame:
        """Filter DataFrame rows based on the predicate template."""
        try:
            from agentics import AG
            from agentics.core.semantic_operators import sem_filter
        except ImportError as e:
            raise ImportError(ERROR_AGENTICS_NOT_INSTALLED) from e

        model_name, provider = validate_model_selection(self.model)
        api_key = get_api_key_for_provider(self.user_id, provider, self.api_key)

        if not api_key and provider != PROVIDER_OLLAMA:
            raise ValueError(ERROR_API_KEY_REQUIRED.format(provider=provider))

        llm = create_llm(
            provider=provider,
            model_name=model_name,
            api_key=api_key,
            base_url_ibm_watsonx=getattr(self, "base_url_ibm_watsonx", None),
            project_id=getattr(self, "project_id", None),
            ollama_base_url=getattr(self, "ollama_base_url", None),
        )

        source = AG.from_dataframe(DataFrame(self.source))
        output = await sem_filter(
            source,
            self.predicate_template,
            batch_size=self.batch_size,
            llm=llm,
        )

        return output.to_dataframe().to_dict(orient="records")
