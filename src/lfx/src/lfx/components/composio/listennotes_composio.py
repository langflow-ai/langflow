from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioListennotesAPIComponent(ComposioBaseComponent):
    display_name: str = "Listennotes"
    icon = "Listennotes"
    documentation: str = "https://docs.composio.dev"
    app_name = "listennotes"

    def set_default_tools(self):
        """Set the default tools for Listennotes component."""
