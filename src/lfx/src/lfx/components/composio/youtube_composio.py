from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioYoutubeAPIComponent(ComposioBaseComponent):
    display_name: str = "YouTube"
    icon = "Youtube"
    documentation: str = "https://docs.composio.dev"
    app_name = "youtube"

    def set_default_tools(self):
        """Set the default tools for YouTube component."""
