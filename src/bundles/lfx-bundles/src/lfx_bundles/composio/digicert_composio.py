from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioDigicertAPIComponent(ComposioBaseComponent):
    display_name: str = "Digicert"
    icon = "Digicert"
    documentation: str = "https://docs.composio.dev"
    app_name = "digicert"

    def set_default_tools(self):
        """Set the default tools for Digicert component."""
