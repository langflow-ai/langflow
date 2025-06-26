from langflow.base.composio.composio_base import ComposioBaseComponent
class ComposioGmailAPIComponent(ComposioBaseComponent):
    display_name: str = "Gmail"
    icon = "Google"
    documentation: str = "https://docs.composio.dev"
    app_name = "gmail"

    def set_default_tools(self):
        """Set the default tools for Gmail component."""
        pass
