from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleDocsAPIComponent(ComposioBaseComponent):
    display_name: str = "GoogleDocs"
    icon = "Googledocs"
    documentation: str = "https://docs.composio.dev"
    app_name = "googledocs"

    def set_default_tools(self):
        """Set the default tools for Google Docs component."""
