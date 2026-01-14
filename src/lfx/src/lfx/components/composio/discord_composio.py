from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioDiscordAPIComponent(ComposioBaseComponent):
    component_id: str = "40ab6c77-4264-4953-a2b0-84c532db7337"
    display_name: str = "Discord"
    icon = "discord"
    documentation: str = "https://docs.composio.dev"
    app_name = "discord"

    def set_default_tools(self):
        """Set the default tools for Discord component."""
