from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioSalesforceAPIComponent(ComposioBaseComponent):
    display_name: str = "Salesforce"
    icon = "Salesforce"
    documentation: str = "https://docs.composio.dev"
    app_name = "salesforce"

    def set_default_tools(self):
        """Set the default tools for Salesforce component."""
