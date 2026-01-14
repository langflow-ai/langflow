from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioRedditAPIComponent(ComposioBaseComponent):
    component_id: str = "afae0141-2ee1-4554-8725-c42aa56a9177"
    display_name: str = "Reddit"
    icon = "Reddit"
    documentation: str = "https://docs.composio.dev"
    app_name = "reddit"

    def set_default_tools(self):
        """Set the default tools for Reddit component."""
