from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleBigQueryAPIComponent(ComposioBaseComponent):
    display_name: str = "GoogleBigQuery"
    icon = "Googlebigquery"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlebigquery"

    def set_default_tools(self):
        """Set the default tools for Google BigQuery component."""
