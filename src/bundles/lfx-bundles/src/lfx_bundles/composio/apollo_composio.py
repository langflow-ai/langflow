from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioApolloAPIComponent(ComposioBaseComponent):
    display_name: str = "Apollo"
    icon = "Apollo"
    documentation: str = "https://docs.composio.dev"
    app_name = "apollo"

    def set_default_tools(self):
        """Set the default tools for Apollo component."""
