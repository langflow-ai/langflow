from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioGoogleSheetsAPIComponent(ComposioBaseComponent):
    component_id: str = "63174978-389e-4ba5-8820-00fbee15c6c4"
    display_name: str = "GoogleSheets"
    icon = "Googlesheets"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlesheets"

    def set_default_tools(self):
        """Set the default tools for Google Sheets component."""
