from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioElevenLabsAPIComponent(ComposioBaseComponent):
    component_id: str = "6164114a-aa5a-4f8b-b0b3-a4a26754d511"
    display_name: str = "ElevenLabs"
    icon = "Elevenlabs"
    documentation: str = "https://docs.composio.dev"
    app_name = "elevenlabs"

    def set_default_tools(self):
        """Set the default tools for ElevenLabs component."""
