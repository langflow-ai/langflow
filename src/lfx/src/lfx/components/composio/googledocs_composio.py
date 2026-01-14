from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleDocsAPIComponent(ComposioBaseComponent):
    component_id: str = "bbb5a067-2d13-4054-bab8-f03d677bbcd6"
    display_name: str = "GoogleDocs"
    icon = "Googledocs"
    documentation: str = "https://docs.composio.dev"
    app_name = "googledocs"

    def set_default_tools(self):
        """Set the default tools for Google Docs component."""
