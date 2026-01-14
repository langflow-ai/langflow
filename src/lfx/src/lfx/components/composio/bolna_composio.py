from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBolnaAPIComponent(ComposioBaseComponent):
    component_id: str = "dff94459-77a0-4cf2-b5fb-201982fe775b"
    display_name: str = "Bolna"
    icon = "Bolna"
    documentation: str = "https://docs.composio.dev"
    app_name = "bolna"

    def set_default_tools(self):
        """Set the default tools for Bolna component."""
