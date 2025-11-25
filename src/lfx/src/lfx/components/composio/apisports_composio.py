from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioAPISportsAPIComponent(ComposioBaseComponent):
    display_name: str = "API Sports"
    icon = "Sportsapi"
    documentation: str = "https://docs.composio.dev"
    app_name = "api_sports"

    def set_default_tools(self):
        """Set the default tools for API Sports component."""
