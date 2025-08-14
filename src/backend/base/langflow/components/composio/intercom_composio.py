from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioIntercomAPIComponent(ComposioBaseComponent):
    display_name: str = "Intercom"
    icon = "Intercom"
    documentation: str = "https://docs.composio.dev"
    app_name = "intercom"

    def set_default_tools(self):
        """Set the default tools for Intercom component."""
