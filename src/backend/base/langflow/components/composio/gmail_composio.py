from langflow.base.composio.composio_base import ComposioBaseComponent


class ComposioGmailAPIComponent(ComposioBaseComponent):
    """Thin Gmail component – all heavy lifting now lives in ComposioBaseComponent."""

    display_name: str = "Gmail"
    name = "GmailAPI"
    icon = "Google"
    documentation: str = "https://docs.composio.dev"
    app_name = "gmail"

    def set_default_tools(self):
        """Set the default tools for Gmail component."""
        pass
