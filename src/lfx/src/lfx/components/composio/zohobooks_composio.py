from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioZohoBooksAPIComponent(ComposioBaseComponent):
    display_name: str = "Zoho Books"
    icon = "Zohobooks"
    documentation: str = "https://docs.composio.dev"
    app_name = "zoho_books"

    def set_default_tools(self):
        """Set the default tools for Zoho Books component."""
