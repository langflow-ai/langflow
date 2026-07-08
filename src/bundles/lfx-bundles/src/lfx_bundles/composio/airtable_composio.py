from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioAirtableAPIComponent(ComposioBaseComponent):
    display_name: str = "Airtable"
    icon = "Airtable"
    documentation: str = "https://docs.composio.dev"
    app_name = "airtable"

    def set_default_tools(self):
        """Set the default tools for Airtable component."""
