from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioNotionAPIComponent(ComposioBaseComponent):
    component_id: str = "f082db2a-b834-4c90-9da1-41492aec8c78"
    display_name: str = "Notion"
    icon = "Notion"
    documentation: str = "https://docs.composio.dev"
    app_name = "notion"

    def set_default_tools(self):
        """Set the default tools for Notion component."""
