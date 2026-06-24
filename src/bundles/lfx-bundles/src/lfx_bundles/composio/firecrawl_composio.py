from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFirecrawlAPIComponent(ComposioBaseComponent):
    display_name: str = "Firecrawl"
    icon = "Firecrawl"
    documentation: str = "https://docs.composio.dev"
    app_name = "firecrawl"

    def set_default_tools(self):
        """Set the default tools for Firecrawl component."""
