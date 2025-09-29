from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBrandfetchAPIComponent(ComposioBaseComponent):
    display_name: str = "Brandfetch"
    icon = "Brandfetch"
    documentation: str = "https://docs.composio.dev"
    app_name = "brandfetch"

    def set_default_tools(self):
        """Set the default tools for Brandfetch component."""
