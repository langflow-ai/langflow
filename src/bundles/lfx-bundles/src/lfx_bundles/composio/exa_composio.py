from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioExaAPIComponent(ComposioBaseComponent):
    display_name: str = "Exa"
    icon = "ExaComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "exa"

    def set_default_tools(self):
        """Set the default tools for Exa component."""
