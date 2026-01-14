from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioAsanaAPIComponent(ComposioBaseComponent):
    component_id: str = "d8d7e9c7-3ef2-4d24-9338-a291fb975921"
    display_name: str = "Asana"
    icon = "Asana"
    documentation: str = "https://docs.composio.dev"
    app_name = "asana"

    def set_default_tools(self):
        """Set the default tools for Asana component."""
