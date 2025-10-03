from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFirefliesAPIComponent(ComposioBaseComponent):
    display_name: str = "Fireflies"
    icon = "Fireflies"
    documentation: str = "https://docs.composio.dev"
    app_name = "fireflies"

    def set_default_tools(self):
        """Set the default tools for Fireflies component."""
