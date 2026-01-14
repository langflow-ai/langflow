from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioInstagramAPIComponent(ComposioBaseComponent):
    component_id: str = "61f9dd7e-7056-44a7-bba3-48d361ba8b04"
    display_name: str = "Instagram"
    icon = "Instagram"
    documentation: str = "https://docs.composio.dev"
    app_name = "instagram"

    def set_default_tools(self):
        """Set the default tools for Instagram component."""
