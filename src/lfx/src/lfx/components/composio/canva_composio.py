from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCanvaAPIComponent(ComposioBaseComponent):
    component_id: str = "20961be7-1ddd-4666-8f53-7241535975bf"
    display_name: str = "Canva"
    icon = "Canva"
    documentation: str = "https://docs.composio.dev"
    app_name = "canva"

    def set_default_tools(self):
        """Set the default tools for Canva component."""
