
from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGooglemeetAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Meet"
    icon = "Googlemeet"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlemeet"

    def set_default_tools(self):
        """Set the default tools for Google Calendar component."""
