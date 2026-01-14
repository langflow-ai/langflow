from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioExaAPIComponent(ComposioBaseComponent):
    component_id: str = "847d5e2b-f3ba-4ef7-b3ef-e9d8c10432f7"
    display_name: str = "Exa"
    icon = "ExaComposio"
    documentation: str = "https://docs.composio.dev"
    app_name = "exa"

    def set_default_tools(self):
        """Set the default tools for Exa component."""
