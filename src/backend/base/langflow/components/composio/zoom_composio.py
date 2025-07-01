from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioZoomAPIComponent(ComposioBaseComponent):
    display_name: str = "Zoom"
    icon = "Zoom"
    documentation: str = "https://docs.composio.dev"
    app_name = "zoom"

    def set_default_tools(self):
        """Set the default tools for Zoom component."""
