from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioDiscordBotAPIComponent(ComposioBaseComponent):
    display_name: str = "Discord Bot"
    icon = "Discord"
    documentation: str = "https://docs.composio.dev"
    app_name = "discordbot"

    def set_default_tools(self):
        """Set the default tools for Discord component."""
