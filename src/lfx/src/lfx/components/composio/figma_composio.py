from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFigmaAPIComponent(ComposioBaseComponent):
    component_id: str = "cfe29417-73da-4e3f-a598-4a570d9b2be0"
    display_name: str = "Figma"
    icon = "Figma"
    documentation: str = "https://docs.composio.dev"
    app_name = "figma"

    def set_default_tools(self):
        """Set the default tools for Figma component."""
