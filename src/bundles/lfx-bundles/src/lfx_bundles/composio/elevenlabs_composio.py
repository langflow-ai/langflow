from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioElevenLabsAPIComponent(ComposioBaseComponent):
    display_name: str = "ElevenLabs"
    icon = "Elevenlabs"
    documentation: str = "https://docs.composio.dev"
    app_name = "elevenlabs"

    def set_default_tools(self):
        """Set the default tools for ElevenLabs component."""
