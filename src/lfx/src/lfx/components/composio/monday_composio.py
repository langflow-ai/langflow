from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioMondayAPIComponent(ComposioBaseComponent):
    display_name: str = "Monday"
    icon = "Monday"
    documentation: str = "https://docs.composio.dev"
    app_name = "monday"

    def set_default_tools(self):
        """Set the default tools for Monday component."""
