from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleBigQueryAPIComponent(ComposioBaseComponent):
    component_id: str = "d54d008c-be66-4b64-a5cf-2d2f0379c5ba"
    display_name: str = "GoogleBigQuery"
    icon = "Googlebigquery"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlebigquery"

    def set_default_tools(self):
        """Set the default tools for Google BigQuery component."""
