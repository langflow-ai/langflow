from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSnowflakeAPIComponent(ComposioBaseComponent):
    component_id: str = "e7e760a7-b33f-4898-a41e-954dc121caa9"
    display_name: str = "Snowflake"
    icon = "Snowflake"
    documentation: str = "https://docs.composio.dev"
    app_name = "snowflake"

    def set_default_tools(self):
        """Set the default tools for Snowflake component."""
