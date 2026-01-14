from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioAirtableAPIComponent(ComposioBaseComponent):
    component_id: str = "f191b9ad-a829-4a97-a1b7-847d52976b69"
    display_name: str = "Airtable"
    icon = "Airtable"
    documentation: str = "https://docs.composio.dev"
    app_name = "airtable"

    def set_default_tools(self):
        """Set the default tools for Airtable component."""
