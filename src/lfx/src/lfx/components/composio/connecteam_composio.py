from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioConnecteamAPIComponent(ComposioBaseComponent):
    display_name: str = "Connecteam"
    icon = "Connecteam"
    documentation: str = "https://docs.composio.dev"
    app_name = "connecteam"

    def set_default_tools(self):
        """Set the default tools for Connecteam component."""
