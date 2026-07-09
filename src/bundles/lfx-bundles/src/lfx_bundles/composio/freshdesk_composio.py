from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFreshdeskAPIComponent(ComposioBaseComponent):
    display_name: str = "Freshdesk"
    icon = "Freshdesk"
    documentation: str = "https://docs.composio.dev"
    app_name = "freshdesk"

    def set_default_tools(self):
        """Set the default tools for Freshdesk component."""
