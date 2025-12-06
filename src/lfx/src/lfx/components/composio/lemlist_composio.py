from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioLemlistAPIComponent(ComposioBaseComponent):
    display_name: str = "Lemlist"
    icon = "Lemlist"
    documentation: str = "https://docs.composio.dev"
    app_name = "lemlist"

    def set_default_tools(self):
        """Set the default tools for Lemlist component."""
