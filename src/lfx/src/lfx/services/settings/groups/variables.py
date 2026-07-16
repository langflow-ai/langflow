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

    agentic_experience: bool = False
    """If set to True, Langflow enables the Langflow Assistant experience.

    This gates the assistant's code-generating endpoints under ``/api/v1/agentic``, the
    streamable-http MCP mount at ``/api/v1/agentic/mcp`` -- which serves the single Langflow
    MCP toolkit, ``lfx.mcp.server`` -- the seeding of the assistant's built-in flows, and the
    per-user agentic global variables. It does not start the deprecated ``langflow-agentic``
    stdio server: that server is no longer auto-configured and is kept only so previously
    configured entries keep working.
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
        # from the env; this default must track that field's, or the vars leak in with it off.
        if os.getenv("LANGFLOW_AGENTIC_EXPERIENCE", "false").lower() == "true":
            result.extend(AGENTIC_VARIABLES)

        return list(set(result))
