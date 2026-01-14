from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioOneDriveAPIComponent(ComposioBaseComponent):
    component_id: str = "7c301d44-9019-426f-b951-233a5990cd63"
    display_name: str = "OneDrive"
    icon = "One_Drive"
    documentation: str = "https://docs.composio.dev"
    app_name = "one_drive"

    def set_default_tools(self):
        """Set the default tools for OneDrive component."""
