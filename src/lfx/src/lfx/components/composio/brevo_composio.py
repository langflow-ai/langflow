from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioBrevoAPIComponent(ComposioBaseComponent):
    display_name: str = "Brevo"
    icon = "Brevo"
    documentation: str = "https://docs.composio.dev"
    app_name = "brevo"

    def set_default_tools(self):
        """Set the default tools for Brevo component."""
