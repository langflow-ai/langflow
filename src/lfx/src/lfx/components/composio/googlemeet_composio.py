from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGooglemeetAPIComponent(ComposioBaseComponent):
    component_id: str = "f9ce3fdf-623d-4963-b409-cad645b48971"
    display_name: str = "GoogleMeet"
    icon = "Googlemeet"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlemeet"

    def set_default_tools(self):
        """Set the default tools for Google Calendar component."""
