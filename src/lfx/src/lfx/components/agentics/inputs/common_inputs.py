"""Common input definitions for Agentics components."""

from __future__ import annotations

from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.components.agentics.constants import DEFAULT_OLLAMA_URL
from lfx.io import (
    DropdownInput,
    MessageInput,
    ModelInput,
    SecretStrInput,
    StrInput,
    TableInput,
)
from lfx.schema.table import EditMode

GENERATED_FIELDS_TABLE_SCHEMA = [
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
]

GENERATED_FIELDS_DEFAULT_VALUE = [
    {
        "name": "text",
        "description": "",
        "type": "str",
        "multiple": False,
    }
]


def get_model_provider_inputs() -> list:
    """Return the common model provider inputs."""
    return [
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider",
            real_time_refresh=True,
            required=True,
        ),
        get_api_key_input(),
        *get_watsonx_inputs(),
        get_ollama_url_input(),
    ]


def get_api_key_input() -> SecretStrInput:
    """Return the API key input."""
    return SecretStrInput(
        name="api_key",
        display_name="API Key",
        info="Model Provider API key",
        real_time_refresh=True,
        advanced=True,
    )


def get_watsonx_inputs() -> list:
    """Return IBM WatsonX-specific inputs."""
    return [
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="Watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="Watsonx Project ID",
            info="The project ID associated with the foundation model (IBM watsonx.ai only)",
            show=False,
            required=False,
        ),
    ]


def get_ollama_url_input() -> MessageInput:
    """Return the Ollama URL input."""
    return MessageInput(
        name="ollama_base_url",
        display_name="Ollama API URL",
        info=f"Endpoint of the Ollama API (Ollama only). Defaults to {DEFAULT_OLLAMA_URL}",
        value=DEFAULT_OLLAMA_URL,
        show=False,
        real_time_refresh=True,
        load_from_db=True,
    )


def get_generated_fields_input(
    name: str = "generated_fields",
    display_name: str = "Generated Fields",
    info: str = "Define the structure and data types for the generated output.",
) -> TableInput:
    """Return the generated fields table input."""
    return TableInput(
        name=name,
        display_name=display_name,
        info=info,
        required=True,
        table_schema=GENERATED_FIELDS_TABLE_SCHEMA,
        value=GENERATED_FIELDS_DEFAULT_VALUE,
    )
