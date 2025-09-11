from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioSlackAPIComponent(ComposioBaseComponent):
    display_name: str = "Slack"
    icon = "Slack"
    documentation: str = "https://docs.composio.dev"
    app_name = "slack"

    def set_default_tools(self):
        """Set the default tools for Slack component."""
