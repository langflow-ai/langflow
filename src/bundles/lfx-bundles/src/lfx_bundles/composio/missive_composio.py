from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioMissiveAPIComponent(ComposioBaseComponent):
    display_name: str = "Missive"
    icon = "Missive"
    documentation: str = "https://docs.composio.dev"
    app_name = "missive"

    def set_default_tools(self):
        """Set the default tools for Missive component."""
