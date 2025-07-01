from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleDriveAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Drive"
    icon = "GoogleDrive"
    documentation: str = "https://docs.composio.dev"
    app_name = "googledrive"

    def set_default_tools(self):
        """Set the default tools for Google Drive component."""
