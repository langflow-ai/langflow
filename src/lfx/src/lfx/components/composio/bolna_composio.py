from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBolnaAPIComponent(ComposioBaseComponent):
    display_name: str = "Bolna"
    icon = "Bolna"
    documentation: str = "https://docs.composio.dev"
    app_name = "bolna"

    def set_default_tools(self):
        """Set the default tools for Bolna component."""
