from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCanvaAPIComponent(ComposioBaseComponent):
    display_name: str = "Canva"
    icon = "Canva"
    documentation: str = "https://docs.composio.dev"
    app_name = "canva"

    def set_default_tools(self):
        """Set the default tools for Canva component."""
