from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioApolloAPIComponent(ComposioBaseComponent):
    component_id: str = "6b246e1c-8947-4c8a-865b-0d289b04615f"
    display_name: str = "Apollo"
    icon = "Apollo"
    documentation: str = "https://docs.composio.dev"
    app_name = "apollo"

    def set_default_tools(self):
        """Set the default tools for Apollo component."""
