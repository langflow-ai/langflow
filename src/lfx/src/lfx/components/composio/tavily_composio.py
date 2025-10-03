from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioTavilyAPIComponent(ComposioBaseComponent):
    display_name: str = "Tavily"
    icon = "Tavily"
    documentation: str = "https://docs.composio.dev"
    app_name = "tavily"

    def set_default_tools(self):
        """Set the default tools for Tavily component."""
