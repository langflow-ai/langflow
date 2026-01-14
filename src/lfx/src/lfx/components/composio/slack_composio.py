from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSlackAPIComponent(ComposioBaseComponent):
    component_id: str = "45664ecb-a047-414a-aad3-17c680acd19f"
    display_name: str = "Slack"
    icon = "SlackComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "slack"

    def set_default_tools(self):
        """Set the default tools for Slack component."""
