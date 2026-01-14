from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFirecrawlAPIComponent(ComposioBaseComponent):
    component_id: str = "a0a201ac-2a76-4b9d-9344-ff79e128d40a"
    display_name: str = "Firecrawl"
    icon = "Firecrawl"
    documentation: str = "https://docs.composio.dev"
    app_name = "firecrawl"

    def set_default_tools(self):
        """Set the default tools for Firecrawl component."""
