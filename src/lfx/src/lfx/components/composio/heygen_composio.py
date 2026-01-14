from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioHeygenAPIComponent(ComposioBaseComponent):
    component_id: str = "01e62c82-88b7-4e8a-82e5-ac469abab90b"
    display_name: str = "Heygen"
    icon = "Heygen"
    documentation: str = "https://docs.composio.dev"
    app_name = "heygen"

    def set_default_tools(self):
        """Set the default tools for Heygen component."""
