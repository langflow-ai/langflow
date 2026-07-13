from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioCodaAPIComponent(ComposioBaseComponent):
    display_name: str = "Coda"
    icon = "Coda"
    documentation: str = "https://docs.composio.dev"
    app_name = "coda"

    def set_default_tools(self):
        """Set the default tools for Coda component."""
