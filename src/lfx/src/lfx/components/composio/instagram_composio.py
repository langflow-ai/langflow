from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioInstagramAPIComponent(ComposioBaseComponent):
    display_name: str = "Instagram"
    icon = "Instagram"
    documentation: str = "https://docs.composio.dev"
    app_name = "instagram"

    def set_default_tools(self):
        """Set the default tools for Instagram component."""
