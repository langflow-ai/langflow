from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioMiroAPIComponent(ComposioBaseComponent):
    display_name: str = "Miro"
    icon = "Miro"
    documentation: str = "https://docs.composio.dev"
    app_name = "miro"

    def set_default_tools(self):
        """Set the default tools for Miro component."""
