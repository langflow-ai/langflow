from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSerpAPIComponent(ComposioBaseComponent):
    component_id: str = "b56a7c89-1e4f-41d2-9e87-e8541d304d94"
    display_name: str = "SerpAPI"
    icon = "SerpSearchComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "serpapi"

    def set_default_tools(self):
        """Set the default tools for SerpAPI component."""
