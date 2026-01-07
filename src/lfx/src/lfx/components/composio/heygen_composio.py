from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioHeygenAPIComponent(ComposioBaseComponent):
    display_name: str = "Heygen"
    icon = "Heygen"
    documentation: str = "https://docs.composio.dev"
    app_name = "heygen"

    def set_default_tools(self):
        """Set the default tools for Heygen component."""
