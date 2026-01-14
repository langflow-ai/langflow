from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioSlackbotAPIComponent(ComposioBaseComponent):
    component_id: str = "4b6f45b9-5a71-4395-a620-98a0c00551bf"
    display_name: str = "Slackbot"
    icon = "SlackComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "slackbot"

    def set_default_tools(self):
        """Set the default tools for Slackbot component."""
