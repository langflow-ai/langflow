from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSlackbotAPIComponent(ComposioBaseComponent):
    display_name: str = "Slackbot"
    icon = "Slack"
    documentation: str = "https://docs.composio.dev"
    app_name = "slackbot"

    def set_default_tools(self):
        """Set the default tools for Slackbot component."""
