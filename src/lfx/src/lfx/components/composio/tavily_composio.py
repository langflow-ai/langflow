from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioTavilyAPIComponent(ComposioBaseComponent):
    component_id: str = "a40135bf-4a5a-4351-898d-754307137b6f"
    display_name: str = "Tavily"
    icon = "Tavily"
    documentation: str = "https://docs.composio.dev"
    app_name = "tavily"

    def set_default_tools(self):
        """Set the default tools for Tavily component."""
