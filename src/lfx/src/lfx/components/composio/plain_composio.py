from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioPlainAPIComponent(ComposioBaseComponent):
    display_name: str = "Plain"
    icon = "Plain"
    documentation: str = "https://docs.composio.dev"
    app_name = "plain"

    def set_default_tools(self):
        """Set the default tools for Plain component."""
