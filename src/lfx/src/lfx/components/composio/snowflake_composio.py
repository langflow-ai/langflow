from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSnowflakeAPIComponent(ComposioBaseComponent):
    display_name: str = "Snowflake"
    icon = "Snowflake"
    documentation: str = "https://docs.composio.dev"
    app_name = "snowflake"

    def set_default_tools(self):
        """Set the default tools for Snowflake component."""
