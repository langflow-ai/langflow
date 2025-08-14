from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioHubspotAPIComponent(ComposioBaseComponent):
    display_name: str = "Hubspot"
    icon = "Hubspot"
    documentation: str = "https://docs.composio.dev"
    app_name = "hubspot"

    def set_default_tools(self):
        """Set the default tools for Hubspot component."""
