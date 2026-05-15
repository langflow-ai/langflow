from lfx_composio.base.composio_base import ComposioBaseComponent


class ComposioRedditAPIComponent(ComposioBaseComponent):
    display_name: str = "Reddit"
    icon = "Reddit"
    documentation: str = "https://docs.composio.dev"
    app_name = "reddit"

    def set_default_tools(self):
        """Set the default tools for Reddit component."""
