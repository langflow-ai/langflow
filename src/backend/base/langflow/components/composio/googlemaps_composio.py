from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleMapsAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Maps"
    icon = "Googlemaps"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlemaps"

    def set_default_tools(self):
        """Set the default tools for Google Maps component."""
