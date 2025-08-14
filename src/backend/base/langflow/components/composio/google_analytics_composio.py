from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleAnalyticsAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Analytics"
    icon = "GoogleAnalytics"
    documentation: str = "https://docs.composio.dev"
    app_name = "google_analytics"

    def set_default_tools(self):
        """Set the default tools for Google Analytics component."""
