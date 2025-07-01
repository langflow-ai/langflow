from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGooglesheetsAPIComponent(ComposioBaseComponent):
    display_name: str = "Google Sheets"
    icon = "Googlesheets"
    documentation: str = "https://docs.composio.dev"
    app_name = "googlesheets"

    def set_default_tools(self):
        """Set the default tools for Google Sheets component."""
