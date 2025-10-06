from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioDiscordAPIComponent(ComposioBaseComponent):
    display_name: str = "Discord"
    icon = "Discord"
    documentation: str = "https://docs.composio.dev"
    app_name = "discord"

    def set_default_tools(self):
        """Set the default tools for Discord component."""
