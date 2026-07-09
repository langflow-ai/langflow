from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFigmaAPIComponent(ComposioBaseComponent):
    display_name: str = "Figma"
    icon = "Figma"
    documentation: str = "https://docs.composio.dev"
    app_name = "figma"

    def set_default_tools(self):
        """Set the default tools for Figma component."""
