from langflow.base.composio.composio_base import ComposioBaseComponent
class ComposioOutlookAPIComponent(ComposioBaseComponent):
    display_name: str = "Outlook"
    icon = "Outlook"
    documentation: str = "https://docs.composio.dev"
    app_name = "outlook"

    def set_default_tools(self):
        """Set the default tools for Gmail component."""
        pass