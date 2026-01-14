from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioFreshdeskAPIComponent(ComposioBaseComponent):
    component_id: str = "ea28dc9c-33b4-46b0-bd76-4b15c59acd63"
    display_name: str = "Freshdesk"
    icon = "Freshdesk"
    documentation: str = "https://docs.composio.dev"
    app_name = "freshdesk"

    def set_default_tools(self):
        """Set the default tools for Freshdesk component."""
