from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioConfluenceAPIComponent(ComposioBaseComponent):
    display_name: str = "Confluence"
    icon = "Confluence"
    documentation: str = "https://docs.composio.dev"
    app_name = "confluence"

    def set_default_tools(self):
        """Set the default tools for Confluence component."""
