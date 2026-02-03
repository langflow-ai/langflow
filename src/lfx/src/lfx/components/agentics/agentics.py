"""Agentics component for Map/Reduce style data transformations."""

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
    TRANSDUCTION_AMAP,
    TRANSDUCTION_GENERATE,
    TRANSDUCTION_TYPES,
)
from lfx.components.agentics.helpers import (
    create_llm,
    update_provider_fields_visibility,
    validate_model_selection,
)
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


class AgenticsComponent(Component):
    """Enables Map Reduce Style Agentic data transformations among dataframes."""

    display_name = "Agentics"
    description = "Enables Map Reduce Style Agentic data transformations among dataframes"
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
        DropdownInput(
            name="transduction_type",
            display_name="Transduction Type",
            options=TRANSDUCTION_TYPES,
            value=TRANSDUCTION_AMAP,
            required=True,
        ),
        MessageTextInput(
            name="atype_name",
            display_name="Generated Type",
            info="Provide a name for the generated target type",
            value="",
            required=True,
        ),
        TableInput(
            name="schema",
            display_name="Generated Fields",
            info="Define the structure and data types for the model's output.",
            required=True,
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "text",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "type",
                    "display_name": "Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": "Indicate the data type of the output field (e.g., str, int, float, bool, dict).",
                    "options": ["str", "int", "float", "bool", "dict"],
                    "default": "str",
                },
                {
                    "name": "multiple",
                    "display_name": "As List",
                    "type": "boolean",
                    "description": "Set to True if this output field should be a list of the specified type.",
                    "default": False,
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[
                {
                    "name": "text",
                    "description": "",
                    "type": "str",
                    "multiple": False,
                }
            ],
        ),
        MessageTextInput(
            name="instructions",
            display_name="Instructions",
            value="",
        ),
        BoolInput(
            name="merge_source",
            display_name="Merge Source States",
            value=True,
            advanced=True,
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
            method="transduce",
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

    async def transduce(self) -> DataFrame:
        """Execute transduction on the source DataFrame."""
        try:
            from agentics import AG
            from agentics.core.atype import create_pydantic_model
            from agentics.core.transducible_functions import generate_prototypical_instances
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

        schema_fields = [
            (
                field["name"],
                field["description"],
                field["type"] if not field["multiple"] else f"list[{field['type']}]",
                False,
            )
            for field in self.schema
        ]
        atype = create_pydantic_model(schema_fields, name=self.atype_name)

        source = AG.from_dataframe(DataFrame(self.source))

        if self.transduction_type == TRANSDUCTION_GENERATE:
            output_states = await generate_prototypical_instances(
                atype,
                n_instances=self.batch_size,
                llm=llm,
            )
            output = AG(states=output_states)
        else:
            target = AG(
                atype=atype,
                instructions=self.instructions,
                transduction_type=self.transduction_type,
                amap_batch_size=self.batch_size,
                llm=llm,
            )
            output = await (target << source)
            if self.merge_source and self.transduction_type == TRANSDUCTION_AMAP:
                output = source.merge_states(output)

        return output.to_dataframe().to_dict(orient="records")
