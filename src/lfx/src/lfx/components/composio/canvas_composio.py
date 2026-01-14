from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCanvasAPIComponent(ComposioBaseComponent):
    component_id: str = "0dca307a-8a6e-4444-ae9a-5c9442536b5c"
    display_name: str = "Canvas"
    icon = "Canvas"
    documentation: str = "https://docs.composio.dev"
    app_name = "canvas"

    def set_default_tools(self):
        """Set the default tools for Canvaas component."""
