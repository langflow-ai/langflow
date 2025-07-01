from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioDropboxAPIComponent(ComposioBaseComponent):
    display_name: str = "Dropbox"
    icon = "Dropbox"
    documentation: str = "https://docs.composio.dev"
    app_name = "dropbox"

    def set_default_tools(self):
        """Set the default tools for Dropbox component."""
