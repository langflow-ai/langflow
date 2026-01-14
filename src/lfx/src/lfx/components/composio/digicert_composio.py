from lfx.base.composio.composio_base import ComposioBaseComponent


class ComposioDigicertAPIComponent(ComposioBaseComponent):
    component_id: str = "4b6ca940-aad8-4cbb-ab7e-330820190ef9"
    display_name: str = "Digicert"
    icon = "Digicert"
    documentation: str = "https://docs.composio.dev"
    app_name = "digicert"

    def set_default_tools(self):
        """Set the default tools for Digicert component."""
