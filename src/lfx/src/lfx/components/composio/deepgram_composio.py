from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioDeepgramAPIComponent(ComposioBaseComponent):
    display_name: str = "Deepgram"
    icon = "Deepgram"
    documentation: str = "https://docs.composio.dev"
    app_name = "deepgram"

    def set_default_tools(self):
        """Set the default tools for Deepgram component."""
