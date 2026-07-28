from pydantic import BaseModel, ValidationInfo, field_validator

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

    # Agentic Experience
    agentic_experience: bool = True
    """Enables the Langflow Assistant and its agentic MCP server (tools for flow/component
    operations, template search, and graph visualization). On by default — the Assistant is
    Langflow's entry-point experience; set LANGFLOW_AGENTIC_EXPERIENCE=false to opt out."""

    variables_to_get_from_environment: list[str] = VARIABLES_TO_GET_FROM_ENVIRONMENT
    """List of environment variables to get from the environment and store in the database."""

    # Developer API
    developer_api_enabled: bool = False
    """If set to True, Langflow will enable developer API endpoints for advanced debugging and introspection."""

    @field_validator("variables_to_get_from_environment", mode="before")
    @classmethod
    def set_variables_to_get_from_environment(cls, value, info: ValidationInfo):
        if isinstance(value, str):
            value = value.split(",")

        result = list(set(VARIABLES_TO_GET_FROM_ENVIRONMENT + value))

        if info.data.get("agentic_experience", True):
            result.extend(AGENTIC_VARIABLES)

        return list(set(result))
