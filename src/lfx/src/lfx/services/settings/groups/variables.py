import os

from pydantic import BaseModel, field_validator

from lfx.services.settings.constants import AGENTIC_VARIABLES, VARIABLES_TO_GET_FROM_ENVIRONMENT


class VariablesSettings(BaseModel):
    """Global variable store, environment-variable bridge, and experimental feature toggles."""

    variable_store: str = "db"
    """The store can be 'db' or 'kubernetes'."""

    fallback_to_env_var: bool = True
    """If set to True, Global Variables set in the UI will fallback to a environment variable
    with the same name in case Langflow fails to retrieve the variable value."""

    store_environment_variables: bool = True
    """Whether to store environment variables as Global Variables in the database."""

    variables_to_get_from_environment: list[str] = VARIABLES_TO_GET_FROM_ENVIRONMENT
    """List of environment variables to get from the environment and store in the database."""

    agentic_experience: bool = True
    """Whether the Langflow Assistant is available. On by default: it is the primary way into
    the product, so requiring opt-in would hide the main entry point behind an env var.

    Set it to False to turn the Assistant off for a deployment -- an operator who does not want
    LLM-authored component code running on their server. That withholds the assistant's
    code-generating endpoints under ``/api/v1/agentic`` (404), the ``run_assistant`` MCP tool,
    the seeding of the assistant's built-in flows, and the per-user agentic global variables.
    It does NOT withhold the rest of the MCP toolkit at ``/api/v1/agentic/mcp``, whose tools are
    REST calls the API already authorizes. Note this is not the control over in-process code
    execution -- that is ``allow_custom_components``, which applies to the Assistant and to
    hand-written custom components alike.
    """

    developer_api_enabled: bool = False
    """If set to True, Langflow will enable developer API endpoints for advanced debugging and introspection."""

    @field_validator("variables_to_get_from_environment", mode="before")
    @classmethod
    def set_variables_to_get_from_environment(cls, value):
        if isinstance(value, str):
            value = value.split(",")

        result = list(set(VARIABLES_TO_GET_FROM_ENVIRONMENT + value))

        # A field validator cannot read the sibling `agentic_experience`, so the gate is re-read
        # from the env; this default must track that field's, or the vars disagree with it.
        if os.getenv("LANGFLOW_AGENTIC_EXPERIENCE", "true").lower() == "true":
            result.extend(AGENTIC_VARIABLES)

        return list(set(result))
