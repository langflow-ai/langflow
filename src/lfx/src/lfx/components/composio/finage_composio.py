from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFinageAPIComponent(ComposioBaseComponent):
    display_name: str = "Finage"
    icon = "Finage"
    documentation: str = "https://docs.composio.dev"
    app_name = "finage"

    def set_default_tools(self):
        """Set the default tools for Finage component."""
