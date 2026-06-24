from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioOneDriveAPIComponent(ComposioBaseComponent):
    display_name: str = "OneDrive"
    icon = "One_Drive"
    documentation: str = "https://docs.composio.dev"
    app_name = "one_drive"

    def set_default_tools(self):
        """Set the default tools for OneDrive component."""
