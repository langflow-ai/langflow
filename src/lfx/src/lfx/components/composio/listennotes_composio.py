from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioListennotesAPIComponent(ComposioBaseComponent):
    component_id: str = "25910249-4ef0-41f7-b63a-79283a19639f"
    display_name: str = "Listennotes"
    icon = "Listennotes"
    documentation: str = "https://docs.composio.dev"
    app_name = "listennotes"

    def set_default_tools(self):
        """Set the default tools for Listennotes component."""
