from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioTypefullyAPIComponent(ComposioBaseComponent):
    display_name: str = "Typefully"
    icon = "Typefully"
    documentation: str = "https://docs.composio.dev"
    app_name = "typefully"

    def set_default_tools(self):
        """Set the default tools for Typefully component."""
