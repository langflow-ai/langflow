from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioWrikeAPIComponent(ComposioBaseComponent):
    display_name: str = "Wrike"
    icon = "Wrike"
    documentation: str = "https://docs.composio.dev"
    app_name = "wrike"

    def set_default_tools(self):
        """Set the default tools for Wrike component."""
