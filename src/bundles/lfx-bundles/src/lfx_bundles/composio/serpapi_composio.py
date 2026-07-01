from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSerpAPIComponent(ComposioBaseComponent):
    display_name: str = "SerpAPI"
    icon = "SerpSearchComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "serpapi"

    def set_default_tools(self):
        """Set the default tools for SerpAPI component."""
